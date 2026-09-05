# Design system ("Grid" for reMarkable 2)

The engine (`scripts/remarkable_send.py`) embeds this system; edit
`PAGE_CSS` there and re-run — no other knobs.

## Page geometry

| Parameter | Value | Why |
|---|---|---|
| Page size | 157.7 × 210.3 mm | exactly the rM2 screen (1404×1872 px @ 226 dpi) — fullscreen, no device zoom |
| Margins | 13 mm top/sides, 15 mm bottom | thumb room, pen rest; 12pt e-ink reading comfort |
| Body | 16 CSS px = exactly 12 pt | community threshold: <12pt is hard to read on rM2 |
| Line height | 1.55 | e-ink clarity |
| Column | single | rM PDFs don't reflow; single column avoids pinch-zoom |

Line length lands ≈ 60–65 characters — the classic comfortable range.

Margins MUST live in `@page { margin: ... }`, never `body` padding: body
padding applies only to the first/last page of a print run.

## Typography (Liberation family)

- Sans (`Liberation Sans`) for body and headings; Mono (`Liberation Mono`)
  for metadata, code, table headers, sources.
- Title 30px bold; `##` 24px (page-breaking), `###` 19px, `####` 16.5px.
- Pure black on white. E-ink is grayscale: no color coding, no large dark
  fills (ghosting), light-gray backgrounds only for code (`#f6f6f6`).

## Grid elements

- **Bar**: 5px solid black top rule on every page — the design's signature.
- **Runhead**: mono caps line under the bar (`REMARKABLE READ · date`).
- **Source row**: mono `source · <b>domain</b>` under the title.
- **Double rule**: 2px black below the header block.
- **Quote**: 4px black left bar + italic.
- **Code/table**: boxed 1px black; `break-inside: avoid` so they never split.

## Themes (`--theme`)

Layout rules (page size, margins, h2 page breaks, keep-together) are shared;
a theme only appends a CSS override block (`THEME_CSS` in the engine):

- **grid** (default) — the system described above.
- **book** — Liberation Serif 16px/1.6, bar becomes a hairline, runhead and
  table headers become small caps, h2 opens its page under a thin rule
  (chapter feel). For essays and long reads.
- **compact** — body 14px/1.45, tighter block spacing, pre 11px; page
  margins and section breaks unchanged. ~15–20% more words per page.

## Images on e-ink

Preprocessor (`scripts/preprocess_images.py`, PIL): fetch (15s timeout,
429 backoff) → EXIF-orient → grayscale → autocontrast → fit ≤1170×1500 →
dither. Modes: **fs1** (1-bit Floyd–Steinberg, default — max contrast,
newspaper halftone, zero dependence on the viewer's gray rendering) and
**gray4** (4-level FS, finest tones for photo-heavy docs). Plain grayscale
must NOT ship: the panel quantizes it uncontrolled and PDFs balloon 8×.
Engine renders images as bordered figures with mono captions
(`break-inside: avoid`), embedded at 225–226ppi = 1:1 device pixels.
Figure height caps at **140mm** (~2/3 page): a plate shares its page with
the section heading and text — magazine-inline feel. Taller caps push the
image to a page of its own and orphan the heading (that was tried and
reverted).

## Navigation (automatic)

- PDF outline (bookmarks) via chrome `--generate-pdf-document-outline` —
  shows in the tablet's sidebar; generated from headings.
- `Содержание` TOC page when the doc has ≥4 `##` sections: dotted leaders,
  mono page numbers, whole row is an internal link (chrome preserves
  `#sec-N` anchors as PDF GoTo links). Built by a two-pass render: render
  with placeholder numbers → locate each section's real page (its title is
  the first text on the page) → re-render → verify.
- Metadata (Title/Author/Subject) via pypdf post-processing
  (`~/.hermes/hermes-agent/venv` has pypdf; script degrades gracefully).

## If Pavel asks for tweaks

| Ask | Change in PAGE_CSS |
|---|---|
| bigger text | `body { font-size: 17-18px }` (12.75–13.5pt) |
| wider/narrower margins | `@page { margin: ... }` (+ mirror in the daily-intelligence script if the digest should match) |
| denser pages | `body { line-height: 1.45 }` |
| serif flavor | swap `SANS` stack for `'Liberation Serif'` |

The Daily Intelligence digest (`~/.hermes/scripts/daily_intelligence_remarkable.py`)
uses the same system — keep the two in sync when changing fundamentals.
