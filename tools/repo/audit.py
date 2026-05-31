"""
tools/repo/audit.py

Repository compliance audit for PrivyBot self-analysis.
Reads ADRs, SDDs, ROADMAP, commits, test status.
No external APIs. No caching.
"""

import re
import subprocess
import os
from pathlib import Path
from datetime import datetime, timedelta

PRIVYBOT_REPO = Path(os.environ.get("PRIVYBOT_REPO_PATH", "C:/Github/PrivyBot"))


def audit_repo_compliance() -> dict:
    """
    Audit PrivyBot repository for compliance with ADR/SDD documentation.
    
    Returns:
        {
            "ok": bool,
            "test_floor": {"passing": int, "required": int, "status": str},
            "phase_status": {"current": str, "completion": str},
            "spec_drift": [{"adr": str, "issue": str}, ...],
            "doc_currency": [{"sdd": str, "last_modified": str, "last_commit": str}, ...],
            "constitutional_violations": [{"principle": str, "violation": str}, ...],
            "what_is_built": str,
            "what_is_next": str,
            "error": str (if ok=False)
        }
    """
    try:
        # Get test floor status from verify.py
        test_floor = _get_test_floor_status()
        
        # Get phase status from ROADMAP.md
        phase_status = _get_phase_status()
        
        # Check for spec drift (ADRs referencing unbuilt features)
        spec_drift = _check_spec_drift()
        
        # Check documentation currency (SDDs vs commits)
        doc_currency = _check_doc_currency()
        
        # Check for constitutional violations (stop rules, scope creep)
        constitutional_violations = _check_constitutional_violations()
        
        # Get what_is_built and what_is_next from ROADMAP
        what_is_built, what_is_next = _get_roadmap_summary()
        
        return {
            "ok": True,
            "test_floor": test_floor,
            "phase_status": phase_status,
            "spec_drift": spec_drift,
            "doc_currency": doc_currency,
            "constitutional_violations": constitutional_violations,
            "what_is_built": what_is_built,
            "what_is_next": what_is_next,
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_test_floor_status() -> dict:
    """Get current test floor status by running verify.py."""
    try:
        result = subprocess.run(
            ["uv", "run", "python", "scripts/verify.py"],
            capture_output=True,
            text=True,
            cwd=str(PRIVYBOT_REPO),
            timeout=60
        )
        
        # Parse output for test count
        output = result.stdout + result.stderr
        match = re.search(r'(\d+)/(\d+) passed', output)
        if match:
            passing = int(match.group(1))
            required = int(match.group(2))
            status = "ok" if passing == required else "fail"
            return {"passing": passing, "required": required, "status": status}
        
        return {"passing": 0, "required": 0, "status": "unknown"}
    
    except Exception:
        return {"passing": 0, "required": 0, "status": "error"}


def _get_phase_status() -> dict:
    """Get current phase status from ROADMAP.md."""
    try:
        roadmap_path = PRIVYBOT_REPO / "docs" / "ROADMAP.md"
        if not roadmap_path.exists():
            return {"current": "unknown", "completion": "unknown"}
        
        content = roadmap_path.read_text(encoding="utf-8")
        
        # Look for current phase table
        match = re.search(r'\*\*Current Phase:\*\*\s*(.+)', content, re.IGNORECASE)
        if match:
            current = match.group(1).strip()
        else:
            current = "unknown"
        
        # Look for completion percentage
        match = re.search(r'(\d+)%\s*complete', content, re.IGNORECASE)
        if match:
            completion = match.group(1) + "%"
        else:
            completion = "unknown"
        
        return {"current": current, "completion": completion}
    
    except Exception:
        return {"current": "unknown", "completion": "unknown"}


def _check_spec_drift() -> list:
    """Check for ADRs referencing unbuilt features."""
    drift = []
    
    try:
        adr_dir = PRIVYBOT_REPO / "docs" / "adr"
        if not adr_dir.exists():
            return drift
        
        for adr_file in adr_dir.glob("*.md"):
            content = adr_file.read_text(encoding="utf-8")
            
            # Look for ADRs that mention "unimplemented", "TODO", "not yet built"
            if re.search(r'unimplemented|TODO|not yet built|pending', content, re.IGNORECASE):
                drift.append({
                    "adr": adr_file.name,
                    "issue": "References unbuilt feature"
                })
    
    except Exception:
        pass
    
    return drift


def _check_doc_currency() -> list:
    """Check SDDs for staleness vs recent commits."""
    stale = []
    
    try:
        sdd_dir = PRIVYBOT_REPO / "docs" / "sdd"
        if not sdd_dir.exists():
            return stale
        
        # Get last commit date
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ci"],
                capture_output=True,
                text=True,
                cwd=str(PRIVYBOT_REPO)
            )
            last_commit_date = datetime.strptime(result.stdout.strip()[:19], "%Y-%m-%d %H:%M:%S")
        except:
            last_commit_date = datetime.now()
        
        for sdd_file in sdd_dir.glob("*.md"):
            stat = sdd_file.stat()
            sdd_date = datetime.fromtimestamp(stat.st_mtime)
            
            # If SDD is older than 30 days, flag as potentially stale
            if (last_commit_date - sdd_date).days > 30:
                stale.append({
                    "sdd": sdd_file.name,
                    "last_modified": sdd_date.isoformat(),
                    "last_commit": last_commit_date.isoformat()
                })
    
    except Exception:
        pass
    
    return stale


def _check_constitutional_violations() -> list:
    """Check for stop rule violations and scope creep."""
    violations = []
    
    try:
        # Check for TODO/FIXME in critical files
        critical_files = [
            "privybot.py",
            "bot/agent.py",
            "bot/router.py",
            "bot/transport.py"
        ]
        
        for file_path in critical_files:
            full_path = PRIVYBOT_REPO / file_path
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8")
                if re.search(r'TODO|FIXME|HACK|XXX', content):
                    violations.append({
                        "principle": "Code Quality",
                        "violation": f"TODO/FIXME found in {file_path}"
                    })
    
    except Exception:
        pass
    
    return violations


def _get_roadmap_summary() -> tuple:
    """Get what_is_built and what_is_next from ROADMAP.md."""
    try:
        roadmap_path = PRIVYBOT_REPO / "docs" / "ROADMAP.md"
        if not roadmap_path.exists():
            return "Unknown", "Unknown"
        
        content = roadmap_path.read_text(encoding="utf-8")
        
        # Look for "What is built" section
        match = re.search(r'##\s*What is built\s*(.+?)(?=##|$)', content, re.DOTALL | re.IGNORECASE)
        if match:
            what_is_built = match.group(1).strip()[:500]  # Truncate
        else:
            what_is_built = "Not found in ROADMAP"
        
        # Look for "What is next" section
        match = re.search(r'##\s*What is next\s*(.+?)(?=##|$)', content, re.DOTALL | re.IGNORECASE)
        if match:
            what_is_next = match.group(1).strip()[:500]  # Truncate
        else:
            what_is_next = "Not found in ROADMAP"
        
        return what_is_built, what_is_next
    
    except Exception:
        return "Error reading ROADMAP", "Error reading ROADMAP"
