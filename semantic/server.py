#!/usr/bin/env python3
"""MCP Server for semantic memory using ChromaDB with local embeddings."""

import json
import os
import sys
import uuid
from datetime import datetime, timezone

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import chromadb
from mcp.server.fastmcp import FastMCP

# --- Config ---
DATA_DIR = os.path.join(_SCRIPT_DIR, "data")
COLLECTION_NAME = "memory"
DEFAULT_N_RESULTS = 10
DEFAULT_MIN_SCORE = 0.7

# --- ChromaDB ---
client = chromadb.PersistentClient(path=DATA_DIR)
_collection = None


def get_collection():
    """Get or refresh collection reference. Handles recreation after --clear."""
    global _collection
    try:
        if _collection is not None:
            # Test if the cached reference is still valid
            _collection.count()
            return _collection
    except Exception:
        _collection = None

    _collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection

# --- MCP Server ---
mcp = FastMCP(
    "memory",
    instructions="Semantic memory: save and search context across sessions",
)


@mcp.tool()
def save_context(
    content: str,
    tags: list[str] | None = None,
    source: str = "claude",
    session_id: str | None = None,
    role: str = "assistant",
) -> str:
    """Save a piece of context to semantic memory.

    Args:
        content: The text content to save (prefer compact summaries over raw text).
        tags: Optional list of tags for filtering (e.g. ["alias", "debug", "architecture"]).
        source: Origin of the content — "claude", "user", "memory-file", etc.
        session_id: Optional session identifier to group related memories.
        role: Who produced this content — "user", "assistant", "system".
    """
    doc_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    metadata = {
        "timestamp": now,
        "source": source,
        "role": role,
        "session_id": session_id or "",
        "tags": json.dumps(tags or []),
    }

    get_collection().add(
        documents=[content],
        metadatas=[metadata],
        ids=[doc_id],
    )

    return json.dumps({"status": "saved", "id": doc_id, "timestamp": now})


@mcp.tool()
def search_context(
    query: str,
    n_results: int = DEFAULT_N_RESULTS,
    min_score: float = DEFAULT_MIN_SCORE,
    source: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """Search semantic memory for relevant context.

    Args:
        query: Natural language query to search for.
        n_results: Max number of results to return (default 10).
        min_score: Minimum similarity score 0-1, higher = more relevant (default 0.7).
        source: Filter by source ("claude", "memory-file", etc). None = all sources.
        tags: Filter results that contain ANY of these tags.
    """
    where_filter = None
    if source:
        where_filter = {"source": source}

    results = get_collection().query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    filtered = []
    for doc_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
        # ChromaDB cosine distance: 0 = identical, 2 = opposite
        # Convert to similarity score: 1 - (distance / 2)
        score = 1 - (dist / 2)
        if score < min_score:
            continue

        # Tag filtering (client-side since ChromaDB doesn't support JSON array contains)
        if tags:
            doc_tags = json.loads(meta.get("tags", "[]"))
            if not any(t in doc_tags for t in tags):
                continue

        filtered.append({
            "id": doc_id,
            "content": doc,
            "score": round(score, 4),
            "source": meta.get("source", ""),
            "role": meta.get("role", ""),
            "session_id": meta.get("session_id", ""),
            "tags": json.loads(meta.get("tags", "[]")),
            "timestamp": meta.get("timestamp", ""),
        })

    return json.dumps({
        "query": query,
        "total_found": len(filtered),
        "results": filtered,
    })


@mcp.tool()
def list_sources() -> str:
    """List all distinct sources in the memory store, with document counts."""
    all_meta = get_collection().get(include=["metadatas"])["metadatas"]
    sources: dict[str, int] = {}
    for m in all_meta:
        src = m.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    return json.dumps({"total_documents": len(all_meta), "sources": sources})


@mcp.tool()
def delete_context(doc_id: str) -> str:
    """Delete a specific document from memory by its ID.

    Args:
        doc_id: The document ID returned by save_context.
    """
    get_collection().delete(ids=[doc_id])
    from synapses import delete_for_memory
    delete_for_memory(doc_id)
    return json.dumps({"status": "deleted", "id": doc_id})


@mcp.tool()
def strengthen_synapses(memory_ids: list[str], delta: float = 0.1) -> str:
    """Hebbian learning: strengthen connections between memories used together.

    Call this after using multiple memories to answer a question.
    "Neurons that fire together wire together" — co-activated memories
    build stronger connections, improving future retrieval via spreading activation.

    Args:
        memory_ids: List of memory IDs that were co-activated (used together in context).
        delta: Weight increment per pair (default 0.1, max weight is 1.0).
    """
    from synapses import strengthen_group
    count = strengthen_group(memory_ids, delta=delta)
    return json.dumps({"status": "strengthened", "pairs": count, "delta": delta})


@mcp.tool()
def synapse_stats() -> str:
    """Get statistics about the synaptic network (connections between memories)."""
    from synapses import stats
    return json.dumps(stats())


if __name__ == "__main__":
    mcp.run(transport="stdio")
