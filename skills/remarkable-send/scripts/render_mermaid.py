#!/usr/bin/env python3
"""Render ```mermaid blocks to standalone PNGs via headless Chrome.

Each block becomes a diagram image: HTML + mermaid.js (CDN, cached),
chrome --screenshot on a large white canvas, PIL autocrop + grayscale +
autocontrast for e-ink. Output feeds prepare_markdown.py which swaps the
blocks for image references.

Usage: render_mermaid.py MARKDOWN_FILE --outdir DIR [--cache DIR]
Prints JSON: {"rendered": n, "failed": n, "images": {index: path}}
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"

HTML = """<!doctype html><html><head><meta charset="utf-8">
<style>
  html, body {{ margin: 0; background: #fff; }}
  #d {{ padding: 40px; font-family: 'Liberation Sans', sans-serif; }}
  .mermaid {{ font-size: 22px; color: #000; max-width: 1600px; }}
</style>
<script>{lib}</script>
<script>
  mermaid.initialize({{ startOnLoad: true, theme: 'neutral',
    themeVariables: {{ fontSize: '22px', primaryColor: '#fff',
      primaryBorderColor: '#000', lineColor: '#000',
      tertiaryColor: '#fff', secondaryColor: '#fff' }} }});
  window.__done = false;
  mermaid.run({{ postProcess: () => {{ window.__done = true; }} }})
    .catch(() => {{ window.__done = true; }});
  setTimeout(() => {{ window.__done = true; }}, 12000);
</script>
</head><body><div id="d"><pre class="mermaid">{diagram}</pre></div></body></html>"""


def fetch_lib(cache_dir: Path) -> Path:
    cache = cache_dir / "mermaid.min.js"
    if not cache.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(MERMAID_URL,
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r, open(cache, "wb") as f:
            f.write(r.read())
    return cache


def chrome_bin() -> str:
    import shutil
    for cand in ("google-chrome", "google-chrome-stable",
                 "chromium-browser", "chromium"):
        if shutil.which(cand):
            return cand
    return "google-chrome"


def shoot(html_path: Path, png_path: Path) -> bool:
    r = subprocess.run(
        [chrome_bin(), "--headless=new", "--disable-gpu", "--no-sandbox",
         "--disable-dev-shm-usage", f"--screenshot={png_path}",
         "--window-size=1800,2400", "--hide-scrollbars",
         "--virtual-time-budget=15000", str(html_path)],
        capture_output=True, text=True)
    return r.returncode == 0 and png_path.exists()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--cache", default=str(Path.home() / ".cache/remarkable-send"))
    args = ap.parse_args()

    src = Path(args.file).read_text(encoding="utf-8")
    blocks = list(re.finditer(r"```mermaid\n(.*?)```", src, re.S))
    out = {"rendered": 0, "failed": 0, "images": {}}
    if not blocks:
        print(json.dumps(out))
        return 0

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    lib = fetch_lib(Path(args.cache))

    import hashlib
    from PIL import Image, ImageOps
    for i, m in enumerate(blocks, 1):
        diagram = m.group(1).strip()
        key = hashlib.md5(diagram.encode("utf-8")).hexdigest()[:12]
        html = HTML.format(lib=lib.read_text(encoding="utf-8"),
                           diagram=diagram.replace("&", "&amp;").replace("<", "&lt;"))
        tmp_html = outdir / f"mm-{i}.html"
        raw = outdir / f"mm-{i}-raw.png"
        tmp_html.write_text(html, encoding="utf-8")
        try:
            if not shoot(tmp_html, raw):
                raise RuntimeError("chrome screenshot failed")
            im = Image.open(raw).convert("L")
            bbox = ImageOps.invert(im).getbbox()  # non-white content bounds
            if not bbox:
                raise RuntimeError("empty render (mermaid parse error?)")
            pad = 24
            bbox = (max(0, bbox[0]-pad), max(0, bbox[1]-pad),
                    min(im.width, bbox[2]+pad), min(im.height, bbox[3]+pad))
            im = im.crop(bbox)
            im = ImageOps.autocontrast(im, cutoff=1)
            # cap width to the tablet column at 2x for sharpness
            if im.width > 1600:
                im = im.resize((1600, round(im.height*1600/im.width)),
                               Image.LANCZOS)
            final = outdir / f"mermaid-{i:02d}.png"
            im.save(final, optimize=True)
            out["images"][key] = str(final)
            out["rendered"] += 1
        except Exception as e:
            out["failed"] += 1
            print(f"mermaid block {i}: {e}", file=sys.stderr)
        finally:
            raw.unlink(missing_ok=True)
            tmp_html.unlink(missing_ok=True)

    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
