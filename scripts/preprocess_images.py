#!/usr/bin/env python3
"""Preprocess markdown images for crisp e-ink rendering on the reMarkable 2.

For every markdown image reference ![alt](src) (http/https URL or local path):
  1. fetch (URLs, urllib, 15s timeout, UA header) or read the local file
  2. grayscale + autocontrast + EXIF-orient + flatten alpha onto white
  3. downscale so width <= 1170px (column width at 226dpi), height <= 1500px
  4. dither to 1-bit Floyd-Steinberg (default) -- newspaper halftone, not blur
  5. save <workdir>/img-<n>.png and rewrite the markdown ref to an absolute path

Failed fetches become an italic caption:  *[image unavailable: <src>]*

Prints one JSON object to stdout: {"found": N, "converted": M, "failed": K, ...}
Progress/diagnostics go to stderr. Exit 0 even if some images failed.

Usage:
  preprocess_images.py ARTICLE.md [--workdir DIR] [--out OUT.md]
                     [--mode fs1|threshold|gray4|gray]
                     [--max-width 1170] [--max-height 1500] [--timeout 15]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

try:
    import numpy as np
except ImportError:  # gray4 needs numpy; fs1/threshold do not
    np = None

UA = ("Mozilla/5.0 (X11; Linux x86_64) remarkable-eink-preprocessor/1.0")
MAX_DOWNLOAD = 64 * 1024 * 1024  # refuse absurdly large remote images

# ![alt](src)  |  ![alt](<src with spaces>)  |  ![alt](src "title")
IMG_RE = re.compile(r'!\[([^\]]*)\]\(\s*(<[^>]+>|[^)\s]+)(?:\s+("[^"]*"))?\s*\)')


# ---------------------------------------------------------------- fetch/load

_last_fetch_ts = 0.0  # be polite: >= 3s between remote requests


def fetch_url(url: str, timeout: int, attempts: int = 3) -> bytes:
    global _last_fetch_ts
    last_err: Exception | None = None
    for i in range(attempts):
        if i:
            # Wikimedia-style rate limiters put the IP in a ~1min penalty box;
            # back off long enough to outlive it: 60s, then 90s.
            time.sleep(60 if i == 1 else 90)
        wait = 3.0 - (time.monotonic() - _last_fetch_ts)
        if wait > 0:
            time.sleep(wait)
        req = urllib.request.Request(url, headers={
            "User-Agent": UA,
            "Accept": "image/*,*/*;q=0.8",
        })
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                _last_fetch_ts = time.monotonic()
                chunks, total = [], 0
                while True:
                    chunk = r.read(1 << 16)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_DOWNLOAD:
                        raise ValueError(
                            f"remote image larger than {MAX_DOWNLOAD >> 20}MB")
                    chunks.append(chunk)
            return b"".join(chunks)
        except urllib.error.HTTPError as e:
            _last_fetch_ts = time.monotonic()
            if e.code == 429 or 500 <= e.code < 600:
                print(f"  ... HTTP {e.code}, backing off before retry",
                      file=sys.stderr)
                last_err = e  # transient -> retry with backoff
                continue
            raise
    raise last_err  # type: ignore[misc]


def load_gray(data: bytes | str) -> Image.Image:
    """Decode, honor EXIF rotation, flatten alpha onto white, grayscale,
    autocontrast (1% tail cutoff)."""
    im = Image.open(data if isinstance(data, str) else BytesIO(data))
    im.load()
    im = ImageOps.exif_transpose(im)
    if im.mode == "P":
        im = im.convert("RGBA")
    if im.mode in ("RGBA", "LA"):
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    return ImageOps.autocontrast(im.convert("L"), cutoff=1)


def fit(im: Image.Image, max_w: int, max_h: int) -> Image.Image:
    """Downscale only: width <= max_w, height <= max_h, aspect kept."""
    w, h = im.size
    scale = min(1.0, max_w / w, max_h / h)
    if scale < 1.0:
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                       Image.LANCZOS)
    return im


# ------------------------------------------------------------------ dithering

def dither_fs1(g: Image.Image) -> Image.Image:
    # PIL's convert('1') dithers with Floyd-Steinberg BY DEFAULT (verified:
    # bit-identical to explicit dither=Image.Dither.FLOYDSTEINBERG); be explicit
    # anyway so the intent survives PIL upgrades.
    return g.convert("1", dither=Image.Dither.FLOYDSTEINBERG)


def dither_threshold(g: Image.Image, t: int = 128) -> Image.Image:
    return g.point(lambda v: 255 if v >= t else 0, mode="1")


def dither_fs_nbits(g: Image.Image, levels: int = 4) -> Image.Image:
    """Floyd-Steinberg error diffusion onto `levels` equidistant grays.
    Saved as 8-bit PNG holding only those values (e.g. 0/85/170/255 for 2-bit).
    Needs numpy; the diffusion is inherently sequential, so this is a plain
    loop and takes a few seconds at 1170px."""
    if np is None:
        raise RuntimeError("gray4 mode requires numpy")
    a = np.asarray(g, dtype=np.float64).tolist()  # lists: faster scalar ops
    h, w = len(a), len(a[0])
    q = 255.0 / (levels - 1)
    out = [[0] * w for _ in range(h)]
    for y in range(h):
        row = a[y]
        orow = out[y]
        below = a[y + 1] if y + 1 < h else None
        for x in range(w):
            old = row[x]
            new = round(old / q) * q
            if new < 0.0:
                new = 0.0
            elif new > 255.0:
                new = 255.0
            err = old - new
            orow[x] = int(new)
            if x + 1 < w:
                row[x + 1] += err * 0.4375          # 7/16
            if below is not None:
                if x > 0:
                    below[x - 1] += err * 0.1875    # 3/16
                below[x] += err * 0.3125            # 5/16
                if x + 1 < w:
                    below[x + 1] += err * 0.0625    # 1/16
    return Image.fromarray(np.asarray(out, dtype=np.uint8), "L")


DITHERERS = {
    "fs1": dither_fs1,
    "threshold": dither_threshold,
    "gray4": dither_fs_nbits,
    "gray": lambda g: g,  # plain grayscale, for comparison only
}


# ----------------------------------------------------------------- rewriting

def process_markdown(md_text: str, md_dir: Path, workdir: Path, mode: str,
                     max_w: int, max_h: int, timeout: int):
    """Returns (new_md_text, summary_dict)."""
    workdir.mkdir(parents=True, exist_ok=True)
    cache: dict[str, str] = {}          # src -> abs png path (dedup repeats)
    found = converted = 0
    failed: list[dict] = []
    counter = 0
    out_lines: list[str] = []
    in_fence = False

    for line in md_text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            out_lines.append(line)
            continue
        if in_fence or "![" not in line:
            out_lines.append(line)
            continue

        def rewrite(m: re.Match) -> str:
            nonlocal counter, found, converted
            alt, raw_src, title = m.group(1), m.group(2), m.group(3)
            src = raw_src[1:-1] if raw_src.startswith("<") else raw_src
            is_url = src.startswith(("http://", "https://"))
            if not is_url and not (md_dir / src).exists() and not Path(src).is_absolute():
                # leave data: and other exotic schemes untouched
                if "://" in src or src.startswith("data:"):
                    return m.group(0)
            found += 1
            if src in cache:
                return f"![{alt}]({cache[src]}{(' ' + title) if title else ''})"
            try:
                if is_url:
                    data = fetch_url(src, timeout)
                    gray = load_gray(data)
                else:
                    p = Path(src)
                    if not p.is_absolute():
                        p = md_dir / p
                    if not p.exists():
                        raise FileNotFoundError(p)
                    gray = load_gray(str(p))
                gray = fit(gray, max_w, max_h)
                final = DITHERERS[mode](gray)
                counter += 1
                out = (workdir / f"img-{counter}.png").resolve()
                final.save(out, format="PNG", optimize=True)
                cache[src] = str(out)
                converted += 1
                print(f"  ok  {src[:80]} -> {out.name} "
                      f"{final.size[0]}x{final.size[1]} mode={final.mode}",
                      file=sys.stderr)
                return f"![{alt}]({out}{(' ' + title) if title else ''})"
            except Exception as e:  # noqa: BLE001 - any failure -> caption
                failed.append({"src": src, "error": f"{type(e).__name__}: {e}"[:200]})
                print(f"  FAIL {src[:80]}: {e}", file=sys.stderr)
                return f"*[image unavailable: {src}]*"

        out_lines.append(IMG_RE.sub(rewrite, line))

    summary = {
        "found": found,
        "converted": converted,
        "failed": len(failed),
        "mode": mode,
        "workdir": str(workdir.resolve()),
        "images": {s: p for s, p in cache.items()},
        "failures": failed,
    }
    return "".join(out_lines), summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("file", help="input markdown file")
    ap.add_argument("--workdir", help="dir for img-<n>.png "
                    "(default: <file dir>/<stem>-images)")
    ap.add_argument("--out", help="output markdown (default: <workdir>/<stem>.eink.md)")
    ap.add_argument("--mode", choices=sorted(DITHERERS), default="fs1",
                    help="dithering: fs1 = 1-bit Floyd-Steinberg (default), "
                         "threshold = hard 128 cut, gray4 = 4-level FS, "
                         "gray = no dither (comparison only)")
    ap.add_argument("--max-width", type=int, default=1170,
                    help="max pixel width at 226dpi (default 1170)")
    ap.add_argument("--max-height", type=int, default=1500,
                    help="max pixel height (default 1500)")
    ap.add_argument("--timeout", type=int, default=15,
                    help="per-image fetch timeout seconds (default 15)")
    args = ap.parse_args()

    src = Path(args.file)
    if not src.exists():
        print(f"ERROR: no such file: {src}", file=sys.stderr)
        return 1
    md_text = src.read_text(encoding="utf-8")
    workdir = Path(args.workdir) if args.workdir else src.parent / f"{src.stem}-images"
    out_path = Path(args.out) if args.out else workdir / f"{src.stem}.eink.md"

    new_md, summary = process_markdown(md_text, src.parent, workdir, args.mode,
                                       args.max_width, args.max_height, args.timeout)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(new_md, encoding="utf-8")
    summary["out_md"] = str(out_path)

    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
