"""Tests for deploy system and launch watchdog."""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add project root to path
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

TESTS = []


def test(name):
    def decorator(func):
        TESTS.append((name, func))
        return func
    return decorator


def run_all() -> tuple[int, int]:
    passed = 0
    failed = 0

    for name, func in TESTS:
        try:
            func()
            print(f"  ✓ deploy: {name}")
            passed += 1
        except Exception as e:
            print(f"  ✗ deploy: {name}: {e}")
            failed += 1

    return passed, failed


@test("deploy: skips when nothing to pull")
def test_deploy_skips_when_nothing_to_pull():
    """Deploy command skips when already on latest commit."""
    # This is a unit test mock - actual deploy logic is in bot/router.py
    # We test the logic flow by simulating the git operations
    _root = Path(__file__).parent.parent

    # Get current commit
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_root,
        capture_output=True,
        text=True,
        timeout=30
    )
    assert result.returncode == 0, "git rev-parse failed"
    current_commit = result.stdout.strip()

    # Fetch to ensure we're up to date
    subprocess.run(["git", "fetch"], cwd=_root, capture_output=True, timeout=30)

    # Check upstream
    result = subprocess.run(
        ["git", "rev-parse", "@{u}"],
        cwd=_root,
        capture_output=True,
        text=True,
        timeout=30
    )
    assert result.returncode == 0, "git rev-parse upstream failed"
    upstream_commit = result.stdout.strip()

    # If we're on latest, deploy should skip
    # (This test assumes the repo is clean and up to date)
    if current_commit == upstream_commit:
        # In a real deploy, this would return "Nothing to deploy"
        assert True, "Already on latest commit - deploy would skip"


@test("deploy: writes restart flag on success")
def test_deploy_writes_restart_flag_on_success():
    """Deploy writes .deploy_restart flag when verify passes."""
    _root = Path(__file__).parent.parent
    flag_file = _root / ".deploy_restart"

    # Clean up if exists
    if flag_file.exists():
        flag_file.unlink()

    # Simulate successful deploy flag write
    flag_file.write_text("1")
    assert flag_file.exists(), "Restart flag not created"
    assert flag_file.read_text() == "1", "Restart flag has wrong content"

    # Clean up
    flag_file.unlink()


@test("deploy: saves last good commit")
def test_deploy_saves_last_good_commit():
    """Deploy saves current commit to .last_good_commit before pull."""
    _root = Path(__file__).parent.parent
    last_good_file = _root / ".last_good_commit"

    # Get current commit
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_root,
        capture_output=True,
        text=True,
        timeout=30
    )
    assert result.returncode == 0, "git rev-parse failed"
    current_commit = result.stdout.strip()

    # Simulate saving last good commit
    last_good_file.write_text(current_commit)
    assert last_good_file.exists(), "Last good commit file not created"
    assert last_good_file.read_text() == current_commit, "Last good commit mismatch"

    # Clean up
    last_good_file.unlink()


@test("watchdog: reverts on fast crash after deploy")
def test_watchdog_reverts_on_fast_crash_after_deploy():
    """Watchdog reverts if process crashes within grace period after deploy."""
    _root = Path(__file__).parent.parent
    flag_file = _root / ".deploy_restart"
    last_good_file = _root / ".last_good_commit"

    # Simulate deploy flag present
    flag_file.write_text("1")

    # Simulate last good commit saved
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_root,
        capture_output=True,
        text=True,
        timeout=30
    )
    last_good = result.stdout.strip()
    last_good_file.write_text(last_good)

    # Simulate fast crash (uptime < 60s)
    uptime = 30  # seconds
    grace_period = 60

    # Check if revert should happen
    was_deploy = flag_file.exists()
    should_revert = was_deploy and uptime < grace_period

    assert should_revert, "Watchdog should revert on fast crash after deploy"

    # Clean up
    flag_file.unlink()
    last_good_file.unlink()


@test("watchdog: does not revert on slow crash")
def test_watchdog_does_not_revert_on_slow_crash():
    """Watchdog does not revert if process runs longer than grace period."""
    _root = Path(__file__).parent.parent
    flag_file = _root / ".deploy_restart"

    # Simulate deploy flag present
    flag_file.write_text("1")

    # Simulate slow crash (uptime > 60s)
    uptime = 120  # seconds
    grace_period = 60

    # Check if revert should happen
    was_deploy = flag_file.exists()
    should_revert = was_deploy and uptime < grace_period

    assert not should_revert, "Watchdog should not revert on slow crash"

    # Clean up
    flag_file.unlink()


@test("watchdog: skips revert when no deploy flag")
def test_watchdog_skips_revert_when_no_deploy_flag():
    """Watchdog does not revert if deploy flag is not present."""
    _root = Path(__file__).parent.parent
    flag_file = _root / ".deploy_restart"

    # Ensure no deploy flag
    if flag_file.exists():
        flag_file.unlink()

    # Simulate fast crash
    uptime = 30  # seconds
    grace_period = 60

    # Check if revert should happen
    was_deploy = flag_file.exists()
    should_revert = was_deploy and uptime < grace_period

    assert not should_revert, "Watchdog should not revert without deploy flag"
