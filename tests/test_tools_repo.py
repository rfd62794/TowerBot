"""Tests for tools/repo/filesystem.py"""

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


@test("filesystem: read_local_file returns ok=True for existing file")
def test_read_existing_file():
    from tools.repo.filesystem import read_local_file
    result = read_local_file("privybot.py")
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "content" in result, "Expected 'content' key"
    assert result.get("line_count") > 0, "Expected line_count > 0"


@test("filesystem: read_local_file returns ok=False for non-existent file")
def test_read_nonexistent_file():
    from tools.repo.filesystem import read_local_file
    result = read_local_file("does_not_exist.py")
    assert result.get("ok") == False, f"Expected ok=False, got {result.get('ok')}"
    assert "error" in result, "Expected 'error' key"


@test("filesystem: read_local_file blocks paths outside repo")
def test_read_path_outside_repo():
    from tools.repo.filesystem import read_local_file
    result = read_local_file("../../../etc/passwd")
    assert result.get("ok") == False, f"Expected ok=False for outside path, got {result.get('ok')}"
    assert "outside repository bounds" in result.get("error", ""), "Expected bounds error"


@test("filesystem: list_local_dir returns entries for repo root")
def test_list_repo_root():
    from tools.repo.filesystem import list_local_dir
    result = list_local_dir("")
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "entries" in result, "Expected 'entries' key"
    assert result.get("total_count") > 0, "Expected total_count > 0"


@test("filesystem: list_local_dir recursive=True returns more entries")
def test_list_recursive():
    from tools.repo.filesystem import list_local_dir
    result_non_recursive = list_local_dir("", recursive=False)
    result_recursive = list_local_dir("", recursive=True)
    assert result_recursive.get("total_count") > result_non_recursive.get("total_count"), \
        "Recursive should return more entries"


@test("filesystem: search_local_code finds pattern in code")
def test_search_pattern():
    from tools.repo.filesystem import search_local_code
    result = search_local_code("def main")
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "matches" in result, "Expected 'matches' key"
    assert result.get("total_matches") > 0, "Expected to find 'def main' pattern"


@test("filesystem: search_local_code returns empty for non-existent pattern")
def test_search_no_matches():
    from tools.repo.filesystem import search_local_code
    result = search_local_code("ZZZXYZZZ_NOT_IN_CODE_999999", path="api")
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert result.get("total_matches") == 0, "Expected 0 matches for non-existent pattern"


@test("filesystem: search_local_code respects file_pattern")
def test_search_file_pattern():
    from tools.repo.filesystem import search_local_code
    result = search_local_code("import", file_pattern="*.py")
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    # All matches should be .py files
    for match in result.get("matches", []):
        assert match.get("file", "").endswith(".py"), f"Expected .py file, got {match.get('file')}"


@test("audit: audit_repo_compliance returns ok=True")
def test_audit_repo_compliance():
    from tools.repo.audit import audit_repo_compliance
    import unittest.mock as mock
    # Mock _get_test_floor_status to avoid verify.py subprocess loop
    with mock.patch("tools.repo.audit._get_test_floor_status", return_value={"passing": 239, "required": 239, "status": "ok"}):
        result = audit_repo_compliance()
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "test_floor" in result, "Expected 'test_floor' key"
    assert "phase_status" in result, "Expected 'phase_status' key"
    assert "spec_drift" in result, "Expected 'spec_drift' key"
    assert "doc_currency" in result, "Expected 'doc_currency' key"
    assert "constitutional_violations" in result, "Expected 'constitutional_violations' key"
    assert "what_is_built" in result, "Expected 'what_is_built' key"
    assert "what_is_next" in result, "Expected 'what_is_next' key"


@test("audit: test_floor has passing and required counts")
def test_audit_test_floor():
    from tools.repo.audit import audit_repo_compliance
    import unittest.mock as mock
    with mock.patch("tools.repo.audit._get_test_floor_status", return_value={"passing": 239, "required": 239, "status": "ok"}):
        result = audit_repo_compliance()
    test_floor = result.get("test_floor", {})
    assert "passing" in test_floor, "Expected 'passing' in test_floor"
    assert "required" in test_floor, "Expected 'required' in test_floor"
    assert "status" in test_floor, "Expected 'status' in test_floor"
    assert isinstance(test_floor["passing"], int), "Expected passing to be int"
    assert isinstance(test_floor["required"], int), "Expected required to be int"


@test("audit: phase_status has current and completion")
def test_audit_phase_status():
    from tools.repo.audit import audit_repo_compliance
    import unittest.mock as mock
    with mock.patch("tools.repo.audit._get_test_floor_status", return_value={"passing": 239, "required": 239, "status": "ok"}):
        result = audit_repo_compliance()
    phase_status = result.get("phase_status", {})
    assert "current" in phase_status, "Expected 'current' in phase_status"
    assert "completion" in phase_status, "Expected 'completion' in phase_status"
    assert isinstance(phase_status["current"], str), "Expected current to be str"
    assert isinstance(phase_status["completion"], str), "Expected completion to be str"


@test("audit: spec_drift is a list")
def test_audit_spec_drift():
    from tools.repo.audit import audit_repo_compliance
    import unittest.mock as mock
    with mock.patch("tools.repo.audit._get_test_floor_status", return_value={"passing": 239, "required": 239, "status": "ok"}):
        result = audit_repo_compliance()
    spec_drift = result.get("spec_drift", [])
    assert isinstance(spec_drift, list), "Expected spec_drift to be a list"


@test("audit: doc_currency is a list")
def test_audit_doc_currency():
    from tools.repo.audit import audit_repo_compliance
    import unittest.mock as mock
    with mock.patch("tools.repo.audit._get_test_floor_status", return_value={"passing": 239, "required": 239, "status": "ok"}):
        result = audit_repo_compliance()
    doc_currency = result.get("doc_currency", [])
    assert isinstance(doc_currency, list), "Expected doc_currency to be a list"


@test("audit: constitutional_violations is a list")
def test_audit_constitutional_violations():
    from tools.repo.audit import audit_repo_compliance
    import unittest.mock as mock
    with mock.patch("tools.repo.audit._get_test_floor_status", return_value={"passing": 239, "required": 239, "status": "ok"}):
        result = audit_repo_compliance()
    violations = result.get("constitutional_violations", [])
    assert isinstance(violations, list), "Expected constitutional_violations to be a list"


def run_all():
    passed = 0
    failed = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"✗ {name}")
            print(f"  {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {name}")
            print(f"  Unexpected error: {e}")
            failed += 1
    
    print(f"\n{passed}/{len(TESTS)} passed")
    if failed > 0:
        print(f"{failed} failed")
    return passed, failed
