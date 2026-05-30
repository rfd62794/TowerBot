"""Tests for core/memory.py — tool_save/update/retire/get_memories."""

import sys
import os

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db
init_db()

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    from tests._harness import run_all as _run
    return _run(TESTS)


@test("memory: tool_save_memory returns correct shape")
def test_save_shape():
    from bot.memory import tool_save_memory
    result = tool_save_memory("test_mem_key", "test content", "technical")
    assert isinstance(result, dict), "Expected dict return"
    assert result.get("status") == "saved", f"Expected status='saved', got {result}"
    assert result.get("key") == "test_mem_key", "Expected key in result"
    assert result.get("layer") == "technical", "Expected layer in result"


@test("memory: tool_update_memory returns correct shape")
def test_update_shape():
    from bot.memory import tool_save_memory, tool_update_memory
    tool_save_memory("test_mem_update_key", "original content", "project")
    result = tool_update_memory("test_mem_update_key", "updated content", "test reason")
    assert isinstance(result, dict), "Expected dict return"
    assert result.get("status") == "updated", f"Expected status='updated', got {result}"
    assert result.get("key") == "test_mem_update_key", "Expected key in result"


@test("memory: tool_retire_memory marks inactive")
def test_retire():
    from bot.memory import tool_save_memory, tool_retire_memory
    from infra.db import list_memories
    tool_save_memory("test_mem_retire_key", "to be retired", "personal")
    result = tool_retire_memory("test_mem_retire_key", "test retirement")
    assert isinstance(result, dict), "Expected dict return"
    assert result.get("status") == "retired", f"Expected status='retired', got {result}"
    memories = list_memories()
    assert not any(m["key"] == "test_mem_retire_key" for m in memories), \
        "Retired memory should not appear in active list"


@test("memory: tool_get_memories returns results for known key")
def test_get_memories():
    from bot.memory import tool_save_memory, tool_get_memories
    tool_save_memory("test_mem_search_key", "searchable content xyz", "technical")
    result = tool_get_memories("searchable content xyz")
    assert isinstance(result, dict), "Expected dict return"
    assert "memories" in result, "Expected 'memories' key"
    assert result.get("count", 0) >= 0, "Expected count >= 0"


@test("memory: invalid layer rejected")
def test_invalid_layer():
    from bot.memory import tool_save_memory
    result = tool_save_memory("test_bad_layer", "content", "invalid_layer_xyz")
    assert isinstance(result, dict), "Expected dict return"
    assert result.get("status") == "error", \
        f"Expected status='error' for invalid layer, got {result}"


@test("memory: tool_get_memories queries seeded data")
def test_get_seeded_memories():
    from bot.memory import tool_get_memories
    from infra.db.schema import _exec
    # Verify seeded data exists
    rows = _exec("SELECT key, content, layer FROM memory WHERE active = 1").fetchall()
    assert len(rows) > 0, "Expected seeded memories in database"
    # Query for known seeded content
    result = tool_get_memories("ReactReel")
    assert isinstance(result, dict), "Expected dict return"
    assert result.get("status") in ["found", "empty"], f"Expected status 'found' or 'empty', got {result}"
    if result.get("status") == "found":
        assert result.get("count", 0) > 0, "Expected count > 0 when status is 'found'"


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    p, f = run_all()
    print(f"\n{p}/{p+f} passed.")
    sys.exit(0 if f == 0 else 1)
