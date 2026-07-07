#!/usr/bin/env bash
#
# Palimpsesto setup — wire the skill into your coding agents, set up the semantic
# engine, and (optionally) scaffold a memory directory. Pure Bash for the wiring;
# the engine needs Python 3.
#
# Usage:
#   ./setup.sh                 # wire the skill + set up the semantic engine
#   ./setup.sh PATH            # ...and scaffold a memory dir at PATH
#   ./setup.sh --no-semantic   # files only — skip the engine (no Python needed)
#   ./setup.sh --uninstall     # remove the skill links and the engine's venv
#   ./setup.sh --uninstall --purge   # ...and DELETE the semantic data (memories)
#   ./setup.sh -h | --help
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$REPO_ROOT/skills/palimpsesto"
SEM="$REPO_ROOT/semantic"

# Agent config roots to wire the skill into. Add your own here.
AGENT_ROOTS=("$HOME/.claude" "$HOME/.codex")

UNINSTALL=0
PURGE=0
SEMANTIC=1
MEMORY_DIR=""

usage() { sed -n '3,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

for arg in "$@"; do
  case "$arg" in
    --uninstall) UNINSTALL=1 ;;
    --purge) PURGE=1 ;;
    --no-semantic) SEMANTIC=0 ;;
    -h|--help) usage ;;
    -*) echo "unknown option: $arg" >&2; exit 2 ;;
    *) MEMORY_DIR="$arg" ;;
  esac
done

info()  { printf '  \033[32m✓\033[0m %s\n' "$1"; }
skip()  { printf '  \033[90m·\033[0m %s\n' "$1"; }
warn()  { printf '  \033[33m!\033[0m %s\n' "$1"; }

# --- uninstall ----------------------------------------------------------------
if [ "$UNINSTALL" -eq 1 ]; then
  echo "Palimpsesto → uninstall"
  for root in "${AGENT_ROOTS[@]}"; do
    dest="$root/skills/palimpsesto"
    if [ -L "$dest" ] || [ -e "$dest" ]; then rm -rf "$dest"; info "removed $dest"; else skip "nothing at $dest"; fi
  done
  if [ -d "$SEM/.venv" ]; then rm -rf "$SEM/.venv"; info "removed $SEM/.venv"; else skip "no engine venv"; fi
  rm -f "$SEM/.last_maintenance"
  if [ "$PURGE" -eq 1 ]; then
    if [ -d "$SEM/data" ]; then rm -rf "$SEM/data"; warn "PURGED $SEM/data — semantic memories deleted"; else skip "no engine data"; fi
  else
    [ -d "$SEM/data" ] && skip "kept $SEM/data (your memories) — pass --purge to delete"
  fi
  echo "Uninstalled. Scaffolded memory/ dirs and MCP/hook config entries are left for you to remove."
  exit 0
fi

# --- wire the skill into each agent that exists on this machine ---------------
echo "Palimpsesto → agents"
linked=0
for root in "${AGENT_ROOTS[@]}"; do
  [ -d "$root" ] || { skip "$root not found — skipping"; continue; }
  dest="$root/skills/palimpsesto"
  mkdir -p "$root/skills"
  rm -rf "$dest"
  ln -s "$SKILL_SRC" "$dest"
  info "linked $dest → skills/palimpsesto"
  linked=$((linked + 1))
done
[ "$linked" -eq 0 ] && warn "no agent configs found — add your own to AGENT_ROOTS in setup.sh"

# --- set up the semantic engine (default) -------------------------------------
if [ "$SEMANTIC" -eq 1 ]; then
  echo "Palimpsesto → semantic engine"
  PY="$(command -v python3 || true)"
  if [ -z "$PY" ]; then
    warn "python3 not found — engine skipped. Install Python 3 and re-run, or use --no-semantic."
  else
    if [ ! -d "$SEM/.venv" ]; then "$PY" -m venv "$SEM/.venv"; info "created $SEM/.venv"; else skip ".venv already exists"; fi
    "$SEM/.venv/bin/pip" install -q -r "$SEM/requirements.txt" && info "installed deps (chromadb, mcp, pyyaml)"
    echo
    echo "  Wire it up (full snippets in semantic/README.md):"
    echo "    • register the MCP server:  command = $SEM/.venv/bin/python  args = [$SEM/server.py]"
    echo "    • hooks: UserPromptSubmit → hook_retrieve.py, Stop → hook_autosave.py"
  fi
else
  skip "semantic engine skipped (--no-semantic)"
fi

# --- optionally scaffold a memory directory -----------------------------------
if [ -n "$MEMORY_DIR" ]; then
  echo "Palimpsesto → memory dir"
  mkdir -p "$MEMORY_DIR"
  cp -f "$REPO_ROOT/PALIMPSESTO.md" "$MEMORY_DIR/PALIMPSESTO.md"; info "$MEMORY_DIR/PALIMPSESTO.md"
  cp -f "$REPO_ROOT/templates/page.md" "$MEMORY_DIR/_TEMPLATE.md"; info "$MEMORY_DIR/_TEMPLATE.md"
  if [ -e "$MEMORY_DIR/MEMORY.md" ]; then
    skip "$MEMORY_DIR/MEMORY.md already exists — left untouched"
  else
    cp "$REPO_ROOT/templates/MEMORY.md" "$MEMORY_DIR/MEMORY.md"; info "$MEMORY_DIR/MEMORY.md (seed index)"
  fi
  if [ "$SEMANTIC" -eq 1 ] && [ -d "$SEM/.venv" ]; then
    echo "    • seed from your files:  $SEM/.venv/bin/python $SEM/seed_from_memory.py $MEMORY_DIR"
  fi
fi

echo "Done."
