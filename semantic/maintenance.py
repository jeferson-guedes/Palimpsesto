#!/usr/bin/env python3
"""Manutenção orgânica da memória semântica — roda throttled (1x/dia) a partir do
hook_autosave (Stop). Sem cron externo: acontece sozinha quando o Claude é usado.

Duas tarefas:
1. decay_all() nas sinapses — esquecimento gradual; sinapse que não é co-reativada
   enfraquece e some (já prunada <0.05 dentro de decay_all). Mantém a rede enxuta e
   relevante sem intervenção.
2. prune de dumps `hippocampal` ANTIGOS e NUNCA conectados — o autosave despeja turnos
   inteiros (ruído que dilui a busca). Remove só os que: role=hippocampal + mais velhos
   que PRUNE_DAYS + sem nenhuma sinapse (nunca co-reativados). NUNCA toca em saves
   curados (role!=hippocampal), memory-file ou user. Cap por execução pra ser gradual.

Conservador de propósito: deletar é irreversível, então só remove o que é
comprovadamente ruído frio (velho + nunca útil).
"""

import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_SCRIPT_DIR, "data")
COLLECTION_NAME = "memory"
STAMP_FILE = os.path.join(_SCRIPT_DIR, ".last_maintenance")
SYNAPSE_DB = os.path.join(DATA_DIR, "synapses.db")

THROTTLE_HOURS = 24
DECAY_FACTOR = 0.95      # decay diário gentil (decay_all pruna sinapse <0.05)
PRUNE_DAYS = 90          # só hippocampal mais velho que isso
PRUNE_MAX = 300          # teto por execução — limpeza gradual


def _is_due() -> bool:
    if not os.path.exists(STAMP_FILE):
        return True
    try:
        with open(STAMP_FILE) as f:
            last = datetime.fromisoformat(f.read().strip())
    except (ValueError, OSError):
        return True
    return datetime.now(timezone.utc) - last >= timedelta(hours=THROTTLE_HOURS)


def _touch_stamp():
    try:
        with open(STAMP_FILE, "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())
    except OSError:
        pass


def _connected_ids() -> set:
    """IDs que participam de pelo menos uma sinapse — nunca prunar esses."""
    if not os.path.exists(SYNAPSE_DB):
        return set()
    conn = sqlite3.connect(SYNAPSE_DB)
    try:
        rows = conn.execute("SELECT id_a, id_b FROM synapses").fetchall()
    except sqlite3.Error:
        return set()
    finally:
        conn.close()
    ids = set()
    for a, b in rows:
        ids.add(a)
        ids.add(b)
    return ids


def run_if_due() -> dict | None:
    """Executa manutenção se passou do throttle. Retorna resumo ou None."""
    if not _is_due():
        return None

    summary = {"decay": None, "pruned": 0}

    # 1. Decay das sinapses
    try:
        from synapses import decay_all, delete_for_memory
        summary["decay"] = decay_all(factor=DECAY_FACTOR)
    except Exception as e:
        print(f"mcp-memory maintenance decay error: {e}", file=sys.stderr)
        delete_for_memory = None

    # 2. Prune de dumps hippocampais antigos e desconectados
    try:
        import chromadb

        client = chromadb.PersistentClient(path=DATA_DIR)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"},
        )

        connected = _connected_ids()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=PRUNE_DAYS)).isoformat()

        got = collection.get(where={"role": "hippocampal"}, include=["metadatas"])
        candidates = []
        for doc_id, meta in zip(got.get("ids", []), got.get("metadatas", [])):
            ts = (meta or {}).get("timestamp", "")
            if ts and ts < cutoff and doc_id not in connected:
                candidates.append((ts, doc_id))

        candidates.sort()  # mais antigos primeiro
        to_delete = [doc_id for _, doc_id in candidates[:PRUNE_MAX]]

        if to_delete:
            collection.delete(ids=to_delete)
            if delete_for_memory:
                for doc_id in to_delete:
                    try:
                        delete_for_memory(doc_id)
                    except Exception:
                        pass
            summary["pruned"] = len(to_delete)
    except Exception as e:
        print(f"mcp-memory maintenance prune error: {e}", file=sys.stderr)

    _touch_stamp()
    print(f"mcp-memory maintenance: {summary}", file=sys.stderr)
    return summary


if __name__ == "__main__":
    import json
    # Execução manual: força (ignora throttle) e mostra resumo
    if "--force" in sys.argv and os.path.exists(STAMP_FILE):
        os.remove(STAMP_FILE)
    result = run_if_due()
    print(json.dumps(result, default=str, ensure_ascii=False))
