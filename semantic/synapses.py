"""Synaptic network: Hebbian learning between memory nodes.

SQLite-backed weighted graph. Edges represent co-activation of memories.
- strengthen(a, b): "neurons that fire together wire together" (+delta)
- get_neighbors(id): spreading activation — find connected memories
- decay_all(factor): global weight decay (synaptic pruning prep)
- prune(threshold): delete weak synapses below threshold
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "synapses.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # concurrent reads
    conn.execute("""
        CREATE TABLE IF NOT EXISTS synapses (
            id_a TEXT NOT NULL,
            id_b TEXT NOT NULL,
            weight REAL NOT NULL DEFAULT 0.1,
            co_activations INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            last_accessed_at TEXT NOT NULL,
            PRIMARY KEY (id_a, id_b)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_synapses_a ON synapses(id_a)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_synapses_b ON synapses(id_b)
    """)
    conn.commit()
    return conn


def _normalize_pair(id_a: str, id_b: str) -> tuple[str, str]:
    """Ensure consistent ordering so (A,B) and (B,A) map to the same edge."""
    return (id_a, id_b) if id_a <= id_b else (id_b, id_a)


def strengthen(id_a: str, id_b: str, delta: float = 0.1) -> float:
    """Hebbian learning: strengthen the synapse between two memories.

    Returns the new weight.
    """
    if id_a == id_b:
        return 0.0

    id_a, id_b = _normalize_pair(id_a, id_b)
    now = datetime.now(timezone.utc).isoformat()
    conn = _connect()

    row = conn.execute(
        "SELECT weight, co_activations FROM synapses WHERE id_a = ? AND id_b = ?",
        (id_a, id_b),
    ).fetchone()

    if row:
        new_weight = min(row["weight"] + delta, 1.0)  # cap at 1.0
        conn.execute(
            """UPDATE synapses
               SET weight = ?, co_activations = co_activations + 1, last_accessed_at = ?
               WHERE id_a = ? AND id_b = ?""",
            (new_weight, now, id_a, id_b),
        )
    else:
        new_weight = delta
        conn.execute(
            """INSERT INTO synapses (id_a, id_b, weight, co_activations, created_at, last_accessed_at)
               VALUES (?, ?, ?, 1, ?, ?)""",
            (id_a, id_b, new_weight, now, now),
        )

    conn.commit()
    conn.close()
    return new_weight


def strengthen_group(ids: list[str], delta: float = 0.1) -> int:
    """Strengthen all pairwise synapses in a group of co-activated memories.

    Returns the number of synapses strengthened.
    """
    count = 0
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            strengthen(ids[i], ids[j], delta)
            count += 1
    return count


def get_neighbors(memory_id: str, min_weight: float = 0.1, limit: int = 10) -> list[dict]:
    """Spreading activation: get memories connected to this one.

    Returns list of {id, weight, co_activations, last_accessed_at}.
    """
    conn = _connect()
    now = datetime.now(timezone.utc).isoformat()

    rows = conn.execute(
        """SELECT id_b AS neighbor_id, weight, co_activations, last_accessed_at
           FROM synapses WHERE id_a = ? AND weight >= ?
           UNION ALL
           SELECT id_a AS neighbor_id, weight, co_activations, last_accessed_at
           FROM synapses WHERE id_b = ? AND weight >= ?
           ORDER BY weight DESC
           LIMIT ?""",
        (memory_id, min_weight, memory_id, min_weight, limit),
    ).fetchall()

    # Touch last_accessed_at for retrieved synapses
    neighbor_ids = [r["neighbor_id"] for r in rows]
    for nid in neighbor_ids:
        a, b = _normalize_pair(memory_id, nid)
        conn.execute(
            "UPDATE synapses SET last_accessed_at = ? WHERE id_a = ? AND id_b = ?",
            (now, a, b),
        )

    conn.commit()
    conn.close()

    return [dict(r) for r in rows]


def get_neighbors_bulk(memory_ids: list[str], min_weight: float = 0.2, limit: int = 10) -> list[str]:
    """Get unique neighbor IDs for a group of memories, excluding the group itself."""
    seen = set(memory_ids)
    neighbors = []

    for mid in memory_ids:
        for n in get_neighbors(mid, min_weight=min_weight, limit=5):
            nid = n["neighbor_id"]
            if nid not in seen:
                seen.add(nid)
                neighbors.append(nid)
            if len(neighbors) >= limit:
                return neighbors

    return neighbors


def decay_all(factor: float = 0.9) -> dict:
    """Apply global weight decay to all synapses.

    Returns {decayed: int, pruned: int}.
    """
    conn = _connect()
    conn.execute("UPDATE synapses SET weight = weight * ?", (factor,))
    decayed = conn.execute("SELECT changes()").fetchone()[0]

    # Prune synapses below threshold
    conn.execute("DELETE FROM synapses WHERE weight < 0.05")
    pruned = conn.execute("SELECT changes()").fetchone()[0]

    conn.commit()
    conn.close()
    return {"decayed": decayed, "pruned": pruned}


def stats() -> dict:
    """Get network statistics."""
    conn = _connect()
    row = conn.execute(
        """SELECT
            COUNT(*) as total_synapses,
            COALESCE(AVG(weight), 0) as avg_weight,
            COALESCE(MAX(weight), 0) as max_weight,
            COALESCE(SUM(co_activations), 0) as total_activations
           FROM synapses"""
    ).fetchone()
    conn.close()
    return dict(row)


def delete_for_memory(memory_id: str) -> int:
    """Delete all synapses involving a memory (when the memory is deleted)."""
    conn = _connect()
    conn.execute("DELETE FROM synapses WHERE id_a = ? OR id_b = ?", (memory_id, memory_id))
    deleted = conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    conn.close()
    return deleted
