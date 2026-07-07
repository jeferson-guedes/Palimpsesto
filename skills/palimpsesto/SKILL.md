---
name: palimpsesto
description: Project memory convention — durable Markdown memory where compiled_truth is rewritable and timeline is append-only, so a change of mind never erases the reasoning behind it. Use when reading or writing project/feedback memory files.
---

# Palimpsesto

You maintain a project's memory as plain Markdown under a `memory/` directory,
indexed by `MEMORY.md`. Full contract: read `PALIMPSESTO.md` at the repo root.

## When to use

- **Session start / before a task** — read `MEMORY.md` and open the memories
  relevant to the request.
- **A decision or insight surfaces** — capture it at the moment, not at the end.
- **A past conclusion is overturned** — record the reversal (see the rule below).

## The test for what belongs

> Will this still matter in a few months, and is it hard to reconstruct from the
> code itself?

Yes → write it. No → leave it in code and commit messages.

## Writing a memory

Frontmatter, always:

```
---
name: <kebab-case-slug>
description: <one-line summary used for recall>
metadata:
  type: user | feedback | project | reference
---
```

`user` and `reference` are stable — a plain body is fine.

`project` and `feedback` evolve — use the Palimpsesto body:

```
# <title>

## compiled_truth
<current best understanding — rewritable as a whole>

## timeline
- <YYYY-MM-DD> · <kind> · <one line> [· source: <origin>]

**Why:** <the reasoning>
**How to apply:** <what to do with this>
```

`kind` ∈ `decision | reversal | hypothesis | finding | milestone | correction`.
Link related memories with `[[name]]`.

## The one rule (no silent edits)

When an understanding changes, **do not overwrite the old conclusion silently**:

1. Rewrite `compiled_truth` to the new state.
2. **Append** a `reversal` (or `correction`) line to `timeline` with what changed
   and why.

Do both together — every time. The change of mind stays on the record.

## Index discipline

Every new memory gets one pointer line in `MEMORY.md`:
`- [Title](file.md) — one-line hook`. `MEMORY.md` holds pointers only, never
memory content. Retrofit `timeline` into a file the next time you touch it —
never rewrite history in bulk.
