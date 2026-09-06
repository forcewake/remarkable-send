---
name: remarkable-send
description: "Send articles and documents to the reMarkable tablet."
version: 1.0.0
author: Pavel Nasovich (forcewake) & Hermes Agent
license: MIT
platforms: [linux]
created_by: agent
metadata:
  hermes:
    tags: [remarkable, e-ink, pdf, reading, typography, rmapi]
    category: productivity
    related_skills: [pdf]
---

# Remarkable Send Skill

Typeset any article, document or text as an e-ink optimized PDF and deliver it
to Pavel's reMarkable 2 tablet (cloud sync, lands in a folder within ~a
minute). Renders in the house "Grid" design: 12pt body, real page margins,
pages sized 1:1 to the device screen. Content arrives as clean markdown; the
bundled engine does the layout and upload. It does not read the tablet, send
images, or manage files already on the device beyond its own folder.

## When to Use

- The user asks to read something on the tablet: "отправь на римарк",
  "скинь на remarkable", "push this to my tablet".
- A long article / paper / report / changelog / doc would benefit from
  distraction-free reading away from the screen.
- NOT for the Daily Intelligence digest — that pipeline uploads itself
  (`~/.hermes/scripts/daily_intelligence_remarkable.py`).

## Prerequisites

Host-bound to deerflow-vm (linux): `google-chrome` (headless print),
`~/bin/rmapi` (ddvk/rmapi v0.0.35+), poppler `pdftotext`. Tablet link is
already authenticated (`~/.config/rmapi/rmapi.conf`). The engine runs on the
hermes venv python or plain python3 — the `markdown` lib is optional
(fallback renderer built in).

## How to Run

```bash
# 1. save prepared markdown (see Procedure) to a temp file
# 2. render + upload:
${HERMES_SKILL_DIR}/scripts/remarkable_send.py \
  --file /tmp/rm-send/article.md \
  --source example.com \
  --folder "/Inbox"          # optional; default /Inbox
  --theme grid               # grid (default) | book | compact
# add --dry-run to render without uploading
```

Themes: **grid** — the house look, scans/reference docs; **book** — serif,
hairline rules, for long reading (essays, interviews, chapters);
**compact** — 14px dense, for manuals/API docs that must fit fewer pages.

Images ARE supported on e-ink — but must be preprocessed into crisp
halftones (never send raw photos). When the markdown contains image refs,
run the preprocessor first (fetch → grayscale → 1-bit Floyd–Steinberg
dither at device resolution):

```bash
~/.hermes/hermes-agent/venv/bin/python3 \
  ${HERMES_SKILL_DIR}/scripts/preprocess_images.py /tmp/rm-send/article.md \
  --workdir /tmp/rm-send/imgwork --out /tmp/rm-send/article.eink.md
```
then send `article.eink.md`. Failed fetches degrade to italic captions.
`--mode gray4` for photo-heavy docs (finer tones).

Navigation is automatic: every PDF gets sidebar bookmarks (outline) and
metadata (title/author/source); documents with ≥4 `##` sections also get a
clickable "Содержание" page with real page numbers (two-pass render).

## Quick Reference

| Need | Do |
|---|---|
| Article from URL | `web_extract` → save markdown → send with `--source <domain>` |
| File upload (docx/epub/pdf) | `scripts/extract_document.py file.docx out.md` → send `out.md` |
| User's pasted text | Save as markdown verbatim (user's language) → send |
| Reading queue | `--folder "/Inbox"` (default) |
| Existing folder | `--folder "/EPAM"`, `"/Research"`, `"/Books"` — created if missing |
| Verify delivery | `terminal`: `~/bin/rmapi ls "<folder>"` |
| Re-send same doc | Same title → overwritten on device (`--force` inside) |
| Long read (essay/book) | `--theme book` |
| Huge manual / API doc | `--theme compact` |
| Chaptered long doc | TOC page appears automatically at ≥4 `##` sections |
| Article with images | preprocess_images.py first (see above), then send the `.eink.md` |
| Queue status | `terminal`: `${HERMES_SKILL_DIR}/scripts/remarkable_manage.py list --json --folder "/Inbox"` |
| Tablet overview | `remarkable_manage.py usage` |
| Review read items | `remarkable_manage.py plan-archive --older-than 7d` (dry-run by default, shows exact rmapi commands) |
| Archive read items | same + `--execute` (creates `/Read` first); add `--trust-name-dates` for Daily Intelligence (its mtimes refresh daily) |

## Procedure

1. **Prepare content** per `references/content-preparation.md`: extract main
   text with `web_extract` (or take user text), strip boilerplate, keep the
   author's wording. Lead with `# Title`. Save under `/tmp/rm-send/`.
   Document files convert first:
   `scripts/extract_document.py upload.docx /tmp/rm-send/upload.md`
   (docx/epub/pdf → markdown; stdlib-only, headings and lists preserved).
2. **Send** with the engine (How to Run). One document per call; for a batch,
   call per item into the same folder.
3. **Report** the engine's `UPLOADED: <folder>/<name> (N pages)` line to the
   user. Optionally show the local copy path (kept under
   `~/workspaces/remarkable-out/YYYY-MM/`). Clean up `/tmp/rm-send/`.

For layout changes, page geometry and the design system see
`references/design-system.md`. For cloud/auth behavior, rate limits and
file-naming traps see `references/rmapi-operations.md`. A complete sample
input lives at `references/example-input.md`.

## Pitfalls

- **Titles with em-dash "—"**: the engine slugifies to plain hyphen — keep it
  that way; rmapi name matching breaks on em-dash (duplicates on re-send).
- **429 from rmapi**: reMarkable cloud rate-limits bursts — wait 60 s, retry
  once; never hammer in a loop.
- **`put --force` can still duplicate** when the tree cache lags after rapid
  re-sends: check with `remarkable_manage.py list` (flags `[duplicate]`),
  remove extras with `rm`, `refresh`, re-put once.
- `RMAPI_NOT_AUTHENTICATED`: tell Pavel the tablet link needs a one-time code
  (my.remarkable.com/device/browser/connect); do not attempt to fix auth.
- **Images**: e-ink shows none — the engine hides them; don't compensate with
  image descriptions unless the user asks.
- **Very long unstructured text** renders as a wall: split into `##` sections
  — each starts a fresh page on the tablet.
- Chrome render failure usually means unclosed markdown fences — fix and retry.

## Verification

- Engine prints `RENDERED ... (N pages)` then `UPLOADED ...` — both must appear.
- Confirm landing: `terminal` → `~/bin/rmapi ls "/Inbox"` shows the file.
- Local copy exists under `~/workspaces/remarkable-out/YYYY-MM/`; when in
  doubt, `read_file` it (binary PDF — check size instead) or re-run with
  `--dry-run` to compare page counts.
