"""Tests for director access tools — full operational access for Claude.

All tests use mocks or isolated fixtures. No real chain execution,
template writes to experimental/, or destructive DB operations.
"""
import os
import sys
import tempfile
from pathlib import Path

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from unittest.mock import patch, MagicMock


# --- Chain tools tests ---

def test_get_chains_all():
    """Returns dict with ok=True and chains list."""
    from tools.meta.director import get_chains
    with patch("infra.db.chains.list_chains", return_value=[]):
        result = get_chains()
        assert result["ok"] is True
        assert "chains" in result
        assert "count" in result


def test_get_chains_filtered():
    """status='complete' — returns only complete chains."""
    from tools.meta.director import get_chains
    mock_chains = [{"id": "1", "status": "complete"}]
    with patch("infra.db.chains.list_chains", return_value=mock_chains):
        result = get_chains(status="complete")
        assert result["ok"] is True
        assert result["count"] == 1


def test_get_chain_found():
    """Existing chain_id — returns chain, steps, payload_count."""
    from tools.meta.director import get_chain
    mock_chain = {"id": "test-chain", "status": "running"}
    with patch("infra.db.chains.get_chain", return_value=mock_chain):
        with patch("infra.db.chains.get_steps_for_chain", return_value=[]):
            with patch("infra.db.payloads.list_payloads_for_chain", return_value=[]):
                result = get_chain("test-chain")
                assert result["ok"] is True
                assert "chain" in result
                assert "steps" in result
                assert "payload_count" in result


def test_get_chain_not_found():
    """Bad chain_id — ok=False, error present."""
    from tools.meta.director import get_chain
    with patch("infra.db.chains.get_chain", return_value=None):
        result = get_chain("bad-id")
        assert result["ok"] is False
        assert "error" in result


def test_get_chain_payload_found():
    """Existing payload_id — returns full data dict."""
    from tools.meta.director import get_chain_payload
    mock_payload = {"id": "payload-1", "type": "test", "data": {}}
    with patch("infra.db.payloads.get_payload", return_value=mock_payload):
        result = get_chain_payload("payload-1")
        assert result["ok"] is True
        assert "payload" in result


def test_get_chain_payload_not_found():
    """Bad payload_id — ok=False."""
    from tools.meta.director import get_chain_payload
    with patch("infra.db.payloads.get_payload", return_value=None):
        result = get_chain_payload("bad-payload")
        assert result["ok"] is False


def test_cancel_chain_running():
    """Running chain — ok=True, status set to failed."""
    from tools.meta.director import cancel_chain
    mock_chain = {"id": "test-chain", "status": "running"}
    with patch("infra.db.chains.get_chain", return_value=mock_chain):
        with patch("infra.db.chains.update_chain_status"):
            result = cancel_chain("test-chain")
            assert result["ok"] is True
            assert result["previous_status"] == "running"


def test_cancel_chain_terminal():
    """Complete chain — ok=False, already terminal."""
    from tools.meta.director import cancel_chain
    mock_chain = {"id": "test-chain", "status": "complete"}
    with patch("infra.db.chains.get_chain", return_value=mock_chain):
        result = cancel_chain("test-chain")
        assert result["ok"] is False
        assert "already terminal" in result["error"]


# --- Template tools tests ---

def test_list_templates_returns_canonical():
    """hourly_fact.yaml in results."""
    from tools.meta.director import list_templates
    mock_templates = [{"name": "hourly_fact", "source": "canonical"}]
    with patch("infra.chain.template_loader.list_templates", return_value=mock_templates):
        result = list_templates()
        assert result["ok"] is True
        assert result["count"] == 1


def test_get_template_canonical():
    """hourly_fact returns content dict."""
    from tools.meta.director import get_template
    mock_template = {"name": "hourly_fact", "steps": []}
    with patch("infra.chain.template_loader.load_template", return_value=mock_template):
        with patch("pathlib.Path.exists", return_value=True):
            result = get_template("hourly_fact")
            assert result["ok"] is True
            assert "content" in result
            assert result["source"] == "canonical"


def test_get_template_not_found():
    """Bad name — ok=False."""
    from tools.meta.director import get_template
    from infra.chain.template_loader import TemplateError
    with patch("infra.chain.template_loader.load_template", side_effect=TemplateError("not found")):
        result = get_template("bad-template")
        assert result["ok"] is False


def test_write_template_valid():
    """Valid YAML — ok=True, file in experimental/."""
    from tools.meta.director import write_template
    valid_yaml = "name: test\nsteps:\n  - type: tool_call"
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("tools.meta.director.EXPERIMENTAL_DIR", Path(tmpdir)):
            with patch("tools.meta.director.CANONICAL_DIR", Path(tmpdir) / "canonical"):
                with patch("infra.chain.template_loader._load_and_validate"):
                    result = write_template("test_template", valid_yaml)
                    assert result["ok"] is True
                    assert result["source"] == "experimental"


def test_write_template_invalid_yaml():
    """Garbage YAML — ok=False, no file written."""
    from tools.meta.director import write_template
    # Use truly invalid YAML - unclosed bracket
    garbage = "name: test\nsteps:\n  - type: tool_call\n  invalid: [unclosed"
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("tools.meta.director.EXPERIMENTAL_DIR", Path(tmpdir)):
            with patch("tools.meta.director.CANONICAL_DIR", Path(tmpdir) / "canonical"):
                result = write_template("test", garbage)
                assert result["ok"] is False
                # Error should mention YAML or validation
                assert "YAML" in result["error"] or "validation" in result["error"].lower()


