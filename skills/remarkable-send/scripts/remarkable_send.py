#!/usr/bin/env python3
"""Send any markdown article to the reMarkable 2 as an e-ink optimized PDF.
Runs on plain python3; markdown/pypdf libs are optional (fallbacks built in).

Takes a markdown file, renders it in the "Grid" design (Liberation Sans +
Mono, 12pt body, 13/15mm page margins, page sized exactly to the rM2 screen),
uploads via rmapi (ddvk fork) into a cloud folder.

Usage:
  remarkable_send.py --file article.md --title "..." --source example.com \
                     [--folder "/Inbox"] [--theme grid|book|compact] [--dry-run]

Themes: grid (default, the "Grid" look), book (Liberation Serif reading
theme, hairline rules, small-caps labels), compact (14px dense long-doc
variant; page margins unchanged).

Navigation:
  - PDF outline (bookmarks) from headings via chrome
    --generate-pdf-document-outline (reMarkable 2 sidebar).
  - "Содержание" TOC page with page numbers + clickable internal links,
    generated via a two-pass render (render -> measure -> re-render).
  - PDF metadata (title/author/subject) via pypdf post-processing.

Env: REMARKABLE_OUTROOT overrides the output root.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

def _resolve_bin(env_var: str, names: list[str]) -> str:
    """env override -> literal path -> any name found on PATH."""
    for cand in [os.environ.get(env_var), *names]:
        if not cand:
            continue
        if Path(cand).exists():
            return cand
        found = shutil.which(cand)
        if found:
            return found
    return names[0]


def find_chrome() -> str:
    """CHROME_BIN env -> google-chrome -> common chromium names."""
    return _resolve_bin("CHROME_BIN",
                        ["google-chrome", "google-chrome-stable",
                         "chromium-browser", "chromium"])


def find_rmapi() -> str:
    """RMAPI_BIN env -> ~/bin/rmapi -> rmapi on PATH."""
    return _resolve_bin("RMAPI_BIN", [str(Path.home() / "bin" / "rmapi"), "rmapi"])


try:
    import markdown  # noqa: F401  (requirements.txt)
except ImportError as _e:
    raise SystemExit(
        "missing dependency: markdown (pip install -r requirements.txt)"
    ) from _e

RMAPI = Path(find_rmapi())
OUTROOT = Path(os.environ.get("REMARKABLE_OUTROOT",
                              Path.home() / "remarkable-out"))

AUTHOR = "Pavel Nasovich"
TOC_MIN_SECTIONS = 4          # add a TOC page when the doc has >= 4 h2 sections
TOC_TITLE = "Содержание"

SANS = "'Liberation Sans', 'DejaVu Sans', Arial, sans-serif"
MONO = "'Liberation Mono', 'DejaVu Sans Mono', monospace"
SERIF = "'Liberation Serif', 'DejaVu Serif', Georgia, serif"

THEMES = ("grid", "book", "compact")

PAGE_CSS = """
<style>
@page { size: 157.7mm 210.3mm; margin: 13mm 13mm 15mm; }
* { box-sizing: border-box; }
body { margin: 0; font-family: %(SANS)s; color: #000;
       font-size: 16px; line-height: 1.55; overflow-wrap: anywhere; }
