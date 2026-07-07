#!/usr/bin/env python3
"""Spreading Activation retrieval: vector search + synaptic neighbors.

1. Searches ChromaDB for semantically similar memories (cosine)
2. Takes the top result IDs and queries the synaptic network for connected memories
3. Fetches synaptic neighbors from ChromaDB by ID
4. Injects both direct + connected memories into stdout for Claude
"""

import json
import os
import sys

# Ensure our directory is on the path so synapses.py is importable
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

DATA_DIR = os.path.join(_SCRIPT_DIR, "data")
COLLECTION_NAME = "memory"
MIN_SCORE = 0.70
MAX_DIRECT_RESULTS = 5
MAX_SYNAPTIC_RESULTS = 3
MIN_PROMPT_LENGTH = 15
MIN_SYNAPSE_WEIGHT = 0.2


def main():
    try:
        hook_input = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    # Claude Code envia a chave "prompt" no UserPromptSubmit; "user_prompt" é
    # fallback defensivo (versões antigas / mudança de schema do CLI).
    user_prompt = (hook_input.get("prompt") or hook_input.get("user_prompt") or "").strip()

    if len(user_prompt) < MIN_PROMPT_LENGTH:
        sys.exit(0)

    try:
        import chromadb

        client = chromadb.PersistentClient(path=DATA_DIR)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        if collection.count() == 0:
            sys.exit(0)

        # --- Phase 1: Vector search ---
        results = collection.query(
            query_texts=[user_prompt],
            n_results=MAX_DIRECT_RESULTS,
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]
        ids = results.get("ids", [[]])[0]

        direct_memories = []
        direct_ids = []
        for doc_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
            score = 1 - (dist / 2)
            if score < MIN_SCORE:
                continue
            source = meta.get("source", "")
            timestamp = meta.get("timestamp", "")[:10]
            tags = json.loads(meta.get("tags", "[]"))
            tag_str = f" [{', '.join(tags)}]" if tags else ""
            direct_memories.append(
                f"[{source} {timestamp}{tag_str} score={score:.2f}] {doc[:500]}"
            )
            direct_ids.append(doc_id)

        # --- Auto-strengthen: co-retrieval for the same prompt IS co-activation ---
        # "Neurons that fire together wire together." Removes the need to call the
        # strengthen_synapses MCP tool by hand — the network now grows organically on
        # every relevant retrieval. Gentle delta so it builds up over repeated co-recall.
        if len(direct_ids) > 1:
            try:
                from synapses import strengthen_group

                strengthen_group(direct_ids, delta=0.05)
            except Exception as e:
                print(f"[semantic-memory] auto-strengthen error: {e}", file=sys.stderr)

        # --- Phase 2: Spreading activation via synaptic network ---
        synaptic_memories = []
        if direct_ids:
            try:
                from synapses import get_neighbors_bulk

                neighbor_ids = get_neighbors_bulk(
                    direct_ids,
                    min_weight=MIN_SYNAPSE_WEIGHT,
                    limit=MAX_SYNAPTIC_RESULTS,
                )

                if neighbor_ids:
                    # Fetch neighbor documents from ChromaDB
                    neighbor_results = collection.get(
                        ids=neighbor_ids,
                        include=["documents", "metadatas"],
                    )

                    for doc, meta in zip(
                        neighbor_results.get("documents", []),
                        neighbor_results.get("metadatas", []),
                    ):
                        source = meta.get("source", "")
                        timestamp = meta.get("timestamp", "")[:10]
                        tags = json.loads(meta.get("tags", "[]"))
                        tag_str = f" [{', '.join(tags)}]" if tags else ""
                        synaptic_memories.append(
                            f"[synapse {source} {timestamp}{tag_str}] {doc[:400]}"
                        )

            except Exception as e:
                print(f"[semantic-memory] synapse lookup error: {e}", file=sys.stderr)

        # --- Output ---
        if not direct_memories and not synaptic_memories:
            sys.exit(0)

        lines = []
        total = len(direct_memories) + len(synaptic_memories)
        lines.append(f"[semantic-memory] {total} relevant memories found:")

        for m in direct_memories:
            lines.append(f"  - {m}")

        if synaptic_memories:
            lines.append(f"  [connected via synapses]:")
            for m in synaptic_memories:
                lines.append(f"  - {m}")

        # Output the IDs used so Claude can strengthen synapses via MCP tool
        all_used_ids = direct_ids + [
            nid for nid in (neighbor_ids if direct_ids and 'neighbor_ids' in dir() else [])
        ]
        if len(all_used_ids) > 1:
            lines.append(f"  [memory_ids: {','.join(all_used_ids[:8])}]")

        print("\n".join(lines))

    except Exception as e:
        print(f"[semantic-memory] retrieval error: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
