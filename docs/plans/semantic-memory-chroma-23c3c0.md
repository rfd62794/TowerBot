# Semantic Memory via Chroma + nomic-embed-text

Replace SQLite `LIKE` search in `get_memories()` with vector similarity search via a local Chroma collection, keeping SQLite as the write source of truth with synchronous dual writes to Chroma.

---

## Architecture

```
tool_save_memory / update / retire
        │
        ▼
infra/memory_manager.py  ← new MemoryManager singleton
        │
        ├── SQLite  (infra/db/memory.py)   ← unchanged CRUD
        └── Chroma  (./privy_chroma_db/)   ← upsert / delete

tool_get_memories
        │
        ▼
memory_manager.search(query)  ← Chroma similarity query
        fallback: SQLite LIKE  (if Chroma errors)
```

**Chroma document structure:**
- `id` = memory key (unique slug)
- `document` = content
- `metadata` = `{"layer": ..., "key": ...}`
- Embedder: `OllamaEmbeddingFunction` from `chromadb.utils.embedding_functions`
  ```python
  from chromadb.utils.embedding_functions import OllamaEmbeddingFunction
  ef = OllamaEmbeddingFunction(
      url="http://localhost:11434/api/embeddings",
      model_name="nomic-embed-text"
  )
  ```
- Collection name: `privybot`
- Persist path: `./privy_chroma_db/`

**Retire = hard delete from Chroma** (not soft). Soft-deleted SQLite rows must not resurface in semantic search.

**Resilience:** Chroma write errors are caught + logged as warnings — SQLite write never rolls back due to Chroma failure. Chroma read errors fall back to SQLite LIKE.

---

## Steps

### Step 1 — Install dependency
```
uv add chromadb
```

### Step 2 — `infra/memory_manager.py` (new)
```python
class MemoryManager:
    _instance = None

    def _collection(self): ...  # lazy init: PersistentClient + get_or_create_collection

    def save(self, key, content, layer):
        _sql_save(key, content, layer)
        try: col.upsert(ids=[key], documents=[content], metadatas=[...])
        except Exception: logger.warning(...)

    def update(self, key, content):
        _sql_update(key, content)
        # upsert (not update) — col.update() raises ValueError if ID absent
        # (any memory created before migration or after a Chroma reset)
        try: col.upsert(ids=[key], documents=[content], metadatas=[...])
        except Exception: logger.warning(...)

    def retire(self, key):
        _sql_retire(key)
        try: col.delete(ids=[key])
        except Exception: logger.warning(...)

    def search(self, query, limit=5) -> list[dict]:
        try:
            results = col.query(query_texts=[query], n_results=limit)
            # map distances → list[{key, content, layer}]
        except Exception:
            logger.warning("Chroma unavailable, falling back to SQLite LIKE")
            return _sql_get_memories(query, limit)

memory_manager = MemoryManager()  # singleton
```

### Step 3 — `bot/memory.py` — route through `memory_manager`
- `tool_save_memory` → `memory_manager.save(...)`
- `tool_update_memory` → `memory_manager.update(...)`
- `tool_retire_memory` → `memory_manager.retire(...)`
- `tool_get_memories` → `memory_manager.search(...)`

`infra/db/memory.py` is **not changed** — `memory_manager` imports it for the SQL half.

### Step 4 — Migration script `scripts/migrate_memories_to_chroma.py`
- Reads all `active=1` memories from SQLite
- `memory_manager._collection().upsert(...)` for each
- Idempotent (safe to re-run; upsert never duplicates)
- Prints progress: `Migrated N memories → Chroma`

### Step 5 — Tests `tests/test_memory_semantic.py` (4 new)
All tests use an **in-memory Chroma client** (`chromadb.EphemeralClient`) and a **mock embedding function** (returns fixed `[0.1]*384`) — no live Ollama needed.

| Test | Verifies |
|------|----------|
| `test_semantic_save_and_search` | save → `search()` returns that memory |
| `test_semantic_update_mirrors_chroma` | update → Chroma doc reflects new content |
| `test_semantic_retire_deletes_from_chroma` | retire → not returned by search |
| `test_semantic_fallback_on_chroma_error` | Chroma raises → returns SQLite LIKE results |

Existing `tests/test_memory.py` tests are **not changed** — they still test tool shape and SQLite CRUD; `MemoryManager` Chroma calls are patched out via the mock embedding function and temp collection.

### Step 6 — Verify
```
uv run python scripts/migrate_memories_to_chroma.py
uv run python scripts/verify.py   # target: 318/318
```

---

## Scope boundaries

| In scope | Out of scope |
|----------|--------------|
| `infra/memory_manager.py` (new) | mem0ai |
| `bot/memory.py` (route through manager) | Changing SQLite schema |
| `scripts/migrate_memories_to_chroma.py` (new) | Async Chroma writes |
| `tests/test_memory_semantic.py` (new) | Auto-extraction from conversations |
| `scripts/verify.py` (+1 file) | OllamaSwapManager changes |

---

## Risk note
`nomic-embed-text` and `gemma3:4b` share the same Ollama instance. Embed calls use `/api/embeddings`; classification uses `/api/chat`. Ollama handles these concurrently without model swapping (embedding models are separate). No lock changes needed.
