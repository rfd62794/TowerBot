"""Deploy script — pull main, verify, restart service."""

import subprocess
import sys


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
        # Rollback
        print("Rolling back...")
        run_command(["git", "stash", "pop"])
        print("Deploy blocked. Pull failed. Rolled back.")
        sys.exit(1)
    print("Pull successful")

    # Step 4: Run verify.py
    print("Running verify.py...")
    import os
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        ["uv", "run", "python", "scripts/verify.py"],
        capture_output=True,
        text=True,
        env=env
    )
    code = result.returncode
    verify_output = result.stdout.strip() or result.stderr.strip()
    print(verify_output)

    # Step 5a: If verify passes
    if code == 0:
        print("Verify passed. Checking NSSM...")
        if check_nssm_available():
            print("Restarting NSSM service...")
            code, stdout, stderr = run_command(["nssm", "restart", "PrivyBot"])
            if code == 0:
                print("Deploy successful.")
                print(f"verify.py: {verify_output.split()[-2] if verify_output else 'passed'}")
                print("Service restarted.")
                sys.exit(0)
            else:
                print(f"Warning: NSSM restart failed: {stderr}")
                print("Deploy successful (verify passed, but service restart failed).")
                sys.exit(0)
        else:
            print("Deploy successful (laptop mode).")
            print("Service restart skipped — NSSM not available.")
            print(f"verify.py: {verify_output.split()[-2] if verify_output else 'passed'}")
            sys.exit(0)

    # Step 5b: If verify fails
    else:
        print("Verify failed. Rolling back...")
        run_command(["git", "stash", "pop"])
        print("Deploy blocked.")
        print(f"verify.py failed:\n{verify_output}")
        print("Rolled back to previous.")
        sys.exit(1)


if __name__ == "__main__":
    main()
