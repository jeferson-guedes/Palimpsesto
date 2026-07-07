#!/usr/bin/env bash
#
# Palimpsesto setup — wire the skill into your coding agents and (optionally)
# scaffold a memory directory for a project. Pure Bash, zero dependencies.
#
# Usage:
#   ./setup.sh                 # link the skill into detected agents
#   ./setup.sh PATH            # ...and scaffold a memory dir at PATH
#   ./setup.sh --semantic      # also set up the semantic layer (venv + deps)
#   ./setup.sh --clean         # remove the linked skill from detected agents
#   ./setup.sh -h | --help
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$REPO_ROOT/skills/palimpsesto"

# Agent config roots to wire the skill into. Add your own here.
AGENT_ROOTS=("$HOME/.claude" "$HOME/.codex")

CLEAN=0
SEMANTIC=0
MEMORY_DIR=""

usage() { sed -n '3,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

for arg in "$@"; do
  case "$arg" in
    --clean) CLEAN=1 ;;
    --semantic) SEMANTIC=1 ;;
    -h|--help) usage ;;
    -*) echo "unknown option: $arg" >&2; exit 2 ;;
    *) MEMORY_DIR="$arg" ;;
  esac
done

info()  { printf '  \033[32m✓\033[0m %s\n' "$1"; }
skip()  { printf '  \033[90m·\033[0m %s\n' "$1"; }
warn()  { printf '  \033[33m!\033[0m %s\n' "$1"; }

# --- wire the skill into each agent that exists on this machine ---------------
echo "Palimpsesto → agents"
linked=0
for root in "${AGENT_ROOTS[@]}"; do
  [ -d "$root" ] || { skip "$root not found — skipping"; continue; }
  dest="$root/skills/palimpsesto"
  if [ "$CLEAN" -eq 1 ]; then
    if [ -L "$dest" ] || [ -e "$dest" ]; then rm -rf "$dest"; info "removed $dest"; else skip "nothing at $dest"; fi
    continue
  fi
  mkdir -p "$root/skills"
  rm -rf "$dest"
  ln -s "$SKILL_SRC" "$dest"
  info "linked $dest → skills/palimpsesto"
  linked=$((linked + 1))
done

if [ "$CLEAN" -eq 1 ]; then echo "Done (clean)."; exit 0; fi
[ "$linked" -eq 0 ] && warn "no agent configs found — add your own to AGENT_ROOTS in setup.sh"

# --- optionally scaffold a memory directory -----------------------------------
if [ -n "$MEMORY_DIR" ]; then
  echo "Palimpsesto → memory dir"
  mkdir -p "$MEMORY_DIR"
  # the contract, so any agent working in this project can read it
  cp -f "$REPO_ROOT/PALIMPSESTO.md" "$MEMORY_DIR/PALIMPSESTO.md"
  info "$MEMORY_DIR/PALIMPSESTO.md"
  # a blank page template to copy from
  cp -f "$REPO_ROOT/templates/page.md" "$MEMORY_DIR/_TEMPLATE.md"
  info "$MEMORY_DIR/_TEMPLATE.md"
  # seed index — never clobber an existing one
  if [ -e "$MEMORY_DIR/MEMORY.md" ]; then
    skip "$MEMORY_DIR/MEMORY.md already exists — left untouched"
  else
    cp "$REPO_ROOT/templates/MEMORY.md" "$MEMORY_DIR/MEMORY.md"
    info "$MEMORY_DIR/MEMORY.md (seed index)"
  fi
fi

# --- optionally set up the semantic layer -------------------------------------
if [ "$SEMANTIC" -eq 1 ]; then
  echo "Palimpsesto → semantic layer"
  SEM="$REPO_ROOT/semantic"
  PY="$(command -v python3 || true)"
  if [ -z "$PY" ]; then warn "python3 not found — skipping semantic layer"; else
    if [ ! -d "$SEM/.venv" ]; then "$PY" -m venv "$SEM/.venv"; info "created $SEM/.venv"; else skip ".venv already exists"; fi
    "$SEM/.venv/bin/pip" install -q -r "$SEM/requirements.txt" && info "installed deps (chromadb, mcp, pyyaml)"
    echo
    echo "  Next, wire it up (see semantic/README.md for the full snippets):"
    echo "    • register the MCP server:  command = $SEM/.venv/bin/python  args = [$SEM/server.py]"
    echo "    • hooks (UserPromptSubmit → hook_retrieve.py, Stop → hook_autosave.py)"
    [ -n "$MEMORY_DIR" ] && echo "    • seed from your files:     $SEM/.venv/bin/python $SEM/seed_from_memory.py $MEMORY_DIR"
  fi
fi

echo "Done."
