#!/usr/bin/env python3
"""Seed the semantic layer from a Palimpsesto memory/ directory.

Reads every `*.md` memory file (skipping the MEMORY.md index), and upserts it
into ChromaDB so the durable file layer becomes semantically searchable. This is
the bridge between the two layers: files are the source of truth, the semantic
store is a recall index over them.

Idempotent: each file maps to a stable ID derived from its path, so re-running
updates in place instead of duplicating.

Usage:
    python seed_from_memory.py /path/to/memory [--dry]
"""

import os
import re
import sys
import uuid

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_SCRIPT_DIR, "data")
COLLECTION_NAME = "memory"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Minimal YAML — no external dep needed."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_raw, body = m.group(1), text[m.end():]
    fm: dict[str, str] = {}
    for line in fm_raw.split("\n"):
        line = line.rstrip()
        if not line or line.startswith(" ") or ":" not in line:
            continue  # skip nested (metadata:) — we read type below separately
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip().strip('"').strip("'")
    # nested metadata.type
    tm = re.search(r"^\s+type:\s*(\S+)", fm_raw, re.MULTILINE)
    if tm:
        fm["type"] = tm.group(1)
    return fm, body


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    if not args:
        print("Usage: python seed_from_memory.py /path/to/memory [--dry]")
        sys.exit(2)

    mem_dir = os.path.expanduser(args[0])
    if not os.path.isdir(mem_dir):
        print(f"not a directory: {mem_dir}")
        sys.exit(1)

    files = []
    for root, _, names in os.walk(mem_dir):
        for n in names:
            if n.endswith(".md") and n != "MEMORY.md":
                files.append(os.path.join(root, n))

    if not dry:
        import chromadb
        client = chromadb.PersistentClient(path=DATA_DIR)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"},
        )

    seeded = 0
    for path in sorted(files):
        with open(path) as f:
            text = f.read()
        fm, body = parse_frontmatter(text)
        name = fm.get("name") or os.path.splitext(os.path.basename(path))[0]
        desc = fm.get("description", "")
        mtype = fm.get("type", "reference")
        content = f"{desc}\n\n{body}".strip() if desc else body.strip()
        if len(content) < 20:
            continue
        # stable id per file so re-seeding updates in place
        doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"palimpsesto://{name}"))
        tags = [mtype, "memory-file"]
        print(f"  {'[dry] ' if dry else ''}{name}  ({mtype}, {len(content)} chars)")
        if not dry:
            collection.upsert(
                documents=[content],
                metadatas=[{
                    "timestamp": "",
                    "source": "memory-file",
                    "role": "curated",
                    "session_id": "",
                    "tags": '["' + '", "'.join(tags) + '"]',
                }],
                ids=[doc_id],
            )
        seeded += 1

    print(f"\n{'Would seed' if dry else 'Seeded'} {seeded} memory files from {mem_dir}")


if __name__ == "__main__":
    main()
