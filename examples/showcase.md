# The E-Ink Reading Pipeline

How plain markdown becomes a document worth putting down your phone for —
a tour of every stage, from typography arithmetic to halftone plates,
exercised by this very document.

> The reMarkable is the best reading surface in the house and the worst
> place to render for. Both facts are about the same screen.

## Typography tuned to the panel

Every page is exactly 157.7 × 210.3 mm — the reMarkable 2 display at
226 dpi, edge to edge. No fit-to-width scaling, no zoom, no letterboxing:
one PDF page is one screen, forever.

The body is a true 12 pt at 16 CSS px, which sounds trivial until you
measure what most "send to e-reader" pipelines produce — usually 9–10 pt
letterboxed corpses. Margins are 13 mm at the sides and top, 15 mm at the
bottom for the thumb. A line settles at ~65 characters: the middle of the
classical comfortable range.

| Decision | Value | Why |
|:---------|:------|:----|
| Page size | 157.7 × 210.3 mm | exactly the panel — zero device scaling |
| Body | 16 px = 12 pt | the e-ink legibility floor |
| Leading | 1.55 | e-ink needs air between lines |
| Margins | 13 / 15 mm | thumb room, pen rest |
| Column | single, ~65 chars | PDFs don't reflow |

## Plates, not pictures

![Ada Lovelace, portrait](https://commons.wikimedia.org/wiki/Special:FilePath/Ada_Lovelace_portrait.jpg?width=1200)

Photographs never ship raw. Each one is fetched, EXIF-oriented, converted
to grayscale, auto-contrasted, and dithered with 1-bit Floyd–Steinberg at
the panel's own pixel density — 225 ppi, one dither dot per device pixel.
The result reads like a newspaper plate instead of blurry gray mud.

## A second plate

![Albert Einstein, 1921](https://commons.wikimedia.org/wiki/Special:FilePath/Albert_Einstein_Head.jpg?width=1400)

A figure shares its page with its heading and text: plates are capped at
two thirds of page height, so sections read like magazine spreads instead
of orphaned image dumps. Captions come from the alt text, set in mono.

## Navigation as a first-class feature

Every render ships with a sidebar outline for the tablet's UI and correct
PDF metadata. Documents with four or more sections — this one qualifies —
get a clickable table of contents whose page numbers are *measured from
the rendered PDF*: render once, find where each section really landed,
render again with the truth. Pagination is a fact, not a hope.

## Code and structure survive

Sections open their own pages. Code blocks are boxed in mono and never
tear across a page break; tables repeat their headers on continuation
pages; headings never dangle at the bottom of a page without their
content.

```python
# the actual pipeline, compressed to its essence
html = grid_css(markdown(article))          # typography + themes
pdf = chrome(headless).print(html)          # pages exactly 446.88 × 595.92 pt
pages = measure(pdf)                        # where did sections really land?
pdf = chrome(headless).print(toc(html, pages))  # contents with real numbers
ship(rmapi.upload(pdf, "/Inbox"))           # cloud → tablet in ~a minute
```

## Themes for the occasion

Three type systems share the same layout engine: `grid` for technical
briefs (this document), `book` — serif, hairline rules, chapter openings —
for essays you'll read for an hour, and `compact` at 14 pt for manuals
that must fit the flight, not the desk.

## Ship it

```
remarkable_send.py --file showcase.md --source github.com/forcewake
```

Markdown in. A folder on the tablet out. That is the whole pipeline.
