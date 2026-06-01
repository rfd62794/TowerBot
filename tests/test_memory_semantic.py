"""Tests for semantic memory via Chroma — no live Ollama required.

Uses mock collection to bypass embedding entirely.
"""

import os
import sys
from unittest.mock import MagicMock, patch

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()
from infra.memory_manager import MemoryManager


def test_semantic_save_and_search():
    """save() writes to Chroma; search() returns that memory."""
    manager = MemoryManager()
    # Mock collection that stores data in memory dict
    mock_store = {}

    def mock_upsert(ids, documents, metadatas):
        for i, doc_id in enumerate(ids):
            mock_store[doc_id] = {"content": documents[i], "metadata": metadatas[i]}

    def mock_query(query_texts, n_results):
        # Return all stored items (mock semantic search)
        results = [mock_store[k] for k in mock_store]
        return {
            "ids": [list(mock_store.keys())],
            "documents": [[r["content"] for r in results]],
            "metadatas": [[r["metadata"] for r in results]],
        }

    mock_col = MagicMock()
    mock_col.upsert = mock_upsert
    mock_col.query = mock_query

    with patch.object(manager, "_get_collection", return_value=mock_col), \
         patch("infra.memory_manager._sql_save"), \
         patch("infra.memory_manager._sql_get_memories", return_value=[]):
        manager.save("test_sem_key", "test semantic content xyz", "technical")
        results = manager.search("semantic content", limit=5)

    assert len(results) == 1, f"Expected 1 result, got {len(results)}"
    assert results[0]["key"] == "test_sem_key"
    assert results[0]["content"] == "test semantic content xyz"
    assert results[0]["layer"] == "technical"


def test_semantic_update_mirrors_chroma():
    """update() upserts to Chroma; search returns updated content."""
    manager = MemoryManager()
    mock_store = {}

    def mock_upsert(ids, documents, metadatas):
        for i, doc_id in enumerate(ids):
            mock_store[doc_id] = {"content": documents[i], "metadata": metadatas[i]}

    def mock_query(query_texts, n_results):
        results = [mock_store[k] for k in mock_store]
        return {
            "ids": [list(mock_store.keys())],
            "documents": [[r["content"] for r in results]],
            "metadatas": [[r["metadata"] for r in results]],
        }

    mock_col = MagicMock()
    mock_col.upsert = mock_upsert
    mock_col.query = mock_query

    with patch.object(manager, "_get_collection", return_value=mock_col), \
         patch("infra.memory_manager._sql_save"), \
         patch("infra.memory_manager._sql_update"), \
         patch("infra.memory_manager._sql_get_memories", return_value=[]):
        manager.save("test_update_key", "original content", "project")
        manager.update("test_update_key", "updated content")
        results = manager.search("updated content", limit=5)

    assert len(results) == 1
    assert results[0]["content"] == "updated content"


def test_semantic_retire_deletes_from_chroma():
    """retire() hard-deletes from Chroma; search does not return retired memory."""
    manager = MemoryManager()
    mock_store = {}

    def mock_upsert(ids, documents, metadatas):
        for i, doc_id in enumerate(ids):
            mock_store[doc_id] = {"content": documents[i], "metadata": metadatas[i]}

    def mock_delete(ids):
        for doc_id in ids:
            mock_store.pop(doc_id, None)

    def mock_query(query_texts, n_results):
        results = [mock_store[k] for k in mock_store]
        return {
            "ids": [list(mock_store.keys())],
            "documents": [[r["content"] for r in results]],
            "metadatas": [[r["metadata"] for r in results]],
        }

    mock_col = MagicMock()
    mock_col.upsert = mock_upsert
    mock_col.delete = mock_delete
    mock_col.query = mock_query

    with patch.object(manager, "_get_collection", return_value=mock_col), \
         patch("infra.memory_manager._sql_save"), \
         patch("infra.memory_manager._sql_retire"), \
         patch("infra.memory_manager._sql_get_memories", return_value=[]):
        manager.save("test_retire_key", "to be retired", "personal")
        manager.retire("test_retire_key")
        results = manager.search("retired", limit=5)

    assert len(results) == 0, "Retired memory should not appear in search results"


def test_semantic_fallback_on_chroma_error():
    """Chroma read error falls back to SQLite LIKE."""
    manager = MemoryManager()
    # Patch _collection to raise an error
    mock_col = MagicMock()
    mock_col.query.side_effect = Exception("Chroma unavailable")

    with patch.object(manager, "_get_collection", return_value=mock_col), \
         patch("infra.memory_manager._sql_get_memories") as mock_sql:
        mock_sql.return_value = [
            {"key": "fallback_key", "content": "fallback content", "layer": "technical"}
        ]
        results = manager.search("fallback", limit=5)

    assert len(results) == 1
    assert results[0]["key"] == "fallback_key"
    mock_sql.assert_called_once_with("fallback", 5)


# ── harness ────────────────────────────────────────────────────────────────

TESTS = [
    test_semantic_save_and_search,
    test_semantic_update_mirrors_chroma,
    test_semantic_retire_deletes_from_chroma,
    test_semantic_fallback_on_chroma_error,
]


def run_all() -> tuple[int, int]:
    passed = failed = 0
    for t in TESTS:
        try:
            t()
            print(f"  \u2713 memory_semantic: {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 memory_semantic: {t.__name__}: {e}")
            failed += 1
    return passed, failed


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
