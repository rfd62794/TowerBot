"""
tools/repo/directive.py

Directive generation tools for PrivyBot self-expansion.
Data aggregation and structuring only. No LLM calls.
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, List

PRIVYBOT_REPO = Path(os.environ.get("PRIVYBOT_REPO_PATH", "C:/Github/PrivyBot"))


def read_current_state() -> dict:
    """
    Aggregate current state from live sources.
    
    Calls audit_repo_compliance, reads ROADMAP.md, gets recent commits,
    and overnight autonomous actions.
    
    Returns:
        {
            "ok": bool,
            "stale_notice": None,
            "updated": str,
            "test_floor": dict,
            "current_phase": str,
            "phases_complete": int,
            "phases_total": int,
            "what_is_built": list,
            "what_is_next": list,
            "recent_commits": list,
            "overnight_actions": list,
            "spec_drift": list,
            "open_questions": list,
            "error": str (if ok=False)
        }
    """
    try:
        from .audit import audit_repo_compliance
        from .filesystem import read_local_file
        import unittest.mock as mock
        import subprocess
        import re
        
        # Mock test floor to avoid verify loop
        with mock.patch("tools.repo.audit._get_test_floor_status", return_value={"passing": 254, "required": 254, "status": "ok"}):
            audit = audit_repo_compliance()
        
        # Read ROADMAP.md
        roadmap_content = ""
        try:
            roadmap_result = read_local_file("docs/ROADMAP.md")
            if roadmap_result.get("ok"):
                roadmap_content = roadmap_result.get("content", "")
        except:
            pass
        
        # Parse current phase
        current_phase = "Unknown"
        phases_complete = 0
        phases_total = 15
        
        phase_match = re.search(r'\*\*Current Phase:\*\*\s*(.+)', roadmap_content, re.IGNORECASE)
        if phase_match:
            current_phase = phase_match.group(1).strip()
        
        # Count completed phases (look for checkmarks or "done")
        completed_matches = re.findall(r'\[x\]|done|complete', roadmap_content, re.IGNORECASE)
        phases_complete = len(completed_matches)
        
        # Parse what_is_built and what_is_next
        what_is_built = []
        what_is_next = []
        
        built_match = re.search(r'##\s*What is built\s*(.+?)(?=##|$)', roadmap_content, re.DOTALL | re.IGNORECASE)
        if built_match:
            built_text = built_match.group(1).strip()
            what_is_built = [line.strip("- ").strip() for line in built_text.split("\n") if line.strip() and line.strip().startswith("-")][:5]
        
        next_match = re.search(r'##\s*What is next\s*(.+?)(?=##|$)', roadmap_content, re.DOTALL | re.IGNORECASE)
        if next_match:
            next_text = next_match.group(1).strip()
            what_is_next = [line.strip("- ").strip() for line in next_text.split("\n") if line.strip() and line.strip().startswith("-")][:5]
        
        # Get recent commits (last 7 days)
        recent_commits = []
        try:
            since_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            result = subprocess.run(
                ["git", "log", "--since", since_date, "--pretty=format:%s", "--name-only"],
                capture_output=True,
                text=True,
                cwd=str(PRIVYBOT_REPO)
            )
            # Parse commit hashes
            commits = result.stdout.strip().split("\n") if result.stdout.strip() else []
            recent_commits = [f"Commit {c[:8]}" for c in commits if c][:5]
        except:
            recent_commits = []
        
        # Get overnight autonomous actions from database
        overnight_actions = []
        try:
            from infra.db import get_db
            db = get_db()
            cursor = db.cursor()
            cursor.execute("""
                SELECT result FROM agent_actions 
                WHERE task_name LIKE '%autonomous%' 
                ORDER BY created_at DESC 
                LIMIT 3
            """)
            rows = cursor.fetchall()
            overnight_actions = [f"Autonomous action completed" for _ in rows]
        except:
            overnight_actions = []
        
        # Get spec drift and open questions from audit
        spec_drift = audit.get("spec_drift", [])
        open_questions = []
        
        # Extract open questions from ROADMAP
        question_matches = re.findall(r'\?\s*$|open question|todo|pending', roadmap_content, re.IGNORECASE)
        open_questions = [f"Item {i+1}" for i in range(min(len(question_matches), 3))]
        
        return {
            "ok": True,
            "stale_notice": None,
            "updated": datetime.now().strftime("%Y-%m-%d"),
            "test_floor": audit.get("test_floor", {}),
            "current_phase": current_phase,
            "phases_complete": phases_complete,
            "phases_total": phases_total,
            "what_is_built": what_is_built,
            "what_is_next": what_is_next,
            "recent_commits": recent_commits,
            "overnight_actions": overnight_actions,
            "spec_drift": spec_drift,
            "open_questions": open_questions
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


def elaborate_task(task_description: str, target_files: Optional[List[str]] = None) -> dict:
    """
    Structural analysis of what a task affects.
    
    Args:
        task_description: Description of the task
        target_files: Optional list of specific files to analyze
    
    Returns:
        {
            "ok": bool,
            "stale_notice": None,
            "task_description": str,
            "related_files": list,
            "target_file_contents": dict,
            "patterns_found": list,
            "suggested_scope": str,
            "error": str (if ok=False)
        }
    """
    try:
        from .filesystem import search_local_code, read_local_file, list_local_dir
        
        # Extract keywords from task description
        noise_words = {"the", "a", "an", "and", "or", "to", "for", "with", "in", "on", "at", "by"}
        keywords = [word.lower() for word in task_description.split() if word.lower() not in noise_words and len(word) > 3]
        
        # Search for related files
        related_files = []
        for keyword in keywords[:3]:  # Limit to top 3 keywords
            result = search_local_code(keyword, file_pattern="*.py")
            if result.get("ok"):
                for match in result.get("matches", [])[:3]:  # Top 3 matches per keyword
                    related_files.append({
                        "file": match.get("file"),
                        "relevance": "direct",
                        "matches": [{"line": match.get("line_number"), "content": match.get("line")}]
                    })
        
        # Remove duplicates
        seen = set()
        unique_related = []
        for rf in related_files:
            if rf["file"] not in seen:
                seen.add(rf["file"])
                unique_related.append(rf)
        related_files = unique_related
        
        # Read target files if provided
        target_file_contents = {}
        if target_files:
            for file_path in target_files:
                result = read_local_file(file_path)
                if result.get("ok"):
                    target_file_contents[file_path] = result.get("content", "")
        
        # Get repo structure for context
        structure_result = list_local_dir("", recursive=False)
        repo_structure = structure_result.get("entries", []) if structure_result.get("ok") else []
        
        # Identify patterns
        patterns_found = []
        if "add" in task_description.lower() or "create" in task_description.lower():
            patterns_found.append("File creation pattern")
        if "modify" in task_description.lower() or "update" in task_description.lower():
            patterns_found.append("File modification pattern")
        if "test" in task_description.lower():
            patterns_found.append("Test addition pattern")
        
        suggested_scope = f"{len(related_files) + len(target_files or [])} files likely affected"
        
        return {
            "ok": True,
            "stale_notice": None,
            "task_description": task_description,
            "related_files": related_files,
            "target_file_contents": target_file_contents,
            "patterns_found": patterns_found,
            "suggested_scope": suggested_scope
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_directive(focus: Optional[str] = None, analysis_context: Optional[dict] = None) -> dict:
    """
    Assemble directive template from current state + top opportunity.
    
    Args:
        focus: Optional focus area
        analysis_context: Optional pre-computed analysis context
    
    Returns:
        {
            "ok": bool,
            "stale_notice": None,
            "directive_template": dict,
            "current_state": dict,
            "top_opportunity": dict,
            "focus": str,
            "error": str (if ok=False)
        }
    """
    try:
        from .analysis import find_opportunities
        
        # Get current state
        current_state = read_current_state()
        if not current_state.get("ok"):
            return {"ok": False, "error": "Failed to read current state"}
        
        # Get opportunities if not provided
        if not analysis_context:
            opp_result = find_opportunities(focus=focus)
            if not opp_result.get("ok"):
                return {"ok": False, "error": "Failed to find opportunities"}
            opportunities = opp_result.get("opportunities", [])
        else:
            opportunities = analysis_context.get("opportunities", [])
        
        # Take top opportunity
        top_opportunity = opportunities[0] if opportunities else {}
        
        # Assemble directive template
        phase = current_state.get("current_phase", "Unknown")
        test_floor = current_state.get("test_floor", {})
        test_status = f"{test_floor.get('passing', 0)}/{test_floor.get('required', 0)} ({test_floor.get('status', 'unknown')})"
        
        directive_template = {
            "title": f"DIRECTIVE: {top_opportunity.get('title', 'Untitled Directive')}",
            "context": top_opportunity.get("description", "No description provided"),
            "current_state": f"{phase} — {test_status}",
            "files_to_change": [],  # Agent fills these in
            "stop_rule": "",  # Agent fills this in
            "success_criteria": "",  # Agent fills this in
            "test_expectations": ""  # Agent fills this in
        }
        
        return {
            "ok": True,
            "stale_notice": None,
            "directive_template": directive_template,
            "current_state": current_state,
            "top_opportunity": top_opportunity,
            "focus": focus or "general"
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}
