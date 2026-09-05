---
name: remarkable-send
description: "Send articles and documents to the reMarkable tablet."
version: 1.2.0
author: Pavel Nasovich (forcewake)
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [remarkable, e-ink, pdf, reading, typography, rmapi]
    category: productivity
    related_skills: [pdf]
---

# Remarkable Send Skill

Typeset any article, document or text as an e-ink optimized PDF and deliver it
to a reMarkable tablet (cloud sync, lands in a folder within ~a minute).
Renders in the house "Grid" design: 12pt body, real page margins, pages sized
1:1 to the device screen. Content arrives as clean markdown; the bundled
engine does the layout and upload. It does not read the tablet, send images
unprocessed, or manage files already on the device beyond its own folder.

## When to Use

- The user asks to read something on the tablet: "send this to my reMarkable",
  "push this article to the tablet".
- A long article / paper / report / changelog / doc would benefit from
  distraction-free reading away from the screen.

## Prerequisites

- `google-chrome` / `chromium` on PATH (headless print), poppler `pdftotext`.
- `rmapi` (the [ddvk fork](https://github.com/ddvk/rmapi) v0.0.35+ — the
  original juruen build is dead), authenticated. The engine finds it via
  `RMAPI_BIN` env, `~/bin/rmapi`, or PATH.
- Python 3.10+ with `pip install -r requirements.txt`
  (`markdown` for tables/footnotes, `pypdf` for metadata, `pillow` for
  image preprocessing).

## How to Run

```bash
# 1. save prepared markdown (see Procedure) to a temp file
# 2. render + upload:
${HERMES_SKILL_DIR}/scripts/remarkable_send.py \
  --file /tmp/article.md \
  --source example.com \
  --folder "/Inbox"          # optional; default /Inbox
  --theme grid               # grid (default) | book | compact
# add --dry-run to render without uploading
```

Images ARE supported on e-ink — but must be preprocessed into crisp
halftones (never send raw photos). When the markdown contains image refs,
run the preprocessor first (fetch → grayscale → 1-bit Floyd–Steinberg
dither at device resolution):

```bash
python3 ${HERMES_SKILL_DIR}/scripts/preprocess_images.py \
  /tmp/article.md --workdir /tmp/imgwork --out /tmp/article.eink.md
```
then send `article.eink.md`. Failed fetches degrade to italic captions.
`--mode gray4` for photo-heavy docs (finer tones).

Navigation is automatic: every PDF gets sidebar bookmarks (outline) and
metadata (title/author/source); documents with ≥4 `##` sections also get a
clickable "Contents" page with real page numbers (two-pass render).

Queue management (optional): `scripts/remarkable_manage.py list --json`,
`usage`, `plan-archive --older-than 7d [--execute]` (dry-run by default).

## Quick Reference

| Need | Do |
|---|---|
| Article from URL | `web_extract` → save markdown → send with `--source <domain>` |
| User's pasted text | Save as markdown verbatim (user's language) → send |
| Long read (essay/book) | `--theme book` |
| Huge manual / API doc | `--theme compact` |
| Chaptered long doc | Contents page appears automatically at ≥4 `##` sections |
| Article with images | `preprocess_images.py` first, then send the `.eink.md` |
| Queue status | `scripts/remarkable_manage.py list --json --folder "/Inbox"` |
| Re-send same doc | Same title → overwritten on device (`--force` inside) |

## Procedure

1. **Prepare content** per `references/content-preparation.md`: extract main
   text (or take user text), strip boilerplate, keep the author's wording.
   Lead with `# Title`. Save under a temp dir.
2. **Send** with the engine (How to Run). One document per call; for a batch,
   call per item into the same folder.
3. **Report** the engine's `UPLOADED: <folder>/<name> (N pages)` line to the
   user. Local copies land under `~/remarkable-out/YYYY-MM/`.

Layout and page geometry: `references/design-system.md`. Cloud/auth behavior
and rate limits: `references/rmapi-operations.md`. A complete annotated
sample input: `references/example-input.md`.

## Pitfalls

- **Titles with em-dash "—"**: the engine slugifies to plain hyphen — keep it
  that way; rmapi name matching breaks on em-dash (duplicates on re-send).
- **429 from rmapi**: reMarkable cloud rate-limits bursts — wait 60 s, retry
  once; never hammer in a loop.
- `RMAPI_NOT_AUTHENTICATED`: the tablet link needs a one-time code
  (my.remarkable.com/device/browser/connect, then
  `echo CODE | rmapi ls /` — an online command triggers the login flow).
- **Images**: e-ink shows no color — always preprocess; don't compensate with
  image descriptions unless the user asks.
- **Very long unstructured text** renders as a wall: split into `##` sections
  — each starts a fresh page on the tablet.
- Chrome render failure usually means unclosed markdown fences — fix and retry.

## Verification

- Engine prints `RENDERED ... (N pages)` then `UPLOADED ...` — both must appear.
- Confirm landing: `rmapi ls "/Inbox"` shows the file.
- When in doubt re-run with `--dry-run` and compare page counts.
