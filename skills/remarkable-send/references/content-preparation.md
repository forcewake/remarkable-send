# Content preparation (input to remarkable-send)

The engine typesets what you give it. Clean markdown in → readable PDF out.
Garbage in → readable garbage.

## Structure

```markdown
# Title (concise, human; the engine reuses it as the document title)

Optional 2–4 sentence lead paragraph — who wrote it, why it matters.

## Section        ← every ## starts a fresh page on the tablet

Body text...

### Subsection    ← flows inline, no page break
```

- `##` = chapter (new page), `###`/`####` = subheads. If the article opens
  with a section heading directly after the title, it stays on the title page
  (engine CSS handles this).
- Keep the author's wording. You are typesetting, not summarizing — unless
  the user explicitly asked for a summary; then say so in the title or lead.
- Language: keep the source language (RU articles stay RU, EN stay EN).

## What to strip (web extraction)

Navigation, cookie/consent banners, related-posts blocks, social share rows,
author bios, newsletter CTAs, comment threads, "read more" pagination links,
timestamp clusters, image captions *for decorative images*. Keep substantive
figures/tables (tables render natively; images are hidden on e-ink anyway).

## What survives the design

| Markdown | Tablet rendering |
|---|---|
| `**bold**`, `*italic*` | as-is, 12pt body |
| Fenced code blocks | mono, boxed, never split across pages |
| Inline `code` | mono with light background |
| Tables | bordered grid, mono header — keep tables narrow (≤4 cols reads best) |
| `> quotes` | black left bar, italic |
| Links | underlined; full URLs also fine as plain text |
| `---` | thin rule |
| Images | supported AFTER `preprocess_images.py`: grayscale + 1-bit Floyd–Steinberg halftone at device resolution (1170px column width), bordered figure + mono caption from alt text, never split across pages. Prefer stable thumbnails (`commons.wikimedia.org/wiki/Special:FilePath/<name>?width=1400`); raw URLs and SVGs are not processed. Keep alt texts — they become captions |

## Titles and sources

- `--title`: override only when the page `<h1>` is junk ("Untitled", SEO slop).
- `--source`: origin domain (`example.com`) or label ("Pavel's notes",
  "arXiv 2609.04098"). Shown in mono under the title.
- Bad titles: clickbait verbatim, ALL CAPS, >90 chars. Rewrite to substance.

## Sizing intuition

One page ≈ 340 words / ≈ 30 lines of body. A 2 000-word article ≈ 6–7 pages.
No practical length limit; sections chunk it for e-ink flipping.
