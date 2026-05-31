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


@test("analysis: analyze_code_quality returns ok=True")
def test_analyze_code_quality():
    from tools.repo.analysis import analyze_code_quality
    result = analyze_code_quality()
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "complexity" in result, "Expected 'complexity' key"
    assert "testing" in result, "Expected 'testing' key"


@test("analysis: analyze_dependencies returns ok=True")
def test_analyze_dependencies():
    from tools.repo.analysis import analyze_dependencies
    result = analyze_dependencies()
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "load_bearing" in result, "Expected 'load_bearing' key"
    assert "external_deps" in result, "Expected 'external_deps' key"


@test("analysis: find_opportunities returns ok=True")
def test_find_opportunities():
    from tools.repo.analysis import find_opportunities
    result = find_opportunities()
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "opportunities" in result, "Expected 'opportunities' key"
    assert isinstance(result["opportunities"], list), "Expected opportunities to be a list"


@test("analysis: find_opportunities with focus filters results")
def test_find_opportunities_with_focus():
    from tools.repo.analysis import find_opportunities
    result = find_opportunities(focus="Phase 11")
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert result.get("focus") == "Phase 11", "Expected focus to be 'Phase 11'"


@test("analysis: analyze_documentation_alignment returns ok=True")
def test_analyze_documentation_alignment():
    from tools.repo.analysis import analyze_documentation_alignment
    result = analyze_documentation_alignment()
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "sdd_coverage" in result, "Expected 'sdd_coverage' key"


@test("synthesis: inspect_repo returns ok=True")
def test_inspect_repo():
    from tools.repo.synthesis import inspect_repo
    result = inspect_repo()
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "structure" in result, "Expected 'structure' key"
    assert "file_counts" in result, "Expected 'file_counts' key"
    assert "git_status" in result, "Expected 'git_status' key"


@test("synthesis: inspect_repo with format=text returns text")
def test_inspect_repo_text_format():
    from tools.repo.synthesis import inspect_repo
    result = inspect_repo(format="text")
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "text" in result, "Expected 'text' key when format='text'"


@test("synthesis: generate_strategic_analysis returns ok=True")
def test_generate_strategic_analysis():
    from tools.repo.synthesis import generate_strategic_analysis
    result = generate_strategic_analysis()
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert "executive_summary" in result, "Expected 'executive_summary' key"
    assert "test_floor" in result, "Expected 'test_floor' key"
    assert "quick_wins" in result, "Expected 'quick_wins' key"


@test("synthesis: generate_strategic_analysis with context")
def test_generate_strategic_analysis_with_context():
    from tools.repo.synthesis import generate_strategic_analysis
    result = generate_strategic_analysis(context="Phase 15")
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert result.get("context") == "Phase 15", "Expected context to be 'Phase 15'"


@test("directive: read_current_state returns ok=True")
def test_read_current_state():
    from tools.repo.directive import read_current_state
    result = read_current_state()
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"


@test("directive: read_current_state has required keys")
def test_read_current_state_keys():
    from tools.repo.directive import read_current_state
    result = read_current_state()
    assert "updated" in result, "Expected 'updated' key"
    assert "test_floor" in result, "Expected 'test_floor' key"
    assert "current_phase" in result, "Expected 'current_phase' key"
    assert "what_is_next" in result, "Expected 'what_is_next' key"
    assert "recent_commits" in result, "Expected 'recent_commits' key"


@test("directive: read_current_state test_floor has passing count > 0")
def test_read_current_state_test_floor():
    from tools.repo.directive import read_current_state
    result = read_current_state()
    test_floor = result.get("test_floor", {})
    assert test_floor.get("passing", 0) > 0, "Expected passing count > 0"


@test("directive: elaborate_task returns ok=True with description")
def test_elaborate_task():
    from tools.repo.directive import elaborate_task
    result = elaborate_task("Add type hints to API functions")
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"
    assert result.get("task_description") == "Add type hints to API functions", "Expected task_description to match"


@test("directive: elaborate_task related_files is a list")
def test_elaborate_task_related_files():
    from tools.repo.directive import elaborate_task
    result = elaborate_task("Add type hints to API functions")
    related_files = result.get("related_files", [])
    assert isinstance(related_files, list), "Expected related_files to be a list"


@test("directive: generate_directive returns ok=True")
def test_generate_directive():
    from tools.repo.directive import generate_directive
    result = generate_directive()
    assert result.get("ok") == True, f"Expected ok=True, got {result.get('ok')}"


@test("directive: generate_directive has directive_template with title key")
def test_generate_directive_template():
    from tools.repo.directive import generate_directive
    result = generate_directive()
    directive_template = result.get("directive_template", {})
    assert "title" in directive_template, "Expected 'title' key in directive_template"


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
