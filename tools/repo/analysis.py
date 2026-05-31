"""
tools/repo/analysis.py

Code analysis tools for PrivyBot self-analysis.
Uses LLM for deep analysis of code quality, dependencies, opportunities, and documentation alignment.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any

PRIVYBOT_REPO = Path(os.environ.get("PRIVYBOT_REPO_PATH", "C:/Github/PrivyBot"))


def analyze_code_quality(path: Optional[str] = None) -> dict:
    """
    Analyze code quality metrics and patterns.
    
    Args:
        path: Relative path to analyze (None = entire repo)
    
    Returns:
        {
            "ok": bool,
            "complexity": dict,
            "testing": dict,
            "patterns": dict,
            "maintainability": dict,
            "error": str (if ok=False)
        }
    """
    # This is a placeholder - actual implementation would use LLM
    # For now, return basic static analysis
    try:
        target_path = PRIVYBOT_REPO / path if path else PRIVYBOT_REPO
        
        if not target_path.exists():
            return {"ok": False, "error": f"Path not found: {path}"}
        
        py_files = list(target_path.rglob("*.py"))
        
        # Basic metrics
        total_loc = 0
        max_function_length = 0
        test_files = [f for f in py_files if "test" in f.name.lower()]
        
        for py_file in py_files:
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                total_loc += len(lines)
                
                # Simple heuristic for function length
                for line in lines:
                    if line.strip().startswith("def "):
                        # Count until next def or class
                        pass
            except:
                continue
        
        return {
            "ok": True,
            "complexity": {
                "total_loc": total_loc,
                "file_count": len(py_files),
                "avg_loc_per_file": total_loc // len(py_files) if py_files else 0
            },
            "testing": {
                "test_file_count": len(test_files),
                "test_ratio": len(test_files) / len(py_files) if py_files else 0
            },
            "patterns": {
                "note": "Pattern analysis requires LLM integration"
            },
            "maintainability": {
                "note": "Maintainability scoring requires LLM integration"
            }
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


def analyze_dependencies() -> dict:
    """
    Analyze dependencies and change impact.
    
    Returns:
        {
            "ok": bool,
            "load_bearing": list,
            "fragile_chains": list,
            "external_deps": dict,
            "change_impact": dict,
            "error": str (if ok=False)
        }
    """
    try:
        # Read pyproject.toml for external dependencies
        pyproject_path = PRIVYBOT_REPO / "pyproject.toml"
        external_deps = {}
        
        if pyproject_path.exists():
            content = pyproject_path.read_text(encoding="utf-8")
            # Simple extraction of dependencies
            in_deps = False
            for line in content.splitlines():
                if "dependencies = [" in line:
                    in_deps = True
                elif in_deps:
                    if "]" in line:
                        break
                    if "=" in line and not line.strip().startswith("#"):
                        dep = line.split("=")[0].strip().strip('"')
                        external_deps[dep] = "external"
        
        return {
            "ok": True,
            "load_bearing": ["bot/agent.py", "bot/router.py", "bot/transport.py"],
            "fragile_chains": [],
            "external_deps": external_deps,
            "change_impact": {
                "note": "Full impact analysis requires import graph parsing"
            }
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


def find_opportunities(focus: Optional[str] = None) -> dict:
    """
    Identify ranked improvement opportunities.
    
    Args:
        focus: Optional focus area (e.g., "Phase 15", "autonomous tasks")
    
    Returns:
        {
            "ok": bool,
            "opportunities": list,
            "focus": str,
            "error": str (if ok=False)
        }
    """
    # Placeholder - actual implementation would use LLM to analyze
    try:
        opportunities = [
            {
                "title": "Add type hints to API functions",
                "impact": "high",
                "effort": "low",
                "phase": "Phase 11 remaining",
                "blockers": [],
                "success_criteria": "mypy passes on api/ directory"
            },
            {
                "title": "Improve test coverage for tools/",
                "impact": "high",
                "effort": "medium",
                "phase": "Ongoing",
                "blockers": [],
                "success_criteria": "90%+ coverage in tools/"
            }
        ]
        
        if focus:
            opportunities = [op for op in opportunities if focus.lower() in op.get("phase", "").lower()]
        
        return {
            "ok": True,
            "opportunities": opportunities,
            "focus": focus or "all"
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


def analyze_documentation_alignment() -> dict:
    """
    Analyze documentation alignment with code.
    
    Returns:
        {
            "ok": bool,
            "sdd_coverage": dict,
            "spec_drift": list,
            "doc_currency": list,
            "missing_docs": list,
            "error": str (if ok=False)
        }
    """
    try:
        # Check SDD coverage
        sdd_dir = PRIVYBOT_REPO / "docs" / "sdd"
        sdd_files = list(sdd_dir.glob("*.md")) if sdd_dir.exists() else []
        
        # Check tools coverage
        tools_dir = PRIVYBOT_REPO / "tools"
        tool_modules = [d.name for d in tools_dir.iterdir() if d.is_dir()] if tools_dir.exists() else []
        
        sdd_coverage = {
            "sdd_count": len(sdd_files),
            "tool_modules": len(tool_modules),
            "coverage_ratio": len(sdd_files) / len(tool_modules) if tool_modules else 0
        }
        
        return {
            "ok": True,
            "sdd_coverage": sdd_coverage,
            "spec_drift": [],
            "doc_currency": [],
            "missing_docs": []
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}
