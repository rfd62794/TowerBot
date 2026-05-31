"""
tools/repo/filesystem.py

Local filesystem access tools for PrivyBot self-analysis.
Bounded to C:/Github/PrivyBot/ for security.
No external APIs. No caching.
"""

from pathlib import Path
import re
import os
from datetime import datetime

PRIVYBOT_REPO = Path(os.environ.get("PRIVYBOT_REPO_PATH", "C:/Github/PrivyBot"))
MAX_FILE_SIZE = 100 * 1024  # 100KB


def read_local_file(path: str) -> dict:
    """
    Read a local file from the PrivyBot repository.
    
    Args:
        path: Relative path from repo root (e.g., "privybot.py", "docs/ROADMAP.md")
    
    Returns:
        {
            "ok": bool,
            "content": str,
            "line_count": int,
            "size_bytes": int,
            "truncated": bool,
            "error": str (if ok=False)
        }
    """
    try:
        full_path = PRIVYBOT_REPO / path
        
        # Security: must be within repo
        if not str(full_path.resolve()).startswith(str(PRIVYBOT_REPO.resolve())):
            return {"ok": False, "error": "Path outside repository bounds"}
        
        if not full_path.exists():
            return {"ok": False, "error": f"File not found: {path}"}
        
        if not full_path.is_file():
            return {"ok": False, "error": f"Not a file: {path}"}
        
        content = full_path.read_text(encoding="utf-8", errors="replace")
        size_bytes = len(content.encode("utf-8"))
        line_count = len(content.splitlines())
        truncated = size_bytes > MAX_FILE_SIZE
        
        if truncated:
            content = content[:MAX_FILE_SIZE] + "\n\n[... TRUNCATED: file too large ...]"
        
        return {
            "ok": True,
            "content": content,
            "line_count": line_count,
            "size_bytes": size_bytes,
            "truncated": truncated,
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_local_dir(path: str = "", recursive: bool = False) -> dict:
    """
    List directory contents in the PrivyBot repository.
    
    Args:
        path: Relative path from repo root (empty string = repo root)
        recursive: If True, list all files recursively
    
    Returns:
        {
            "ok": bool,
            "entries": [
                {
                    "name": str,
                    "type": "file" | "dir",
                    "size_bytes": int,
                    "modified": str (ISO timestamp),
                    "relative_path": str
                },
                ...
            ],
            "total_count": int,
            "error": str (if ok=False)
        }
    """
    try:
        target_path = PRIVYBOT_REPO / path if path else PRIVYBOT_REPO
        
        # Security: must be within repo
        if not str(target_path.resolve()).startswith(str(PRIVYBOT_REPO.resolve())):
            return {"ok": False, "error": "Path outside repository bounds"}
        
        if not target_path.exists():
            return {"ok": False, "error": f"Path not found: {path}"}
        
        if not target_path.is_dir():
            return {"ok": False, "error": f"Not a directory: {path}"}
        
        entries = []
        
        if recursive:
            for item in target_path.rglob("*"):
                if item.is_file() or item.is_dir():
                    rel_path = item.relative_to(PRIVYBOT_REPO)
                    stat = item.stat()
                    entries.append({
                        "name": item.name,
                        "type": "dir" if item.is_dir() else "file",
                        "size_bytes": stat.st_size if item.is_file() else 0,
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "relative_path": str(rel_path),
                    })
        else:
            for item in target_path.iterdir():
                if item.name.startswith("."):
                    continue  # Skip hidden files
                rel_path = item.relative_to(PRIVYBOT_REPO)
                stat = item.stat()
                entries.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size_bytes": stat.st_size if item.is_file() else 0,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "relative_path": str(rel_path),
                })
        
        return {
            "ok": True,
            "entries": entries,
            "total_count": len(entries),
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}


def search_local_code(pattern: str, path: str = None, file_pattern: str = "*.py") -> dict:
    """
    Search for a pattern in code files using regex.
    
    Args:
        pattern: Regex pattern to search for
        path: Relative path to search (None = entire repo)
        file_pattern: Glob pattern for files to search (default: *.py)
    
    Returns:
        {
            "ok": bool,
            "matches": [
                {
                    "file": str,
                    "line_number": int,
                    "line": str,
                    "context_before": [str],
                    "context_after": [str]
                },
                ...
            ],
            "total_matches": int,
            "error": str (if ok=False)
        }
    """
    try:
        search_path = PRIVYBOT_REPO / path if path else PRIVYBOT_REPO
        
        # Security: must be within repo
        if not str(search_path.resolve()).startswith(str(PRIVYBOT_REPO.resolve())):
            return {"ok": False, "error": "Path outside repository bounds"}
        
        if not search_path.exists():
            return {"ok": False, "error": f"Path not found: {path}"}
        
        # Compile regex
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return {"ok": False, "error": f"Invalid regex pattern: {e}"}
        
        matches = []
        
        for file_path in search_path.rglob(file_pattern):
            if not file_path.is_file():
                continue
            
            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                
                for line_num, line in enumerate(lines, start=1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(PRIVYBOT_REPO)
                        matches.append({
                            "file": str(rel_path),
                            "line_number": line_num,
                            "line": line.strip(),
                            "context_before": lines[max(0, line_num-3):line_num-1],
                            "context_after": lines[line_num:min(len(lines), line_num+2)],
                        })
            except Exception:
                continue  # Skip files that can't be read
        
        return {
            "ok": True,
            "matches": matches,
            "total_matches": len(matches),
        }
    
    except Exception as e:
        return {"ok": False, "error": str(e)}