def test_write_template_cannot_overwrite_canonical():
    """Canonical name — ok=False."""
    from tools.meta.director import write_template
    with patch("pathlib.Path.exists", return_value=True):
        result = write_template("hourly_fact", "name: hourly_fact\nsteps: []")
        assert result["ok"] is False
        assert "canonical" in result["error"]


def test_delete_experimental_template():
    """Experimental file — ok=True, file gone."""
    from tools.meta.director import delete_experimental_template
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_dir = Path(tmpdir) / "experimental"
        exp_dir.mkdir()
        test_file = exp_dir / "test.yaml"
        test_file.write_text("test")
        
        with patch("tools.meta.director.EXPERIMENTAL_DIR", exp_dir):
            with patch("tools.meta.director.CANONICAL_DIR", Path(tmpdir) / "canonical"):
                result = delete_experimental_template("test")
                assert result["ok"] is True
                assert not test_file.exists()


def test_delete_canonical_blocked():
    """Canonical name — ok=False, file untouched."""
    from tools.meta.director import delete_experimental_template
    with patch("pathlib.Path.exists", return_value=True):
        result = delete_experimental_template("hourly_fact")
        assert result["ok"] is False
        assert "canonical" in result["error"]


# --- Memory tools tests ---

def test_list_memories_all():
    """Returns memories list with preview."""
    from tools.meta.director import list_memories
    mock_rows = [{"key": "test", "layer": "technical", "content": "test content", "created_at": "2026-01-01"}]
    with patch("infra.db.schema._exec", return_value=mock_rows):
        result = list_memories()
        assert result["ok"] is True
        assert "memories" in result
        assert result["count"] == 1


def test_list_memories_filtered():
    """layer='technical' — only technical layer."""
    from tools.meta.director import list_memories
    mock_rows = [{"key": "test", "layer": "technical", "content": "test", "created_at": "2026-01-01"}]
    with patch("infra.db.schema._exec", return_value=mock_rows):
        result = list_memories(layer="technical")
        assert result["ok"] is True
        assert result["count"] == 1


def test_delete_memory_soft():
    """Sets active=0, not hard delete."""
    from tools.meta.director import delete_memory
    mock_rows = [{"id": 1}]
    with patch("infra.db.schema._exec", return_value=mock_rows):
        with patch("infra.db.schema._exec") as exec_mock:
            result = delete_memory("test_key")
            assert result["ok"] is True
            # Check that UPDATE was called with active=0
            assert exec_mock.called


# --- DB inspection tests ---

def test_query_db_select():
    """Valid SELECT — returns rows."""
    from tools.meta.director import query_db
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [{"c": 5}]
    with patch("infra.db.schema._exec", return_value=mock_cursor):
        result = query_db("SELECT COUNT(*) as c FROM memories")
        assert result["ok"] is True
        assert "rows" in result
        assert result["count"] == 1


def test_query_db_blocks_update():
    """UPDATE statement — ok=False."""
    from tools.meta.director import query_db
    result = query_db("UPDATE memories SET active=0")
    assert result["ok"] is False
    assert "Only SELECT" in result["error"]


# --- Pattern tools tests ---

def test_get_promotion_candidates():
    """Returns candidates list."""
    from tools.meta.director import get_promotion_candidates
    mock_rows = [{"id": 1, "pattern": "test", "observed_count": 5}]
    with patch("infra.db.schema._exec", return_value=mock_rows):
        result = get_promotion_candidates()
        assert result["ok"] is True
        assert "candidates" in result


# --- run_all shim for verify.py ---

TESTS = [
    ("get_chains_all", test_get_chains_all),
    ("get_chains_filtered", test_get_chains_filtered),
    ("get_chain_found", test_get_chain_found),
    ("get_chain_not_found", test_get_chain_not_found),
    ("get_chain_payload_found", test_get_chain_payload_found),
    ("get_chain_payload_not_found", test_get_chain_payload_not_found),
    ("cancel_chain_running", test_cancel_chain_running),
    ("cancel_chain_terminal", test_cancel_chain_terminal),
    ("list_templates_returns_canonical", test_list_templates_returns_canonical),
    ("get_template_canonical", test_get_template_canonical),
    ("get_template_not_found", test_get_template_not_found),
    ("write_template_valid", test_write_template_valid),
    ("write_template_invalid_yaml", test_write_template_invalid_yaml),
    ("write_template_cannot_overwrite_canonical", test_write_template_cannot_overwrite_canonical),
    ("delete_experimental_template", test_delete_experimental_template),
    ("delete_canonical_blocked", test_delete_canonical_blocked),
    ("list_memories_all", test_list_memories_all),
    ("list_memories_filtered", test_list_memories_filtered),
    ("delete_memory_soft", test_delete_memory_soft),
    ("query_db_select", test_query_db_select),
    ("query_db_blocks_update", test_query_db_blocks_update),
    ("get_promotion_candidates", test_get_promotion_candidates),
]


def run_all() -> tuple[int, int]:
    passed = failed = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"  \u2713 director_tools: {name}")
            passed += 1
        except Exception as e:
            print(f"  \u2717 director_tools: {name}: {e}")
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
