# A Field Guide to E-Ink Typography

Sample for `--theme book`: Liberation Serif at 1.6 leading, hairline rules,
small-caps labels. The original showcase document rendered as a typeset
paperback.

## On reading longform

The serif theme is for anything you will read for an hour rather than
annotate: essays, interviews, book chapters.

## On chapters

Every section opens its own page under a thin rule, the way a proper book
does. Drop caps were tried and rejected: on a 16-gray panel restraint wins.

## On the compact theme

For manuals and API references there is a third theme — 14 pt body, tighter
leading, the same chrome. It packs roughly a fifth more words per page for
the times a document must fit the flight, not the desk.

---

Rendered: `remarkable_send.py --file theme-book.md --theme book`.