.bar { border-top: 5px solid #000; margin-bottom: 6px; }
.runhead { display: flex; justify-content: space-between; font-family: %(MONO)s;
  font-size: 10.5px; letter-spacing: .04em; border-bottom: 1px solid #000;
  padding: 2px 0 6px; margin-bottom: 18px; }
h1.title { font-size: 30px; line-height: 1.08; font-weight: 700; margin: 0 0 10px; }
.srcrow { font-family: %(MONO)s; font-size: 11.5px; color: #333; margin: 0 0 6px; }
.srcrow b { color: #000; }
.rule2 { border-top: 2px solid #000; margin: 14px 0 18px; }
h2 { font-size: 24px; line-height: 1.12; font-weight: 700; margin: 26px 0 10px; }
/* digest mode: every section opens its own page (except right after the title) */
body.sec-pages h2 { break-before: page; page-break-before: always; }
body.sec-pages .content > h2:first-child { break-before: auto; page-break-before: auto; }
h3 { font-size: 19px; font-weight: 700; margin: 20px 0 8px; }
h4 { font-size: 16.5px; font-weight: 700; margin: 16px 0 6px; }
/* headings never dangle at a page break without their content,
   and a wrapped heading never splits across pages itself */
h2, h3, h4 { break-after: avoid-page; page-break-after: avoid;
             break-inside: avoid-page; page-break-inside: avoid; }
p { margin: 0 0 12px; }
ul, ol { margin: 0 0 12px; padding-left: 22px; }
li { margin: 0 0 5px; }
a { color: #000; text-decoration: underline; text-underline-offset: 2px; }
strong { font-weight: 700; }
blockquote { margin: 14px 0; border-left: 4px solid #000; padding: 2px 0 2px 12px;
  font-style: italic; color: #222; }
blockquote p { margin: 0 0 8px; }
code { font-family: %(MONO)s; font-size: 14px; background: #f2f2f2; padding: 0 3px; }
pre { font-family: %(MONO)s; font-size: 12.5px; line-height: 1.5; background: #f6f6f6;
  border: 1px solid #000; padding: 10px 12px; margin: 0 0 14px; white-space: pre-wrap;
  break-inside: avoid; page-break-inside: avoid; }
pre code { background: none; padding: 0; font-size: 12.5px; }
table { border-collapse: collapse; width: 100%%; margin: 0 0 14px;
        font-size: 14px; break-inside: avoid; page-break-inside: avoid; }
thead { display: table-header-group; }  /* repeat header on every split page */
th, td { border: 1px solid #000; padding: 6px 9px; text-align: left;
         vertical-align: top; }
th { font-family: %(MONO)s; font-size: 12px; font-weight: 700;
     letter-spacing: .04em; }
hr { border: 0; border-top: 1px solid #000; margin: 16px 0; }
/* e-ink images: preprocessed 1-bit/2-bit halftones sized for the 226dpi panel
   (1170px == full column width), shown full-width, never split across pages */
figure { margin: 12px 0; text-align: center;
         break-inside: avoid; page-break-inside: avoid; }
figure img { display: block; width: 100%; max-width: 100%; height: auto;
             max-height: 140mm;  /* a plate shares its page with heading+text */
             object-fit: contain; margin: 0 auto;
             border: 1px solid #000; }
figcaption { font-family: %(MONO)s; font-size: 10.5px; color: #333;
             letter-spacing: .03em; margin-top: 4px; }
.footnote { font-size: 13px; color: #333; }
/* --- generated TOC ("Содержание") page: Grid style, dotted leaders --- */
.toc { margin: 6px 0 0; break-after: page; page-break-after: always; }
.toc-head { font-size: 24px; font-weight: 700; line-height: 1.12;
  border-bottom: 2px solid #000; padding-bottom: 6px; margin: 0 0 14px; }
.toc ul { list-style: none; margin: 0; padding: 0; }
.toc li { margin: 0 0 9px; }
.toc a { display: flex; align-items: baseline; gap: 7px;
         text-decoration: none; color: #000; }
.toc .t { overflow-wrap: anywhere; }
.toc .dots { flex: 1; border-bottom: 1px dotted #444; min-width: 10px;
             transform: translateY(-4px); }
.toc .num { font-family: %(MONO)s; font-size: 13.5px; min-width: 4ch;
            text-align: right; }
</style>
"""

# Theme overrides append AFTER the base style block: equal-specificity rules
# here win. Layout logic (page size/margins, breaks, keep-together) stays in
# PAGE_CSS and is shared by every theme.
THEME_CSS = {
    "book": """
<style>
/* book: serif reading theme — hairline rules, small-caps labels.
   Left-aligned (never justified): ragged-right reads better on e-ink. */
body { font-family: %(SERIF)s; line-height: 1.6; }
.bar { border-top-width: 1px; margin-bottom: 4px; }  /* slab -> hairline */
.runhead { font-family: %(SERIF)s; font-size: 11.5px;
  font-variant: small-caps; text-transform: lowercase; letter-spacing: .14em; }
.srcrow { font-family: %(SERIF)s; font-style: italic; font-size: 12px; }
h1.title { font-size: 28px; }
.rule2 { border-top-width: 1px; margin: 12px 0 16px; }
/* chapter-style section starts: each h2 opens its page under a thin rule */
h2 { font-size: 24px; border-top: 1px solid #000; padding-top: 16px;
     margin: 0 0 12px; }
.content > h2:first-child { border-top: 0; padding-top: 0; margin-top: 26px; }
h3 { font-size: 19px; font-style: italic; }
p { margin: 0 0 13px; }
li { margin: 0 0 6px; }
blockquote { border-left-width: 2px; }
th { font-family: %(SERIF)s; font-variant: small-caps;
     text-transform: lowercase; letter-spacing: .08em; font-size: 12.5px; }
</style>
""",
    "compact": """
<style>
/* compact: dense long-doc variant — 14px body (~10.5pt), tighter block
   spacing. Page margins stay 13/15mm; h2 section breaks stay. */
body { font-size: 14px; line-height: 1.45; }
.runhead { padding: 1px 0 4px; margin-bottom: 12px; }
h1.title { font-size: 26px; margin: 0 0 8px; }
.rule2 { margin: 10px 0 12px; }
h2 { font-size: 20px; margin: 16px 0 8px; }
h3 { font-size: 16.5px; margin: 14px 0 6px; }
h4 { font-size: 15px; margin: 12px 0 5px; }
p { margin: 0 0 8px; }
ul, ol { margin: 0 0 8px; padding-left: 18px; }
li { margin: 0 0 3px; }
blockquote { margin: 10px 0; }
blockquote p { margin: 0 0 6px; }
code { font-size: 12.5px; }
pre { font-size: 11px; line-height: 1.4; padding: 8px 10px; margin: 0 0 10px; }
pre code { font-size: 11px; }
table { font-size: 12.5px; margin: 0 0 10px; }
th { font-size: 11px; }
th, td { padding: 4px 7px; }
hr { margin: 10px 0; }
.footnote { font-size: 12px; }
</style>
""",
}


def md_to_html(md_text: str) -> str:
    """Full markdown: tables, footnotes, fenced code (the `extra` extension)."""
    import markdown
    return markdown.markdown(md_text, extensions=["extra", "sane_lists"])

def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def slugify(name: str) -> str:
    s = re.sub(r"[–—]+", "-", name)            # dash traps in rmapi name matching
    s = re.sub(r'[<>:"/\\|?*]+', " ", s)
    s = re.sub(r"\s+", " ", s).strip().rstrip(".")
    return s or "Untitled"


def _img_to_figure(body: str) -> str:
    """Wrap <img> in <figure>; non-empty alt becomes a mono figcaption.
    Single-pass alternation regex: never re-wraps an already-wrapped image."""
    import re as _re
    pat = _re.compile(
        r"<img\b[^>]*?\bsrc=\"([^\"]+)\"[^>]*?\balt=\"([^\"]*)\"[^>]*?>"
        r"|<img\b[^>]*?\balt=\"([^\"]*)\"[^>]*?\bsrc=\"([^\"]+)\"[^>]*?>",
        _re.S)

    def wrap(m: _re.Match) -> str:
        src_url, alt1, alt2, src2 = m.groups()
        s, alt = (src_url, alt1) if src_url else (src2, alt2)
        cap = (f"<figcaption>{html.escape(alt)}</figcaption>") if alt.strip() else ""
        return f'<figure><img src="{s}" alt="{html.escape(alt)}">{cap}</figure>'

    return pat.sub(wrap, body)


def strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\u00a0", " ")).strip()


def tag_h2_sections(body: str) -> tuple[str, list[dict]]:
    """Give every <h2> an id="sec-N" (for TOC anchors); return (html, sections)."""
    sections: list[dict] = []
    n = [0]

    def repl(m: re.Match) -> str:
        n[0] += 1
        sid = f"sec-{n[0]}"
        raw = m.group(1)
        title = _norm(html.unescape(strip_tags(raw)))
        sections.append({"id": sid, "title": title})
        return f'<h2 id="{sid}">{raw}</h2>'

    out = re.sub(r"<h2(?:\s[^>]*)?>(.*?)</h2>", repl, body, flags=re.S)
    return out, sections


def build_toc_html(sections: list[dict], pages: list[int | None] | None) -> str:
    """TOC rows: dotted leaders, mono page numbers with fixed min-width so
    placeholder vs. real numbers cannot rewrap (two-pass pagination stable).
    Whole row is <a href="#sec-N">: chrome keeps internal anchors as PDF links."""
    rows = []
    for i, sec in enumerate(sections):
        num = "?" if pages is None else str(pages[i] or 0)
        rows.append(
            f'<li><a href="#{sec["id"]}">'
            f'<span class="t">{i + 1}. {html.escape(sec["title"])}</span>'
            f'<span class="dots"></span>'
            f'<span class="num">{num}</span></a></li>'
        )
    return (f'<div class="toc"><div class="toc-head">{TOC_TITLE}</div>'
            f'<ul>{"".join(rows)}</ul></div>')


def pdftotext_pages(pdf: Path) -> list[str]:
    txt = subprocess.run(["pdftotext", str(pdf), "-"],
                         capture_output=True, text=True).stdout
    return txt.split("\f")


def locate_section_pages(pdf: Path, sections: list[dict],
                         start_page: int = 1) -> list[int | None]:
    """1-based page each h2 starts on. Every h2 opens a fresh page, so its
    title is the FIRST text there; monotonic scan, immune to body mentions."""
    pages = pdftotext_pages(pdf)
    found: list[int | None] = [None] * len(sections)
    cur = start_page
    for i, sec in enumerate(sections):
        for k in range(cur, len(pages) + 1):
            if _norm(pages[k - 1]).startswith(sec["title"]):
                found[i] = k
                cur = k
                break
    return found


def set_pdf_metadata(pdf: Path, title: str, source: str) -> bool:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        print("NOTE: pypdf not available - PDF metadata left as chrome wrote it",
              file=sys.stderr)
        return False
    reader = PdfReader(str(pdf))
    writer = PdfWriter(clone_from=reader)   # clone keeps outline + link annots
    writer.add_metadata({
        "/Title": title,
        "/Author": AUTHOR,
        "/Subject": source,
        "/Creator": "remarkable_send.py (chrome headless print-to-pdf)",
    })
    tmp = pdf.with_suffix(".meta.tmp.pdf")
    with open(tmp, "wb") as f:
        writer.write(f)
    tmp.replace(pdf)
    return True


def build_html(md_text: str, title: str, source: str, theme: str = "grid",
               sections: str = "flow",
               toc_sections: list[dict] | None = None,
               toc_pages: list[int | None] | None = None) -> str:
    if sections not in ("flow", "pages"):
        raise ValueError(f"unknown sections mode: {sections}")
    body_class = f"sec-{sections}"  # capture now: `sections` is reused by TOC code below
    if theme not in THEMES:
        raise ValueError(f"unknown theme: {theme}")
    body = md_to_html(md_text)
    # drop the first H1 if it duplicates the title block
    body = re.sub(r"<h1>.*?</h1>", "", body, count=1, flags=re.S)
    body = _img_to_figure(body)
    body, sections = tag_h2_sections(body)
    # split the lede (everything before the first h2) so the title page
    # carries title + lede + TOC together; nothing dangles on its own page
    h2_at = re.search(r"<h2\b", body)
    lede, body_rest = (body[:h2_at.start()], body[h2_at.start():]) if h2_at else (body, "")
    body = body_rest
    toc_html = ""
    if toc_sections is None and len(sections) >= TOC_MIN_SECTIONS:
        toc_sections = sections
    if toc_sections:
        toc_html = build_toc_html(toc_sections, toc_pages)
    today = dt.date.today().isoformat()
    src = (f'<p class="srcrow">source · <b>{html.escape(source)}</b></p>' if source else "")
    css = PAGE_CSS + THEME_CSS.get(theme, "")
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
{css.replace('%(SANS)s', SANS).replace('%(MONO)s', MONO).replace('%(SERIF)s', SERIF)}
</head><body class="{body_class}">
<div class="bar"></div>
<div class="runhead"><span>REMARKABLE READ</span><span>{today}</span></div>
<h1 class="title">{html.escape(title)}</h1>
{src}
<div class="rule2"></div>
{lede}
{toc_html}
<div class="content">
{body}
</div>
</body></html>"""


def render_pdf(html_src: str, out_pdf: Path) -> None:
    tmp = out_pdf.with_suffix(".html")
    tmp.write_text(html_src, encoding="utf-8")
    r = run([find_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox",
             "--disable-dev-shm-usage", f"--print-to-pdf={out_pdf}",
             "--no-pdf-header-footer", "--generate-pdf-document-outline",
             "--virtual-time-budget=20000", str(tmp)])
    tmp.unlink(missing_ok=True)
    if r.returncode != 0 or not out_pdf.exists() or out_pdf.stat().st_size < 5_000:
        raise SystemExit(f"chrome render failed: rc={r.returncode} {r.stderr[-400:]}")


def page_count(pdf: Path) -> int:
    txt = subprocess.run(["pdftotext", str(pdf), "-"],
                         capture_output=True, text=True).stdout
    return len([p for p in txt.split("\f") if p.strip()])


def upload(pdf: Path, folder: str) -> None:
    run([str(RMAPI), "mkdir", folder])
    r = run([str(RMAPI), "put", "--force", str(pdf), folder])
    if r.returncode != 0:
        raise SystemExit(f"rmapi put failed: {r.stdout[-200:]} {r.stderr[-200:]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="markdown (or plain text) file")
    ap.add_argument("--title", help="document title (default: first # heading)")
    ap.add_argument("--source", default="", help="origin label: domain or URL")
    ap.add_argument("--folder", default="/Inbox",
                    help="reMarkable cloud folder (default: /Inbox)")
    ap.add_argument("--theme", choices=THEMES, default="grid",
                    help="grid: default look; book: serif reading; "
                         "compact: dense for long docs")
    ap.add_argument("--sections", choices=("flow", "pages"), default="flow",
                    help="flow: sections run continuously (articles, default); "
                         "pages: every section opens a fresh page (digests)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    src = Path(args.file)
    if not src.exists():
        print(f"ERROR: no such file: {src}", file=sys.stderr)
        return 1
    md_text = src.read_text(encoding="utf-8")

    display_title = args.title
    if not display_title:
        m = re.match(r"\s*#\s+(.+)", md_text)
        display_title = m.group(1).strip() if m else src.stem
    title = slugify(display_title)

    OUTROOT.mkdir(parents=True, exist_ok=True)
    out_dir = OUTROOT / dt.date.today().strftime("%Y-%m")
    out_dir.mkdir(exist_ok=True)
    pdf = out_dir / f"{title} - {dt.date.today().isoformat()}.pdf"

    # pass 0 (cheap): decide whether a TOC page is needed
    _, sections = tag_h2_sections(
        re.sub(r"<h1>.*?</h1>", "", md_to_html(md_text), count=1, flags=re.S))
    if len(sections) >= TOC_MIN_SECTIONS:
        # two-pass render: placeholder TOC keeps pagination identical
        # (fixed-width .num), measure real section pages, re-render, verify
        pages: list[int | None] | None = None
        for attempt in range(5):
            html_src = build_html(md_text, title, args.source, args.theme, args.sections,
                                  toc_sections=sections, toc_pages=pages)
            render_pdf(html_src, pdf)
            measured = locate_section_pages(pdf, sections, start_page=2)
            if pages == measured:
                break
            pages = measured
        print(f"TOC: {len(sections)} sections -> pages {[p for p in (pages or [])]}")
    else:
        html_src = build_html(md_text, title, args.source, args.theme, args.sections)
        render_pdf(html_src, pdf)

    n = page_count(pdf)
    print(f"RENDERED: {pdf} ({n} pages)")
    if set_pdf_metadata(pdf, display_title, args.source):
        print(f"METADATA: title={display_title!r} author={AUTHOR!r} "
              f"subject={args.source!r}")

    if args.dry_run:
        return 0

    conf = next((p for p in (
        Path.home() / ".config" / "rmapi" / "rmapi.conf",  # ddvk fork
        Path.home() / ".rmapi.conf",                        # upstream layout
    ) if p.exists()), None)
    if not conf:
        print("RMAPI_NOT_AUTHENTICATED", file=sys.stderr)
        return 2
    upload(pdf, args.folder)
    print(f"UPLOADED: {args.folder}/{pdf.name} ({n} pages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
