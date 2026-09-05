# Brutal Layout Stress Test

A document designed to break naive PDF pipelines: wide tables, code taller
than a page, unicode soup, zalgo, base64 and 300-word walls of text.

## Wide table: 6 columns

| Feature | Claude Code 4.5 | Codex GPT-6 | Hermes 0.21 | Aider 0.9 | Cursor 2.0 | Copilot Agent |
|---|---|---|---|---|---|---|
| Context, tokens | 1 000 000 (`[1m]` flag) | 2 000 000 (X-mode) | 320 000 + in-place compaction | 200 000 (repo map) | 1 500 000 (composer) | 128 000 (index) |
| Subagents | yes (`delegate_task`) | yes (threads) | yes (`peer`) | no | yes (background) | no |
| Price per 1M in | $3.00 promo | $2.25 off-peak | GLM-5.3: $0.60 bulk | $1.20 cache miss | $2.80 | $1.95 |
| Local run | no | no | yes (headless) | yes | no | no |
| Sandbox | container | container | landlock + seccomp | none | VM | ephemeral |

## Code taller than a page

```diff
commit f6bd1634a9c1e2d3b4a5f6a7b8c9d0e1f2a3b4c5
Author: forcewake <pavel@example.dev>
Date:   Fri Sep 5 03:14:07 2026 +0200

    gateway: fix root AGENTS.md truncation at 100 797 bytes

diff --git a/gateway/run.py b/gateway/run.py
index 1a2b3c4..5d6e7f8 100644
--- a/gateway/run.py
+++ b/gateway/run.py
@@ -15256,10 +15256,18 @@ def dispatch_message(payload):
-    raw = read_file(AGENTS_PATH)
-    if len(raw) > ROOT_LIMIT:
-        raw = raw[:ROOT_LIMIT]
-        log.warning("root AGENTS.md truncated")
+    raw = read_file_bytes(AGENTS_PATH)
+    # decode per-chunk: multibyte UTF-8 at the cut boundary previously
+    # produced a surrogate that ate the next 3 bytes
+    decoded = b"".join(
+        chunk.decode("utf-8", errors="surrogatepass")
+        for chunk in chunked(raw, 65536)
+    )
+    if len(decoded) > ROOT_LIMIT:
+        cut = decoded[:ROOT_LIMIT]
+        # snap back to the last complete grapheme cluster
+        while cut and unicodedata.combining(cut[-1]):
+            cut = cut[:-1]
+        decoded = cut
+        log.warning("root AGENTS.md truncated to grapheme boundary")
     return render_context(decoded)
```

```python
# page-height block on purpose
import hashlib, pathlib, sys

def fingerprint_tree(root: pathlib.Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(x in p.parts for x in (".git", "__pycache__", "node_modules")):
            continue
        h = hashlib.sha256()
        with p.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 16), b""):
                h.update(chunk)
        out[str(p.relative_to(root))] = h.hexdigest()
    return out

def verify(manifest: dict[str, str], root: pathlib.Path) -> list[str]:
    current = fingerprint_tree(root)
    drift = []
    for rel, digest in manifest.items():
        got = current.get(rel)
        if got is None:
            drift.append(f"missing: {rel}")
        elif got != digest:
            drift.append(f"changed: {rel} {digest[:12]} -> {got[:12]}")
    for rel in current:
        if rel not in manifest:
            drift.append(f"extra:   {rel}")
    return drift

if __name__ == "__main__":
    problems = verify(
        dict(l.split("  ", 1) for l in pathlib.Path(sys.argv[2]).read_text().splitlines() if l.strip()),
        pathlib.Path(sys.argv[1]))
    print("\n".join(problems))
    sys.exit(1 if problems else 0)
```

## 30-row table

| # | Package | Version | Downloads/mo | Deps | License |
|---|---|---|---|---|---|
| 1 | hermes-agent | 0.21.0 | 412 889 | 34 | Apache-2.0 |
| 2 | deerflow-core | 2.3.1 | 89 133 | 18 | MIT |
| 3 | zai-sdk | 1.14.0 | 1 204 556 | 6 | MIT |
| 4 | glm-flash-bulk | 0.9.7 | 55 402 | 2 | proprietary |
| 5 | honcho-memory | 3.0.2 | 71 930 | 12 | MIT |
| 6 | kanban-swarm | 1.7.4 | 22 118 | 9 | Apache-2.0 |
| 7 | rmapi-ddvk | 0.0.35 | 17 653 | 0 | MIT |
| 8 | rmfakecloud | 1.2.9 | 9 844 | 3 | AGPL-3.0 |
| 9 | docx-cp | 0.4.1 | 3 127 | 22 | internal |
| 10 | serving-compiler | 0.6.0 | 812 | 41 | internal |
| 11 | agentfield | 2.1.3 | 134 005 | 27 | BSD-3 |
| 12 | copilot-credit-lab | 0.2.0 | 1 940 | 15 | internal |
| 13 | epam-pptx-next | 3.3.3 | 6 208 | 19 | internal |
| 14 | faceless-explainer | 1.9.2 | 44 719 | 8 | MIT |
| 15 | hyperframes | 4.0.1 | 96 214 | 33 | Apache-2.0 |
| 16 | media-use | 2.5.0 | 61 880 | 11 | MIT |
| 17 | grill-me | 0.8.8 | 5 555 | 1 | MIT |
| 18 | humanizer | 1.3.1 | 78 909 | 4 | MIT |
| 19 | dsh-lane | 0.5.5 | 2 246 | 5 | internal |
| 20 | remarkable-send | 1.0.0 | 890 | 3 | MIT |
| 21 | minsk-watch | 0.7.0 | 433 | 6 | internal |
| 22 | receipt-pipeline | 2.2.8 | 15 662 | 29 | MIT |
| 23 | mfo-blueprint | 1.1.1 | 2 077 | 24 | internal |
| 24 | book-recompiler | 0.3.9 | 1 155 | 7 | MIT |
| 25 | prototype-furnace | 0.1.4 | 76 | 38 | internal |
| 26 | forge-workshops | 1.0.6 | 3 044 | 13 | internal |
| 27 | sovereign-devops | 2.4.0 | 8 231 | 20 | Apache-2.0 |
| 28 | groundwell | 5.1.2 | 190 447 | 26 | MIT |
| 29 | sdlc-conveyor | 0.9.3 | 7 806 | 31 | internal |
| 30 | azure-voice | 1.6.7 | 13 209 | 9 | MIT |

