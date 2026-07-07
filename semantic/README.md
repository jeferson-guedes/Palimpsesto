# Palimpsesto — Semantic Layer

The durable file layer (`PALIMPSESTO.md`) is the source of truth: curated
Markdown you and the agent read and write deliberately. This is the **recall
layer** on top of it — an associative index that surfaces relevant past context
by *similarity*, without anyone having to remember which file it lives in.

Two layers, two jobs:

| | Durable files | Semantic layer (this) |
|---|---|---|
| Retrieval | index read every session | similarity search on demand |
| Curation | deliberate, by hand/agent | automatic (hooks) + seeded from files |
| Best at | decisions, references, feedback | "didn't we discuss this before?" recall |

It is a local **ChromaDB** store with on-device embeddings (`all-MiniLM-L6-v2`)
— **zero API cost, nothing leaves your machine** — plus a synaptic graph that
learns which memories belong together.

## Why the synapses

Vector search alone is stateless: it finds what *reads* like your query. The
synaptic layer adds *association* — a SQLite weighted graph over memory IDs,
Hebbian by design: **memories co-retrieved for the same prompt wire together**
(`synapses.py`). On the next recall, a strong hit drags its neighbors in too
(spreading activation), so context that isn't textually similar but is
*relationally* relevant still surfaces. A daily decay prunes links that stop
firing — the network stays lean, hippocampus-style.

## Components

| File | Role |
|------|------|
| `server.py` | MCP server (stdio). Tools: `save_context`, `search_context`, `list_sources`, `delete_context`, `strengthen_synapses`, `synapse_stats`. |
| `synapses.py` | Hebbian weighted graph: strengthen, spreading activation, decay, prune. |
| `hook_retrieve.py` | `UserPromptSubmit` hook — vector search + synaptic neighbors, injected into context. Auto-strengthens co-retrieved memories. |
| `hook_autosave.py` | `Stop` hook — distills the last turns into a compact memory and saves it. Runs light maintenance opportunistically. |
| `maintenance.py` | Throttled (1×/day) synaptic decay + pruning of old, never-connected auto-saves. Called from the autosave hook — no external cron needed. |
| `sleep_cycle.py` | Optional heavier daily consolidation: dedup/merge near-duplicates, decay, orphan cleanup. |
| `seed_from_memory.py` | Bridge: seed the store from a Palimpsesto `memory/` directory so curated files become searchable. |

## Install

```sh
cd semantic
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt          # chromadb, mcp, pyyaml
```

Or let the top-level installer do it: `./setup.sh --semantic`.

### 1. Register the MCP server

Add to your agent's MCP config (e.g. `~/.claude.json` or a project `.mcp.json`):

```json
{
  "mcpServers": {
    "memory": {
      "command": "/ABS/PATH/palimpsesto/semantic/.venv/bin/python",
      "args": ["/ABS/PATH/palimpsesto/semantic/server.py"]
    }
  }
}
```

### 2. Wire the hooks (optional but recommended)

In `~/.claude/settings.json`, so recall and auto-save happen automatically:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command",
        "command": "/ABS/PATH/semantic/.venv/bin/python /ABS/PATH/semantic/hook_retrieve.py" }] }
    ],
    "Stop": [
      { "hooks": [{ "type": "command",
        "command": "/ABS/PATH/semantic/.venv/bin/python /ABS/PATH/semantic/hook_autosave.py" }] }
    ]
  }
}
```

### 3. Seed from your durable files

```sh
.venv/bin/python seed_from_memory.py /path/to/your/memory --dry   # preview
.venv/bin/python seed_from_memory.py /path/to/your/memory         # write
```

## Data

Everything persists under `semantic/data/` — `chroma.sqlite3` (vectors) and
`synapses.db` (the graph). It is git-ignored: **your memories never get
committed to this repo.** Back it up like any local database.

## Not model-locked

The store is ChromaDB + a SQLite graph on plain files; the embeddings run
locally. Any agent that can call an MCP tool — or just run these scripts as
hooks — can use it. The memory belongs to you, not to a model or a vendor.
