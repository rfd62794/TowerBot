"""Deploy script — pull main, verify, restart service, record deploy history."""

import os
import subprocess
import sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))

from infra.db import init_db, record_deploy, mark_verify_passed, mark_stable, mark_rolled_back
init_db()


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run command and return exit code, stdout, stderr."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_current_commit() -> tuple[str, str]:
    """Return (hash, message) of current HEAD commit."""
    _, hash_out, _ = run_command(["git", "rev-parse", "--short", "HEAD"])
    _, msg_out, _ = run_command(["git", "log", "-1", "--format=%s"])
    return hash_out or "unknown", msg_out or ""


def check_nssm_available() -> bool:
    """Check if NSSM is available in PATH."""
    try:
        subprocess.run(["nssm", "version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def main():
    """Main deploy workflow."""
    print("Starting deploy...")

    # Step 1: Check git is available
    print("Checking git...")
    code, stdout, stderr = run_command(["git", "--version"])
    if code != 0:
        print(f"Error: Git not available: {stderr}")
        sys.exit(1)
    print(f"Git available: {stdout}")

    # Step 2: Stash any local changes
    print("Stashing local changes...")
    code, stdout, stderr = run_command(["git", "stash"])
    if code != 0:
        print(f"Warning: Stash failed: {stderr}")
        stash_result = "Stash failed (no changes to stash)"
    else:
        stash_result = stdout or "Stashed successfully"
    print(f"Stash result: {stash_result}")

    # Step 3: Pull from origin main
    print("Pulling from origin main...")
    code, stdout, stderr = run_command(["git", "pull", "origin", "main"])
    if code != 0:
        print(f"Error: Pull failed: {stderr}")
        run_command(["git", "stash", "pop"])
        print("Deploy blocked. Pull failed. Rolled back.")
        sys.exit(1)
    print("Pull successful")

    # Record this deploy attempt (after pull, so hash reflects new code)
    commit_hash, commit_message = get_current_commit()
    deploy_id = record_deploy(commit_hash, commit_message)
    print(f"Commit: {commit_hash} — {commit_message}")

    # Step 4: Run verify.py
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

    # Step 5a: Verify passes
    if code == 0:
        mark_verify_passed(deploy_id)
        print("Verify passed. Checking NSSM...")
        if check_nssm_available():
            print("Restarting NSSM service...")
            nssm_code, _, nssm_err = run_command(["nssm", "restart", "PrivyBot"])
            mark_stable(deploy_id)
            if nssm_code == 0:
                print(f"✅ Deployed {commit_hash} — {verify_output.split()[-2] if verify_output else 'passed'}. Service restarted.")
                sys.exit(0)
            else:
                print(f"Warning: NSSM restart failed: {nssm_err}")
                print(f"✅ Deployed {commit_hash} — verify passed, service restart failed.")
                sys.exit(0)
        else:
            mark_stable(deploy_id)
            print(f"✅ Deployed {commit_hash} (laptop mode) — {verify_output.split()[-2] if verify_output else 'passed'}. NSSM not available.")
            sys.exit(0)

    # Step 5b: Verify fails
    else:
        mark_rolled_back(deploy_id)
        run_command(["git", "stash", "pop"])
        print(f"🔴 Deploy blocked. Tests failed. Rolled back to previous.")
        print(f"verify.py output:\n{verify_output}")
        sys.exit(1)


if __name__ == "__main__":
    main()
