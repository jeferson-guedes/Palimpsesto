# Palimpsesto

**Project memory for coding agents that never erases the why.**

Your agent settles something real in a session — why Markdown over SQLite, why
option B is out, what *done* means. The session ends. Next time it asks the same
questions. The work survives as code; the reasoning evaporates into a chat log.

Palimpsesto gives the project a durable memory written as plain Markdown that
lives in the repo. It is **convention-first**: nothing to install to start, no
runtime, no CLI required. The agent learns how it works by reading one file.

> A *palimpsest* is a manuscript rewritten over an erased one, where the earlier
> text still shows through. That is the design: the current understanding is
> rewritten in place; the reasoning behind it stays readable underneath.

## How it works

A memory file has two layers:

- **`compiled_truth`** — the current best understanding, rewritable as a whole.
- **`timeline`** — an append-only trail of how it got there.

When a conclusion changes, you rewrite `compiled_truth` **and** append a
`reversal` line to `timeline`, together. The change of mind stays on the record.
That single habit is what stops a knowledge base from rotting through silent
edits.

The full contract is in **[PALIMPSESTO.md](./PALIMPSESTO.md)** — point your agent
at it.

## Two layers

Palimpsesto is the durable layer — but recall matters too. Ships with both:

| Layer | What it is | Retrieval |
|-------|-----------|-----------|
| **Durable files** (core) | Curated Markdown, `compiled_truth` + `timeline`. The source of truth. | Index read every session. |
| **[Semantic layer](./semantic/)** (optional) | Local ChromaDB + on-device embeddings + a Hebbian synaptic graph. Zero API cost. | Similarity search + spreading activation, on demand. |

The files are the truth; the semantic layer is an associative index over them
that answers *"didn't we discuss this before?"* even when you don't know which
file it lives in. Co-retrieved memories **wire together** and drag their
neighbors in on the next recall. Fully optional — the file layer stands alone.
See **[semantic/README.md](./semantic/README.md)**.

## Quickstart

```sh
git clone git@github.com:jeferson-guedes/Palimpsesto.git
cd Palimpsesto
./setup.sh                       # wire the skill into your agents (~/.claude, ~/.codex)
./setup.sh ~/my-project/memory   # also scaffold a memory dir for a project
./setup.sh --semantic            # also set up the optional semantic layer (venv + deps)
```

`setup.sh` is pure Bash — **zero dependencies**. It:

- links the `palimpsesto` skill into every agent config it finds, so the agent
  learns the convention once and applies it everywhere;
- scaffolds a `memory/` directory (with a seed `MEMORY.md`) when you pass a path.

From there it is just Markdown. Read and write the files with your editor, your
agent, or `grep`.

## What's in the box

| Path | What |
|------|------|
| `PALIMPSESTO.md` | The contract — the agent reads this to learn the memory. |
| `skills/palimpsesto/SKILL.md` | Install-once skill teaching the convention. |
| `templates/MEMORY.md` | Seed index. |
| `templates/page.md` | Blank memory page (`compiled_truth` + `timeline`). |
| `templates/page-example.md` | A worked example showing a reversal on the record. |
| `setup.sh` | Wire skill into agents + scaffold a memory dir + optional semantic setup. |
| `semantic/` | Optional recall layer: local ChromaDB + embeddings + synaptic graph. |

## Not this

- **A rules file (CLAUDE.md / AGENTS.md).** Those are great for standing
  instructions. Palimpsesto is structured, addressable knowledge with an audit
  trail — a different job. Use both.
- **A vector store or hosted memory.** Those are runtimes over your knowledge.
  Palimpsesto is the substrate: plain files in git, diffable in a PR, readable by
  a human, an agent, or `grep`. Put a runtime on top if you want; the knowledge
  still belongs to the repo.
- **Chat history.** History is the process. A memory is the conclusion — the
  handful of judgments you will need again.

## Credit

Palimpsesto stands on [brain.md](https://github.com/mindmuxai/brain.md) by
MindMux, which introduced `compiled_truth` + append-only `timeline` written as
one atomic move. brain.md enforces it through a CLI; Palimpsesto keeps it as a
convention, so any agent that can read a file can use one.

## License

MIT — see [LICENSE](./LICENSE).
