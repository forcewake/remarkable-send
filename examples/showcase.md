# The e-ink Reading Pipeline

A tour of what remarkable-send does to a plain markdown file before it lands
on a reMarkable tablet. Every feature below is exercised by this document.

## Typography tuned for the panel

The page is exactly 157.7 × 210.3 mm — the reMarkable 2 screen at 226 dpi,
edge to edge. Body text is a true 12 pt at 16 CSS px; margins are 13 mm
sides and top, 15 mm at the bottom for the thumb. Nothing needs pinching,
zooming or panning: one PDF page is one screen.

1. Pages sized 1:1 to the device — no fit-to-width scaling
2. 12 pt body with 1.55 leading — the e-ink legibility floor
3. Single column, ~65 characters per line
4. Pure black on white; no fills that ghost on partial refresh

## Portraits in newspaper halftone

![Ada Lovelace, portrait](https://commons.wikimedia.org/wiki/Special:FilePath/Ada_Lovelace_portrait.jpg?width=1200)

Photos never ship raw: they are converted to grayscale, auto-contrasted and
dithered with 1-bit Floyd–Steinberg at device resolution — newspaper plates,
not blurry gray mush.

## One more plate

![Albert Einstein, 1921](https://commons.wikimedia.org/wiki/Special:FilePath/Albert_Einstein_Head.jpg?width=1400)

A figure shares its page with the heading and text: the plate is capped at
two thirds of page height, so sections read like magazine spreads.

## Navigation is automatic

Every render gets a PDF outline for the tablet's sidebar and real metadata.
Documents with four or more sections — like this one — get a clickable
table of contents with measured page numbers: render once, find where each
section really landed, render again.

## Ship it

```
remarkable_send.py --file showcase.md --source github.com/forcewake
```

That is the whole pipeline: markdown in, a folder on the tablet out.
