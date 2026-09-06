#!/usr/bin/env python3
"""Prepare arbitrary markdown for remarkable-send: cleanup + mermaid swap.

Deterministic, so a drop-zone agent does not improvise:

1. ```mermaid blocks -> rendered PNGs (render_mermaid.py), unless --no-mermaid
   (then blocks are dropped with an italic caption). A <details> wrapper
   around the block is consumed together with the block.
2. Drops the document's own navigation sections: a heading like
   "## Навигация"/"## Navigation"/"## Contents" whose body is a single
   link-wall paragraph (the engine generates a real TOC itself).
3. Strips <a id="..."></a> anchor lines and {#custom-ids} from headings.
4. Image references to files that do not exist are removed together with
   an immediately following italic caption line about the same asset —
   silently (the rendered mermaid replaces them).
5. Unwraps remaining <details>/<summary> tags (keeps inner content).

Usage: prepare_markdown.py IN.md OUT.md [--workdir DIR] [--no-mermaid]
Prints a JSON summary on stderr.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

NAV_HEADINGS = ("навигация", "navigation", "contents", "оглавление",
                "содержание")


def clean_navigation(src: str) -> tuple[str, int]:
    out, removed = [], 0
    lines = src.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^#{1,3}\s+(.+?)\s*$", line.rstrip("\n"))
        if m and m.group(1).strip().lower() in NAV_HEADINGS:
            # consume the heading + following link-wall paragraph (lines
            # up to a blank-line-separated block that is mostly links)
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            para = []
            while j < len(lines) and lines[j].strip():
                para.append(lines[j])
                j += 1
            text = "".join(para)
            if text.count("](#") >= 3 or (para and len(re.findall(r"\]\(", text)) >= 5
                                          and len(para) <= 3):
                removed += 1
                i = j
                continue
        out.append(line)
        i += 1
    return "".join(out), removed


def strip_anchors(src: str) -> tuple[str, int]:
    n = len(re.findall(r'<a id="[^"]+"></a>', src))
    src = re.sub(r'<a id="[^"]+"></a>\s*', "", src)
    n2 = len(re.findall(r"\{#[a-zA-Z0-9_-]+\}\s*$", src, re.M))
    src = re.sub(r"\{#[a-zA-Z0-9_-]+\}\s*$", "", src, flags=re.M)
    return src, n + n2


def swap_mermaid(src: str, workdir: Path, do_render: bool, script_dir: Path) -> tuple[str, int]:
    blocks = list(re.finditer(
        r"(?:<details>\s*(?:<summary>[^<]*</summary>\s*)?)?```mermaid\n.*?```\s*(?:</details>\s*)?",
        src, re.S))
    if not blocks:
        return src, 0
    images: dict[int, str] = {}
    if do_render:
        tmp = workdir / "_mermaid_input.md"
        tmp.write_text(src, encoding="utf-8")
        r = subprocess.run(
            [sys.executable, str(script_dir / "render_mermaid.py"), str(tmp),
             "--outdir", str(workdir)],
            capture_output=True, text=True)
        try:
            data = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            data = {"rendered": 0, "failed": 0, "images": {}}
        images = dict(data.get("images", {}))
    import hashlib
    out, swapped, last = [], 0, 0
    for m in blocks:
        out.append(src[last:m.start()])
        inner = re.search(r"```mermaid\n(.*?)```", m.group(0), re.S)
        key = hashlib.md5(inner.group(1).strip().encode("utf-8")).hexdigest()[:12] if inner else None
        img = images.get(key)
        if img:
            out.append(f"\n![схема](<{img}>)\n\n*(авторская mermaid-схема, отрендерена для e-ink)*\n")
            swapped += 1
        else:
            out.append("\n*(mermaid-схема опущена: не отрендерилась)*\n")
        last = m.end()
    out.append(src[last:])
    return "".join(out), swapped


def drop_dead_images(src: str) -> tuple[str, int]:
    lines = src.splitlines(keepends=True)
    out, dropped, i = [], 0, 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"\s*!\[[^\]]*\]\(([^)]+)\)\s*$", line.rstrip("\n"))
        if m:
            target = m.group(1).strip("<>")
            if not re.match(r"^[a-z]+://", target) and not Path(target).exists():
                # also swallow a following italic caption about this asset
                j = i + 1
                if j < len(lines):
                    cap = lines[j].strip()
                    name = Path(target).name
                    if cap.startswith("*") and name[:20] in cap:
                        i = j
                dropped += 1
                i += 1
                continue
        out.append(line)
        i += 1
    return "".join(out), dropped


def unwrap_details(src: str) -> str:
    src = re.sub(r"<details>\s*(?:<summary>[^<]*</summary>\s*)?", "", src)
    src = src.replace("</details>", "")
    return src


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--workdir", default="/tmp/rm-prepare")
    ap.add_argument("--no-mermaid", action="store_true")
    args = ap.parse_args()

    src = Path(args.infile).read_text(encoding="utf-8")
    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    src, nav_removed = clean_navigation(src)
    src, anchors = strip_anchors(src)
    src, mermaid = swap_mermaid(src, workdir, not args.no_mermaid,
                                Path(__file__).parent)
    src, dead_imgs = drop_dead_images(src)
    src = unwrap_details(src)

    Path(args.outfile).write_text(src, encoding="utf-8")
    print(json.dumps({
        "nav_sections_removed": nav_removed,
        "anchors_stripped": anchors,
        "mermaid_rendered": mermaid,
        "dead_images_dropped": dead_imgs,
        "chars": len(src),
    }), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
