#!/usr/bin/env python3
"""Cut a few review pages from a rendered PDF as PNGs (drop-zone review step).

Picks: title page, contents/first-content page, a dense middle page, the
last page (dedup). Prints a JSON list of PNG paths for the agent to send
into the chat.

Usage: preview_pages.py PDF --outdir DIR [--n 4] [--dpi 110]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def page_texts(pdf: str) -> list[str]:
    txt = subprocess.run(["pdftotext", pdf, "-"],
                         capture_output=True, text=True).stdout
    return txt.split("\f")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--dpi", type=int, default=110)
    args = ap.parse_args()

    pages = [p for p in page_texts(args.pdf) if p.strip()]
    n = len(pages)
    if n == 0:
        print("no pages", file=sys.stderr)
        return 1
    words = [len(re.findall(r"\S+", p)) for p in pages]
    picks = {1}
    if n >= 2:
        picks.add(2)
    dense_mid = max(range(1, n + 1), key=lambda i: words[i - 1])
    picks.add(dense_mid)
    picks.add(n)
    # fill up to --n with dense pages not yet picked
    for i in sorted(range(1, n + 1), key=lambda i: -words[i - 1]):
        if len(picks) >= args.n:
            break
        picks.add(i)
    picks = sorted(picks)[: max(args.n, 1)]

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    outs = []
    for p in picks:
        dst = outdir / f"review-{p:02d}.png"
        r = subprocess.run(["pdftoppm", "-png", "-r", str(args.dpi),
                            "-f", str(p), "-l", str(p),
                            args.pdf, str(dst.with_suffix(""))],
                           capture_output=True)
        made = sorted(outdir.glob(f"review-{p:02d}-*.png"))
        if made:
            made[0].rename(dst)
            outs.append(str(dst))
    print(json.dumps({"pages": n, "previews": outs}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
