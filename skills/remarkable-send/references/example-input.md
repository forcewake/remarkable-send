# Example input (complete, annotated)

This is what a prepared article looks like before calling the engine.
Command for this exact file:

```bash
${HERMES_SKILL_DIR}/scripts/remarkable_send.py \
  --file /tmp/rm-send/sample.md --source internal.test
```

Notes after the fence describe what the tablet does with each element —
they are NOT part of the file.

```markdown
# Context engineering for production agents

The gap between demo agents and production agents is almost never the model.
It is what the model sees at decision time.

## Why context beats prompts

Three levers matter in practice:

1. **Selection** — what enters the window (retrieval, tools, memory).
2. **Compression** — summaries that preserve decisions, not vibes.
3. **Layout** — stable structure so the model can navigate its own input.

> An agent is a function from context to action. Everything else is plumbing.

### A worked example

```python
def build_context(task, memory):
    relevant = memory.search(task, k=8, min_score=0.55)
    pinned = [m for m in relevant if m.pinned]
    return render(pinned, relevant, budget_tokens=24_000)
```

| Lever | Naive | Engineered |
|---|---|---|
| Selection | top-k by cos sim | score + recency + pinned set |
| Compression | truncate tail | decision-preserving summaries |

## Failure modes

- Context rot: stale facts pinned forever — audit monthly.
- Summary drift: keep verbatim anchors for decisions.

That's the whole game: measure what enters the window, then engineer it.
```

Rendering behavior, element by element:

- `#` title → 30px bold headline, `source` row beneath it (from `--source`).
- lead paragraph → shares the title page.
- `## Why context beats prompts` → starts page 2 (every `##` = new page).
- numbered list + bold → 12pt body, page 2.
- quote → black left bar, italic.
- `### A worked example` → subhead on the same page.
- fenced python → boxed mono block, never split across pages.
- table → bordered grid with mono header.
- `## Failure modes` → starts page 3.
