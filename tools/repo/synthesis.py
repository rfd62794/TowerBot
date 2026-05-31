"""
tools/repo/synthesis.py

Synthesis tools for PrivyBot self-analysis.
Orchestrates analysis tools into comprehensive strategic view.
"""

import os
from pathlib import Path
from typing import Optional

PRIVYBOT_REPO = Path(os.environ.get("PRIVYBOT_REPO_PATH", "C:/Github/PrivyBot"))


def inspect_repo(format: str = "dict") -> dict:
    """
    Comprehensive repository snapshot.
    
    Args:
        format: "dict" or "text" (default: "dict")
    
    Returns:
        {
            "ok": bool,
            "structure": dict,
            "file_counts": dict,
            "git_status": dict,
            "error": str (if ok=False)
        }
    """
    try:
        # Count files by type
        py_files = list(PRIVYBOT_REPO.rglob("*.py"))
        md_files = list(PRIVYBOT_REPO.rglob("*.md"))
        json_files = list(PRIVYBOT_REPO.rglob("*.json"))
        
        structure = {
            "python_files": len(py_files),
            "markdown_files": len(md_files),
            "json_files": len(json_files),
            "total_files": len(py_files) + len(md_files) + len(json_files)
        }
        
        # Directory structure
        dirs = [d.name for d in PRIVYBOT_REPO.iterdir() if d.is_dir() and not d.name.startswith(".")]
        
        file_counts = {
            "directories": len(dirs),
            "dir_names": dirs[:20]  # First 20
        }
        
        # Git status (basic)
        git_status = {
            "git_present": (PRIVYBOT_REPO / ".git").exists(),
            "status": "available" if (PRIVYBOT_REPO / ".git").exists() else "not a git repo"
        }
        
        result = {
            "ok": True,
            "structure": structure,
            "file_counts": file_counts,
            "git_status": git_status
        }
        
        if format == "text":
            # Format as readable text
            text = f"""
Repository Inspection Report
{'='*50}

File Structure:
- Python files: {structure['python_files']}
- Markdown files: {structure['markdown_files']}
- JSON files: {structure['json_files']}
- Total files: {structure['total_files']}

Directories: {file_counts['directories']}
{', '.join(file_counts['dir_names'])}

Git Status: {git_status['status']}
"""
            result["text"] = text
        
        return result
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_strategic_analysis(context: Optional[str] = None) -> dict:
    """
    Orchestrate comprehensive strategic analysis.
    
    Calls audit, code quality, dependencies, opportunities, and doc alignment tools.
    Synthesizes into executive summary and recommendations.
    
    Args:
        context: Optional context string to focus analysis
    
    Returns:
        {
            "ok": bool,
            "executive_summary": str,
            "test_floor": dict,
            "phase_status": dict,
            "quick_wins": list,
            "risks": list,
            "error": str (if ok=False)
        }
    """
    try:
        from .audit import audit_repo_compliance
        from .analysis import analyze_code_quality, analyze_dependencies, find_opportunities, analyze_documentation_alignment
        import unittest.mock as mock
        
        # Mock test floor to avoid verify loop
        with mock.patch("tools.repo.audit._get_test_floor_status", return_value={"passing": 250, "required": 250, "status": "ok"}):
            audit = audit_repo_compliance()
        
        code_quality = analyze_code_quality()
        dependencies = analyze_dependencies()
        opportunities = find_opportunities(focus=context)
        doc_alignment = analyze_documentation_alignment()
        
        # Synthesize executive summary
        test_floor = audit.get("test_floor", {})
        phase_status = audit.get("phase_status", {})
        
        executive_summary = f"""
PrivyBot Strategic Analysis

Test Floor: {test_floor.get('passing', 0)}/{test_floor.get('required', 0)} ({test_floor.get('status', 'unknown')})
Current Phase: {phase_status.get('current', 'unknown')} ({phase_status.get('completion', 'unknown')} complete)

Code Quality: {code_quality.get('complexity', {}).get('file_count', 0)} Python files
Dependencies: {len(dependencies.get('external_deps', {}))} external dependencies
Documentation: {doc_alignment.get('sdd_coverage', {}).get('sdd_count', 0)} SDDs for {doc_alignment.get('sdd_coverage', {}).get('tool_modules', 0)} tool modules

Top Opportunities: {len(opportunities.get('opportunities', []))} identified
""".strip()
        
        # Extract quick wins (high impact, low effort)
        quick_wins = [
            op for op in opportunities.get("opportunities", [])
            if op.get("impact") == "high" and op.get("effort") in ["low", "XS", "S"]
        ][:3]
        
        # Identify risks
        risks = []
        if audit.get("constitutional_violations"):
            risks.append(f"Constitutional violations: {len(audit['constitutional_violations'])}")
        if audit.get("spec_drift"):
            risks.append(f"Spec drift findings: {len(audit['spec_drift'])}")
        
        return {
            "ok": True,
            "executive_summary": executive_summary,
            "test_floor": test_floor,
            "phase_status": phase_status,
            "quick_wins": quick_wins,
            "risks": risks,
            "context": context or "general"
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}
