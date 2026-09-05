# A Field Guide to E-Ink Typography

Four short chapters on setting text for a 16-gray panel, rendered with
`--theme book --sections pages`: Liberation Serif at 1.6 leading, hairline
rules, chapters that open their own page.

## On reading longform

The serif theme exists for the documents you will read for an hour rather
than annotate: essays, interviews, book chapters, long retrospectives. Its
body is set in Liberation Serif at sixteen pixels with one-point-six
leading, which sounds like an arbitrary pair of numbers until you hold the
tablet. Serif letterforms give the eye more distinguishing detail at e-ink
resolutions than geometric sans; the generous leading gives partial-refresh
ghosting somewhere harmless to land. Everything else is subtraction. There
are no rules heavier than a hairline, no small caps louder than the running
head, no color, no fills, no drop caps. Drop caps were tried and rejected:
on a panel with sixteen gray levels, a decorative initial is a smudge that
the reader pays for on every refresh. The result reads like a trade
paperback that happens to weigh four hundred grams and never run out of
margin.

The same engine renders this theme and the technical grid you saw at the
top of the repository; only the stylesheet differs, and the stylesheet is
less than a screenful.

## On chapters

Every chapter opens its own page under a thin rule, the way a proper book
does, and the title page carries the table of contents with page numbers
measured from the rendered document rather than guessed. That last clause
matters more than it sounds. Pagination is where naive pipelines lie to
you: they compute where sections *should* land, ship a table of contents
full of wrong numbers, and let the reader discover the drift on page
seventeen. Here the document is rendered once, measured, and rendered
again with the truth. A chapter that grows by a paragraph moves every
number after it, and the contents page knows.

Chapters are also a pacing device. On a device with no scroll bar, a page
turn is the only progress signal; opening a chapter on a fresh page gives
the reader a place to stop, which is what chapters are for.

## On the compact theme

For manuals and API references there is a third theme — fourteen-point
body, tighter leading, the same chrome — packing roughly a fifth more
words per page. It exists for the times a document must fit the flight,
not the desk. The compact theme is deliberately not the default: density
is a cost you pay in margin notes and finger room, and most documents sent
to a tablet are read once and deleted, not consulted for a quarter.

Choose it when the document is reference-shaped: numbered sections,
tables of parameters, code you will scroll past rather than read. Choose
the serif when the document has a voice. Choose the grid when it has a
deadline.

## On margins that earn their keep

The thirteen-millimeter side margins are not decoration; they are where a
thumb rests while the other hand holds a pen, and the fifteen-millimeter
bottom margin is where that pen waits between thoughts. Typography that
ignores the hand is furniture that ignores the room. The same logic sets
the body size: sixteen pixels is exactly twelve points, the floor below
which sustained reading on this panel becomes work, verified the hard way
by a community that has been arguing about it since the first firmware.

None of these values are fashionable. They are the arithmetic of one
specific screen — a thousand four hundred and four by a thousand eight
hundred and seventy-two pixels at two hundred twenty-six dots per inch —
and the point of the whole pipeline is that you should never have to think
about them again.
