#!/usr/bin/env python3
"""Extract plain markdown-ish text from document files for remarkable-send.

stdlib-only. Formats:
  .docx  -> word/document.xml <w:t> runs, paragraphs preserved, headings kept as ## lines
  .epub  -> spine xhtml documents, tags stripped, chapters as ## headings
  .pdf   -> pdftotext (poppler), form feeds to headings heuristics off: raw text
  .md/.txt/.markdown -> passthrough

Usage: extract_document.py INPUT [OUTPUT]   (stdout if no OUTPUT)
Exit 0 + JSON status line on stderr.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path


class _XhtmlToText(HTMLParser):
    BLOCK = {"p", "div", "li", "blockquote", "tr", "section", "article"}
    SKIP = {"script", "style", "head", "title"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and not self._skip:
            self.out.append("\n\n" + "#" * int(tag[1]) + " ")
        elif tag in self.BLOCK and not self._skip:
            self.out.append("\n\n")
        elif tag == "li" and not self._skip:
            self.out.append("\n- ")
        elif tag == "br" and not self._skip:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.out.append(data)

    def text(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self.out)).strip()


def from_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    paras = []
    # paragraphs with their style; map Heading N styles to markdown headings
    for pm in re.finditer(r"<w:p[ >].*?</w:p>", xml, re.S):
        p = pm.group(0)
        style = re.search(r'w:pStyle w:val="([^"]+)"', p)
        texts = re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)
        text = "".join(texts).strip()
        if not text:
            continue
        s = style.group(1) if style else ""
        m = re.match(r"[Hh]eading(\d)", s)
        if m:
            paras.append("#" * min(int(m.group(1)) + 1, 4) + " " + text)
        elif s.lower() in ("title",):
            paras.append("# " + text)
        elif re.match(r"ListParagraph", s):
            paras.append("- " + text)
        else:
            paras.append(text)
    return "\n\n".join(paras)


def from_epub(path: Path) -> str:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        opf = next((n for n in names if n.endswith(".opf")), None)
        if opf is None:
            raise SystemExit("epub: no .opf found")
        base = str(Path(opf).parent)
        opf_xml = z.read(opf).decode("utf-8", "replace")
        manifest = dict(re.findall(
            r'<item[^>]*id="([^"]+)"[^>]*href="([^"]+)"', opf_xml))
        manifest.update(dict(re.findall(
            r'<item[^>]*href="([^"]+)"[^>]*id="([^"]+)"', opf_xml)[::-1]))
        spine = re.findall(r'<itemref[^>]*idref="([^"]+)"', opf_xml)
        parts = []
        for ref in spine:
            href = manifest.get(ref)
            if not href or not href.endswith((".xhtml", ".html", ".htm")):
                continue
            full = f"{base}/{href}" if base else href
            if full not in names:
                full = href
            parser = _XhtmlToText()
            parser.feed(z.read(full).decode("utf-8", "replace"))
            t = parser.text()
            if t:
                parts.append(t)
    return "\n\n".join(parts)


def from_pdf(path: Path) -> str:
    r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"pdftotext failed: {r.stderr[-200:]}")
    return r.stdout.strip()


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"no such file: {src}", file=sys.stderr)
        return 1
    ext = src.suffix.lower()
    if ext == ".docx":
        text, fmt = from_docx(src), "docx"
    elif ext == ".epub":
        text, fmt = from_epub(src), "epub"
    elif ext == ".pdf":
        text, fmt = from_pdf(src), "pdf"
    elif ext in (".md", ".markdown", ".txt", ""):
        text = src.read_text(encoding="utf-8", errors="replace")
        fmt = ext.strip(".") or "txt"
    else:
        print(f"unsupported format: {ext}", file=sys.stderr)
        return 1
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    payload = text.encode("utf-8")
    if out:
        out.write_bytes(payload)
    else:
        sys.stdout.buffer.write(payload)
    print(json.dumps({"format": fmt, "chars": len(text),
                      "out": str(out) if out else "stdout"}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
