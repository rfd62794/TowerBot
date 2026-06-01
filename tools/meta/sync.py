"""Database sync tools for MCP and CLI access."""

from typing import Optional, Dict, Any, List
from infra.db.sync import DBSync


def sync_db_status() -> Dict[str, Any]:
    """
    Get table inventory and sync status.
    
    Returns:
        Dict with table inventory, policies, and row counts.
    """
    sync = DBSync()
    inventory = sync.get_table_inventory()
    
    # Group by policy
    shared = {name: info for name, info in inventory.items() if info["policy"] == "shared"}
    instance = {name: info for name, info in inventory.items() if info["policy"] == "instance"}
    cache = {name: info for name, info in inventory.items() if info["policy"] == "cache"}
    config = {name: info for name, info in inventory.items() if info["policy"] == "config"}
    
    return {
        "total_tables": len(inventory),
        "shared": shared,
        "instance": instance,
        "cache": cache,
        "config": config,
        "shared_row_count": sum(info["row_count"] for info in shared.values())
    }


def sync_db_export(tables: Optional[List[str]] = None, output_path: str = "sync.json") -> Dict[str, Any]:
    """
    Export SHARED tables to JSON file.
    
    Args:
        tables: Optional list of specific tables to export (default: all SHARED)
        output_path: Path for output JSON file (default: sync.json)
    
    Returns:
        Dict with export status and file path.
    """
    sync = DBSync()
    result_path = sync.export_tables(tables=tables, output_path=output_path)
    
    return {
        "status": "success",
        "output_path": result_path,
        "tables_exported": tables if tables else "all SHARED"
    }


def sync_db_import(sync_data: Optional[Dict[str, Any]] = None, source: str = "sync.json", 
                   dry_run: bool = True, conflict: Optional[str] = None) -> Dict[str, Any]:
    """
    Import tables from sync source.
    
    Args:
        sync_data: Optional direct sync data dict (if None, reads from source file)
        source: Path to sync JSON file (default: sync.json)
        dry_run: If True, show changes without applying (default: True)
        conflict: Conflict resolution strategy (default: from config)
    
    Returns:
        Dict with import report (added, updated, conflicts, skipped).
    """
    sync = DBSync()
    
    if sync_data:
        # Import from direct data dict
        # Need to temporarily save to file for transport.receive() to work
        import json
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sync_data, f)
            temp_path = f.name
        try:
            report = sync.import_tables(source=temp_path, dry_run=dry_run, conflict=conflict)
        finally:
            import os
            os.unlink(temp_path)
    else:
        # Import from file
        report = sync.import_tables(source=source, dry_run=dry_run, conflict=conflict)
    
    return {
        "status": "success" if not dry_run else "dry_run",
        "added": report["added"],
        "updated": report["updated"],
        "conflicts": report["conflicts"],
        "skipped": report["skipped"],
        "changes": report["changes"]
    }
