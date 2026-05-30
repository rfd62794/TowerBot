"""Rollback script — revert to last stable commit, verify, restart service."""

import os
import subprocess
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db, get_last_stable_commit, record_deploy, mark_verify_passed, mark_stable
init_db()


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run command and return exit code, stdout, stderr."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_nssm_available() -> bool:
    """Check if NSSM is available in PATH."""
    try:
        subprocess.run(["nssm", "version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    """Rollback to last stable commit."""
    print("Starting rollback...")

    # Step 1: Get last stable commit
    stable = get_last_stable_commit()
    if not stable:
        print("🔴 Rollback failed: no stable commit recorded.")
        sys.exit(1)

    commit_hash = stable["commit_hash"]
    commit_message = stable["commit_message"] or ""
    print(f"Last stable commit: {commit_hash} — {commit_message}")

    # Step 2: Checkout stable commit
    print(f"Checking out {commit_hash}...")
    code, stdout, stderr = run_command(["git", "checkout", commit_hash])
    if code != 0:
        print(f"🔴 Rollback failed: git checkout error: {stderr}")
        sys.exit(1)
    print("Checkout successful")

    # Step 3: Run verify.py
    print("Running verify.py...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        ["uv", "run", "python", "scripts/verify.py"],
        capture_output=True,
        text=True,
        env=env,
        cwd=_root,
    )
    code = result.returncode
    verify_output = result.stdout.strip() or result.stderr.strip()
    print(verify_output)

    # Step 4a: Verify passes
    if code == 0:
        deploy_id = record_deploy(commit_hash, f"rollback: {commit_message}")
        mark_verify_passed(deploy_id)
        mark_stable(deploy_id)

        if check_nssm_available():
            run_command(["nssm", "restart", "PrivyBot"])
            print(f"↩️ Rolled back to {commit_hash[:7]} — {commit_message}. Service restarted.")
        else:
            print(f"↩️ Rolled back to {commit_hash[:7]} — {commit_message}. NSSM not available.")
        sys.exit(0)

    # Step 4b: Verify fails even on stable commit
    else:
        print(f"🔴 Rollback failed. Stable commit {commit_hash[:7]} also failing verify.")
        print("Manual intervention needed.")
        print(f"verify.py output:\n{verify_output}")
        sys.exit(1)


if __name__ == "__main__":
    main()
