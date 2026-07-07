# PALIMPSESTO — Project Memory Contract

> A *palimpsest* is a manuscript written over an erased one, where the earlier
> text still shows through. That is the whole idea: the current understanding is
> rewritten in place, but the reasoning behind it is never erased — it stays
> readable underneath.

This file is the contract. Any coding agent learns how the memory works just by
reading it. The memory itself is plain Markdown that lives with the project and
outlives every session.

Palimpsesto is convention-first: there is no CLI and no runtime to stand up. The
correctness comes from a habit the agent follows, not from tooling. (A helper
script is optional and lives outside this contract.)

## What belongs in memory

Before writing anything, ask:

> **Will this still matter in a few months, and is it hard to reconstruct from
> the code itself?**

Yes → write it to memory. No → leave it in the code and commit messages.

## File layout

```
memory/
├── MEMORY.md        # the index — one line per memory, loaded every session
└── *.md             # one memory per file
```

`MEMORY.md` is the table of contents. It carries no memory content itself — only
pointers: `- [Title](file.md) — one-line hook`. It is loaded into context at the
start of every session, so keep it to a single line per file.

## The two kinds of memory

Every memory file has YAML frontmatter:

```
---
name: <kebab-case-slug>
description: <one-line summary — used to judge relevance during recall>
metadata:
  type: user | feedback | project | reference
---
```

- **user** — who the person is (role, expertise, preferences). Stable.
- **reference** — pointers to external resources (URLs, dashboards, credentials
  location, tickets). Mostly stable.
- **feedback** — guidance on how the agent should work; include the *why*.
- **project** — ongoing work, decisions, and constraints not derivable from the
  code or git history.

`user` and `reference` are usually stable — a simple body is enough.

**`project` and `feedback` evolve over time. They carry a Palimpsesto body:**

```
# <title>

## compiled_truth
<the current best understanding — rewritable as a whole>

## timeline
- <YYYY-MM-DD> · <kind> · <one-line summary> [· source: <origin>]
- ...

**Why:** <for feedback/project — the reasoning>
**How to apply:** <for feedback/project — what to do with this>
```

`kind` is one of: `decision`, `reversal`, `hypothesis`, `finding`, `milestone`,
`correction`.

Link related memories with `[[name]]`, where `name` is another file's `name:`
slug. A `[[name]]` that has no file yet is fine — it marks something worth
writing later.

## The one rule that matters (no silent edits)

The most common way a knowledge base rots is the silent edit: someone changes
the conclusion and the reasoning behind it disappears.

When an understanding changes, **do not overwrite the old conclusion in
silence.** Instead:

1. Rewrite `compiled_truth` to the new state.
2. **Append** a `reversal` (or `correction`) line to `timeline` saying what
   changed and why.

Rewriting `compiled_truth` and appending its `timeline` entry are one move — do
them together, always. The change of mind stays on the record, and the path back
is traceable. This is the same atomic pair brain.md enforces through its CLI;
here it is upheld by discipline instead.

## Working habits

- **Load first.** At the start of a task, read `MEMORY.md` and open the memories
  relevant to the request.
- **Capture at the moment.** Write a decision or insight when it surfaces, not at
  the end.
- **Retrofit incrementally.** A `project`/`feedback` file gains its `timeline`
  the next time you touch it — never rewrite history in bulk.
- **Point-in-time.** A memory reflects what was true when written. If it cites a
  file, function, or value, verify it still holds before asserting it as fact.

## Credit

Palimpsesto adapts two invariants from
[brain.md](https://github.com/mindmuxai/brain.md) (MindMux): `compiled_truth` +
append-only `timeline`, written together. brain.md enforces them through a CLI;
Palimpsesto keeps them as a convention so any agent that can read a file can use
one — with nothing but your editor and a terminal.
