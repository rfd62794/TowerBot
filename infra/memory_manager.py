"""MemoryManager — dual SQLite + Chroma semantic search.

Wraps infra.db.memory CRUD with synchronous Chroma upserts.
- SQLite is source of truth for writes
- Chroma provides semantic similarity for get_memories
- Chroma write failures are logged but do not roll back SQLite
- Chroma read errors fall back to SQLite LIKE
"""

import logging
import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from infra.db.memory import (
    save_memory as _sql_save,
    update_memory as _sql_update,
    retire_memory as _sql_retire,
    get_memories as _sql_get_memories,
)

logger = logging.getLogger("privy.memory")

# Ollama embedding config
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"
COLLECTION_NAME = "privybot"
CHROMA_PATH = Path(__file__).parent.parent / "privy_chroma_db"


class MemoryManager:
    """Singleton manager for dual SQLite + Chroma memory operations."""

    _instance = None
    _client = None
    _collection = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _collection(self):
        """Lazy init Chroma client and collection."""
        if self._collection is None:
            self._client = chromadb.PersistentClient(path=str(CHROMA_PATH))
            embedding_fn = OllamaEmbeddingFunction(
                url=f"{OLLAMA_HOST}/api/embeddings",
                model_name=EMBED_MODEL,
            )
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_fn,
            )
        return self._collection

    def save(self, key: str, content: str, layer: str) -> None:
        """Save to SQLite and upsert to Chroma."""
        _sql_save(key, content, layer)
        try:
            col = self._collection()
            col.upsert(
                ids=[key],
                documents=[content],
                metadatas=[{"layer": layer, "key": key}],
            )
        except Exception as e:
            logger.warning("Chroma upsert failed for key=%s: %s", key, e)

    def update(self, key: str, content: str) -> None:
        """Update SQLite and upsert to Chroma (upsert, not update — idempotent)."""
        _sql_update(key, content)
        try:
            col = self._collection()
            # upsert (not update) — col.update() raises ValueError if ID absent
            # (any memory created before migration or after a Chroma reset)
            col.upsert(
                ids=[key],
                documents=[content],
                metadatas=[{"key": key}],  # layer unchanged
            )
        except Exception as e:
            logger.warning("Chroma upsert failed for key=%s: %s", key, e)

    def retire(self, key: str) -> None:
        """Retire in SQLite and hard-delete from Chroma."""
        _sql_retire(key)
        try:
            col = self._collection()
            col.delete(ids=[key])
        except Exception as e:
            logger.warning("Chroma delete failed for key=%s: %s", key, e)

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Semantic search via Chroma, fallback to SQLite LIKE on error."""
        try:
            col = self._collection()
            results = col.query(query_texts=[query], n_results=limit)
            if not results["ids"] or not results["ids"][0]:
                return []
            memories = []
            for i, doc_id in enumerate(results["ids"][0]):
                memories.append({
                    "key": doc_id,
                    "content": results["documents"][0][i],
                    "layer": results["metadatas"][0][i].get("layer", "unknown"),
                })
            return memories
        except Exception as e:
            logger.warning("Chroma search failed, falling back to SQLite LIKE: %s", e)
            return _sql_get_memories(query, limit)


memory_manager = MemoryManager()
