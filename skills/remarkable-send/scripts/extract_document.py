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


class _HtmlToMd(HTMLParser):
    """Semantic HTML -> markdown; decodes data: images to files; drops
    mermaid source blocks (documents embedding rendered diagram PNGs);
    skips chrome (header/footer/nav/dialog/script/style)."""

    SKIP = {"script", "style", "head", "title", "header", "footer", "nav",
            "dialog"}
    BLOCK = {"p", "div", "section", "article", "main", "blockquote", "tr",
             "figure"}

    def __init__(self, workdir: Path):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self._skip = 0
        self._skip_mermaid = 0
        self._pre = None  # (lang or None, [lines])
        self._in_code = 0
        self._a_href = None
        self._a_buf: list[str] = []
        self._summary_muted = False
        self.workdir = workdir
        self.imgs = 0

    def _emit(self, s: str) -> None:
        if self._skip or self._skip_mermaid or self._pre is not None:
            return
        self.out.append(s)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self._skip += 1
            return
        if tag == "pre":
            cls = a.get("class", "")
            lang = None
            for tok in cls.split():
                if tok.startswith("language-"):
                    lang = tok.removeprefix("language-")
            self._pre = [lang, []]
            return
        if self._pre is not None:
            if tag in ("code", "br"):
                return
            return
        if tag == "code":
            if not self._in_code:
                self._emit("`")
            self._in_code += 1
            return
        if tag == "strong" or tag == "b":
            self._emit("**")
        elif tag == "em" or tag == "i":
            self._emit("*")
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._emit("\n\n" + "#" * min(int(tag[1]) + 0, 6) + " ")
        elif tag in self.BLOCK:
            self._emit("\n\n")
        elif tag == "li":
            self._emit("\n- ")
        elif tag == "br":
            self._emit("\n")
        elif tag == "hr":
            self._emit("\n\n---\n\n")
        elif tag == "img":
            src_url = a.get("src", "")
            alt = a.get("alt", "")
            if src_url.startswith("data:image/"):
                ext = "png" if "png" in src_url[:30] else "jpg"
                self.imgs += 1
                b64 = src_url.split(",", 1)[1]
                import base64
                f = self.workdir / f"html-img-{self.imgs:02d}.{ext}"
                self.workdir.mkdir(parents=True, exist_ok=True)
                f.write_bytes(base64.b64decode(b64))
                self._emit(f"\n\n![{alt}](<{f}>)\n\n")
            elif src_url.startswith("http"):
                self._emit(f"\n\n![{alt}]({src_url})\n\n")
            # local missing refs: dropped silently (prepare handles too)
        elif tag == "summary":
            self._summary_muted = True
        elif tag == "a":
            href = a.get("href", "")
            if href.startswith("http"):
                self._a_href = href
                self._a_buf = []

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if tag == "pre" and self._pre is not None:
            lang, lines = self._pre
            body = "\n".join(lines)
            if lang == "mermaid":
                pass  # rendered PNG is embedded next to it; source is noise
            else:
                self.out.append(f"\n\n```{lang or ''}\n{body}\n```\n\n")
            self._pre = None
            return
        if self._pre is not None:
            if tag == "code":
                pass
            return
        if tag == "summary":
            self._summary_muted = False
            return
        if tag == "code":
            self._in_code = max(0, self._in_code - 1)
            if not self._in_code:
                self._emit("`")
            return
        if tag in ("strong", "b"):
            self._emit("**")
        elif tag in ("em", "i"):
            self._emit("*")
        elif tag == "a" and self._a_href is not None:
            text = "".join(self._a_buf).strip()
            if text and not text.startswith("["):
                self._emit(f"[{text}]({self._a_href})")
            self._a_href = None
            self._a_buf = []

    def handle_data(self, data):
        if self._skip or self._summary_muted:
            return
        if self._pre is not None:
            self._pre[1].append(data)
            return
        if self._a_href is not None:
            self._a_buf.append(data)
            return
        self._emit(data)

    def markdown(self) -> str:
        return re.sub(r"\n{3,}", "\n\n", "".join(self.out)).strip()


def from_html(path: Path, workdir: Path) -> str:
    p = _HtmlToMd(workdir)
    p.feed(path.read_text(encoding="utf-8", errors="replace"))
    return p.markdown()


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
    if ext in (".html", ".htm"):
        text, fmt = from_html(src, Path("/tmp/rm-extract-html")), "html"
    elif ext == ".docx":
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
