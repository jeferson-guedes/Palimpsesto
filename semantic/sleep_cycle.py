#!/usr/bin/env python3
"""Sleep Cycle: memory consolidation, deduplication, and synaptic pruning.

Zero external API cost. All merges use structural heuristics.

Run daily via cron (adjust the path to where you installed the semantic layer):
  0 3 * * * "$HOME/.claude/skills/palimpsesto/../../../semantic/.venv/bin/python" /path/to/palimpsesto/semantic/sleep_cycle.py

Note: maintenance.py already runs a lighter version of this opportunistically from
the autosave hook, so the cron job is optional — use it only if you want a
heavier daily consolidation independent of when the agent runs.

Three phases:
1. Deduplication — find near-duplicate memories (score > 0.95), merge structurally
2. Synaptic Decay — reduce all weights by factor, prune weak connections
3. Orphan Cleanup — remove synapses pointing to deleted memories
"""

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

DATA_DIR = os.path.join(_SCRIPT_DIR, "data")
COLLECTION_NAME = "memory"
DEDUP_THRESHOLD = 0.95
DECAY_FACTOR = 0.9


def merge_documents(doc_a: str, doc_b: str) -> str:
    """Merge two near-duplicate documents keeping unique content.

    Understands the ## section structure (Summary, Facts, Decisions, Corrections).
    """
    sections_a = _parse_sections(doc_a)
    sections_b = _parse_sections(doc_b)

    all_headers = list(dict.fromkeys(list(sections_a.keys()) + list(sections_b.keys())))

    parts = []
    for header in all_headers:
        items_a = _extract_items(sections_a.get(header, ""))
        items_b = _extract_items(sections_b.get(header, ""))

        # Merge unique items
        merged_items = list(dict.fromkeys(items_a + items_b))
        if merged_items:
            if header:
                parts.append(f"## {header}\n" + "\n".join(f"- {item}" for item in merged_items))
            else:
                parts.append("\n".join(merged_items))

    return "\n\n".join(parts) if parts else (doc_a if len(doc_a) >= len(doc_b) else doc_b)


def _parse_sections(text: str) -> dict[str, str]:
    """Parse markdown ## sections into {header: content}."""
    sections = {}
    current_header = ""
    current_lines = []

    for line in text.split("\n"):
        if line.startswith("## "):
            if current_header or current_lines:
                sections[current_header] = "\n".join(current_lines)
            current_header = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_header or current_lines:
        sections[current_header] = "\n".join(current_lines)

    return sections


def _extract_items(text: str) -> list[str]:
    """Extract list items or sentences from section content."""
    items = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Remove bullet prefixes
        clean = re.sub(r"^[\-\*]\s+", "", line)
        if clean and len(clean) > 5:
            items.append(clean)
    return items


def phase_dedup(collection) -> dict:
    """Find and merge near-duplicate documents."""
    all_data = collection.get(include=["documents", "metadatas"])
    ids = all_data["ids"]
    docs = all_data["documents"]
    metas = all_data["metadatas"]

    if len(ids) < 2:
        return {"checked": 0, "merged": 0}

    merged_away = set()
    new_docs = []
    checked = 0

    for i in range(len(ids)):
        if ids[i] in merged_away:
            continue

        results = collection.query(
            query_texts=[docs[i]],
            n_results=5,
            include=["documents", "metadatas", "distances"],
        )

        for j_doc, j_meta, j_dist, j_id in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
            results["ids"][0],
        ):
            if j_id == ids[i] or j_id in merged_away:
                continue

            score = 1 - (j_dist / 2)
            checked += 1

            if score >= DEDUP_THRESHOLD:
                merged_text = merge_documents(docs[i], j_doc)

                # Merge tags
                tags_a = json.loads(metas[i].get("tags", "[]"))
                tags_b = json.loads(j_meta.get("tags", "[]"))
                merged_tags = list(dict.fromkeys(tags_a + tags_b))[:5]

                newest_ts = max(metas[i].get("timestamp", ""), j_meta.get("timestamp", ""))

                new_docs.append((
                    merged_text,
                    {
                        "timestamp": newest_ts,
                        "source": metas[i].get("source", "claude"),
                        "role": "consolidated",
                        "session_id": "",
                        "tags": json.dumps(merged_tags),
                    },
                ))

                merged_away.add(ids[i])
                merged_away.add(j_id)
                print(f"  Merged: {ids[i][:8]}... + {j_id[:8]}... (score={score:.3f})")
                break

    if merged_away:
        collection.delete(ids=list(merged_away))
        try:
            from synapses import delete_for_memory
            for mid in merged_away:
                delete_for_memory(mid)
        except Exception:
            pass

    for content, metadata in new_docs:
        doc_id = str(uuid.uuid4())
        collection.add(documents=[content], metadatas=[metadata], ids=[doc_id])

    return {"checked": checked, "merged": len(new_docs)}


def phase_decay() -> dict:
    """Apply synaptic weight decay and prune weak connections."""
    try:
        from synapses import decay_all, stats

        before = stats()
        result = decay_all(factor=DECAY_FACTOR)
        after = stats()

        return {
            "decayed": result["decayed"],
            "pruned": result["pruned"],
            "synapses_before": before["total_synapses"],
            "synapses_after": after["total_synapses"],
            "avg_weight": round(after["avg_weight"], 4),
        }
    except Exception as e:
        return {"error": str(e)}


def phase_orphan_cleanup(collection) -> dict:
    """Remove synapses that reference non-existent memories."""
    try:
        import sqlite3
        from synapses import DB_PATH

        all_ids = set(collection.get()["ids"])
        conn = sqlite3.connect(DB_PATH)

        rows = conn.execute("SELECT id_a, id_b FROM synapses").fetchall()
        orphans = []
        for id_a, id_b in rows:
            if id_a not in all_ids or id_b not in all_ids:
                orphans.append((id_a, id_b))

        for id_a, id_b in orphans:
            conn.execute("DELETE FROM synapses WHERE id_a = ? AND id_b = ?", (id_a, id_b))

        conn.commit()
        conn.close()
        return {"orphans_removed": len(orphans)}

    except Exception as e:
        return {"error": str(e)}


def main():
    import chromadb

    print(f"=== Sleep Cycle — {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")

    client = chromadb.PersistentClient(path=DATA_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    total = collection.count()
    print(f"Collection: {total} documents\n")

    print("Phase 1: Deduplication & Consolidation")
    dedup_result = phase_dedup(collection)
    print(f"  Checked {dedup_result['checked']} pairs, merged {dedup_result['merged']}\n")

    print("Phase 2: Synaptic Decay")
    decay_result = phase_decay()
    if "error" in decay_result:
        print(f"  Error: {decay_result['error']}\n")
    else:
        print(f"  Decayed {decay_result['decayed']} synapses (factor={DECAY_FACTOR})")
        print(f"  Pruned {decay_result['pruned']} weak synapses")
        print(f"  Network: {decay_result['synapses_after']} synapses, avg weight={decay_result['avg_weight']}\n")

    print("Phase 3: Orphan Cleanup")
    orphan_result = phase_orphan_cleanup(collection)
    if "error" in orphan_result:
        print(f"  Error: {orphan_result['error']}\n")
    else:
        print(f"  Removed {orphan_result['orphans_removed']} orphan synapses\n")

    final_count = collection.count()
    print(f"Done. Documents: {total} → {final_count}")


if __name__ == "__main__":
    main()
