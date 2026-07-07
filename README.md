# Palimpsesto

**Project memory for coding agents that never erases the why.**

Your agent settles something real in a session — why Markdown over SQLite, why
option B is out, what *done* means. The session ends. Next time it asks the same
questions. The work survives as code; the reasoning evaporates into a chat log.

Palimpsesto is a **two-layer memory**: a durable Markdown substrate that holds
the truth, and a local semantic engine — **ChromaDB + a Hebbian synaptic graph**
— that recalls it. On-device embeddings, no API calls, no vendor, no lock-in:
it all runs on your machine and lives in your repo. The write discipline is
convention-first (no CLI to hand-edit memory); the recall is powered by the
engine. Both halves are the tool.

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

## Two layers, one tool

Neither half is an add-on — together they are what Palimpsesto *is*:

| Layer | What it is | Retrieval |
|-------|-----------|-----------|
| **Durable files** | Curated Markdown, `compiled_truth` + `timeline`. The source of truth. | Index read every session. |
| **[Semantic engine](./semantic/)** | Local ChromaDB + on-device embeddings + a Hebbian synaptic graph. Zero API cost. | Similarity search + spreading activation, on demand. |

The files hold the truth; the semantic engine is what turns a folder of Markdown
into *memory* — it answers *"didn't we discuss this before?"* even when you don't
know which file it lives in. Co-retrieved memories **wire together** and drag
their neighbors in on the next recall; a daily decay prunes cold links,
hippocampus-style. Without the engine you have notes; with it you have recall.
See **[semantic/README.md](./semantic/README.md)**.

## Quickstart

```sh
git clone git@github.com:jeferson-guedes/Palimpsesto.git
cd Palimpsesto
./setup.sh                       # wire the skill + set up the semantic engine (venv + deps)
./setup.sh ~/my-project/memory   # also scaffold a memory dir for a project
./setup.sh --no-semantic         # files only — skip the engine (needs Python otherwise)
./setup.sh --uninstall           # remove the skill links and the engine's venv
```

Setup provisions the semantic engine by default (it needs Python 3). Pass
`--no-semantic` for the files-only case.

`setup.sh` does three things:

- links the `palimpsesto` skill into every agent config it finds, so the agent
  learns the convention once and applies it everywhere;
- provisions the semantic engine — a Python venv with ChromaDB (the engine is
  what makes this memory, not just notes; skip with `--no-semantic`);
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
| `setup.sh` | Wire skill into agents + set up the engine + scaffold a memory dir. |
| `semantic/` | The recall engine: local ChromaDB + embeddings + synaptic graph. |

## Not this

- **A rules file (CLAUDE.md / AGENTS.md).** Those are great for standing
  instructions. Palimpsesto is structured, addressable knowledge with an audit
  trail — a different job. Use both.
- **A hosted memory service.** A vendor's vector store or a model's built-in
  memory is a runtime you don't own — your knowledge lives on their infra.
  Palimpsesto's engine runs *locally* and its truth is plain files in git:
  diffable in a PR, readable by a human, an agent, or `grep`. The memory belongs
  to you, not to a model or a vendor.
- **Chat history.** History is the process. A memory is the conclusion — the
  handful of judgments you will need again.

## Credit

Palimpsesto stands on [brain.md](https://github.com/mindmuxai/brain.md) by
MindMux, which introduced `compiled_truth` + append-only `timeline` written as
one atomic move. brain.md enforces it through a CLI; Palimpsesto keeps it as a
convention, so any agent that can read a file can use one.

## License

MIT — see [LICENSE](./LICENSE).