## Unicode soup

Chinese: 人工智能体正在安装未经验证的代码.

Arabic: يعمل الوكلاء الذكيون على تثبيت تعليمات برمجية غير موثوقة.

Hebrew: סוכני בינה מלאכותית מתקינים קוד לא מהימן.

Japanese: エージェントは検証されていないコードをインストールします。

Zalgo: Z̴̢̛A̶̗̓L̷̜̊Ġ̵̰O̸̗̎ ̷̜̈́c̸̱̈́o̶̼̓ň̷̢t̶̰̊ḁ̵̈́ğ̷̙i̶̩̊o̷͚̓n̸̢̆.

SHA-256 with no break points:
`a3f5d8e91c04b7f6a2d3e4f5061728394a5b6c7d8e9f0a1b2c3d4e5f60718293`
and one more: `ff11aa22bb33cc44dd55ee66ff77889900112233445566778899aabbccddeeff`.

Monster URL:
https://example.com/very/long/path/segments/that/keep/going/and/going?query=1&another=2&more=3&even=4&more=5&still=6&going=7&on=8&forever=9&yes=10#anchor-at-the-end

German compound words: Donaudampfschifffahrtsgesellschaftskapitän,
Grundstücksverkehrsgenehmigungszuständigkeitsübertragungsverordnung.

Dashes and quotes: "straight" vs ‘single’ vs “double”, hyphen-minus -,
real minus −, em-dash —, en-dash – in one sentence.

## Nesting and quotes

1. Level 1
   - Level 2
     - Level 3
       - Level 4 with `inline code` and **bold**
         - Level 5 (markdown allows it; layout says hold my beer)
2. Back to level 1

> First-level quote with a long line that must wrap somewhere in the middle
> of the sentence, otherwise it runs past the margins.
> > Nested quote: researchers registered unclaimed package names and got a
> > phone-home from a Fortune 500 within an hour.
> > > Third level of nesting. More text to check indents and borders.

A footnote about Schneier[^1] and one about the researchers[^2].

[^1]: Bruce Schneier, blog, September 4, 2026.
[^2]: Hertz et al., 6 214 domains scanned, 120 pointed at unregistered packages.

## The monoparagraph

This paragraph intentionally has no line breaks for over three hundred words, because the real stress for justification is an unbroken stream of English text with embedded German compounds and technical terms like gateway, sandbox, supply-chain attack and landlock, with numbers like 100 797 bytes and 6 214 domains, with fractions like 3.5–4.0 GB and percentages like 78% used, with nested parentheses (like this (twice (thrice))) and dashes — long and short –, with hyphenated compounds like e-ink and reMarkable-compatible, with slashes like SSL/TLS and MCP/API, and all of it must sit neatly in lines of about sixty-five characters without spilling into the margins or leaving rivers three centimeters wide, because left-aligned text with anywhere-wrap either breaks monsters like Donaudampfschifffahrtsgesellschaftskapitän gracefully or mangles the layout; there are also runs of exclamation marks!!!!!!!! and ellipses…, and the camera obscura of typography: CAPITAL LETTERS OF CYRILLIC AND LATIN MIXД ОМОДЕЛЬ FOR TRACKING CHECKS, plus WeIrD CaSe and a run of numbers 0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20, and finally a link https://example.com/a/very/long/link/inside/flow/of/text/without/protection right in the middle of everything.

## Micro sections

### Crumb A

One line.

### Crumb B

One line.

### Crumb C

One line.

## Struck-through conclusion

~~First render had no margins~~ → 13 mm margins → **12pt** → `shipped`.

What this document proves, in one paragraph: a six-column table keeps its
columns aligned without overlapping; a code block taller than a page splits
cleanly with its box redrawn; a thirty-row table repeats its header on every
continuation; CJK, RTL and combining-diacritic text stay inside the margins;
footnotes land at the end without breaking the flow above them; and a
300-word unbroken paragraph still settles into ~65-character lines. None of
this required tuning per document — the same engine that renders the digest
and the essay renders this.

---

End of the stress test. If this reads well on e-ink, the layout holds.
