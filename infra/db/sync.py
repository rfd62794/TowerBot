"""Database sync system with auto-classification and pluggable transport."""

import json
import sqlite3
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import os
import yaml

from infra.db.schema import _exec


class SyncPolicy(Enum):
    SHARED = "shared"      # sync bidirectionally — memory, tasks, goals
    INSTANCE = "instance"  # never sync — logs, conversations, metrics
    CACHE = "cache"        # skip, rebuild from APIs — history, tool_cache
    CONFIG = "config"      # instance-specific, manual review — bot_state


class ConflictStrategy(Enum):
    LATEST_WINS = "latest_wins"    # use most recent updated_at
    MERGE_APPEND = "merge_append"  # append all records (commitments)


TABLE_REGISTRY = {
    # SHARED
    "memory": SyncPolicy.SHARED,
    "goals": SyncPolicy.SHARED,
    "milestones": SyncPolicy.SHARED,
    "tasks": SyncPolicy.SHARED,
    "weekly_plans": SyncPolicy.SHARED,
    "personal_tasks": SyncPolicy.SHARED,
    "commitments": SyncPolicy.SHARED,
    "post_pipeline": SyncPolicy.SHARED,
    "tasks_sync": SyncPolicy.SHARED,

    # INSTANCE — never cross machines
    "messages": SyncPolicy.INSTANCE,
    "threads": SyncPolicy.INSTANCE,
    "agent_actions": SyncPolicy.INSTANCE,
    "model_usage": SyncPolicy.INSTANCE,
    "poll_log": SyncPolicy.INSTANCE,
    "deploy_history": SyncPolicy.INSTANCE,
    "preload_log": SyncPolicy.INSTANCE,
    "observations": SyncPolicy.INSTANCE,
    "system_metrics": SyncPolicy.INSTANCE,
    "task_queue": SyncPolicy.INSTANCE,

    # CACHE — skip, APIs rebuild these
    "tool_cache": SyncPolicy.CACHE,
    "channel_history": SyncPolicy.CACHE,
    "video_history": SyncPolicy.CACHE,
    "game_history": SyncPolicy.CACHE,
    "weather_history": SyncPolicy.CACHE,
    "video_metadata_cache": SyncPolicy.CACHE,
    "api_rate_limits": SyncPolicy.CACHE,
    "api_call_log": SyncPolicy.CACHE,

    # CONFIG — exists but differs per instance
    "bot_state": SyncPolicy.CONFIG,
}


CONFLICT_STRATEGY = {
    "memory": ConflictStrategy.LATEST_WINS,
    "personal_tasks": ConflictStrategy.LATEST_WINS,
    "goals": ConflictStrategy.LATEST_WINS,
    "commitments": ConflictStrategy.MERGE_APPEND,
    "post_pipeline": ConflictStrategy.LATEST_WINS,
}


def classify_unknown_table(name: str, columns: List[str]) -> SyncPolicy:
    """
    Auto-classify tables not yet in registry.
    Conservative — defaults to INSTANCE if uncertain.
    """
    if any(x in name for x in ["_cache", "_log", "_history"]):
        return SyncPolicy.CACHE
    if any(x in columns for x in ["thread_id", "chat_id", "ran_at"]):
        return SyncPolicy.INSTANCE
    if any(x in columns for x in ["expires_at", "fetched_at"]):
        return SyncPolicy.CACHE
    if "layer" in columns or "content" in columns:
        return SyncPolicy.SHARED
    return SyncPolicy.INSTANCE


@dataclass
class SyncManifest:
    timestamp: str
    instance: str
    schema_version: str
    tables: List[str]


class SyncTransport(ABC):
    @abstractmethod
    def send(self, payload: Dict[str, Any]) -> str:
        """Send sync payload, return path/identifier."""
        pass

    @abstractmethod
    def receive(self, source: str) -> Dict[str, Any]:
        """Receive sync payload from source."""
        pass


class JSONFileTransport(SyncTransport):
    """Export/import via JSON file, manual copy."""

    def send(self, payload: Dict[str, Any], output_path: str = "sync.json") -> str:
        with open(output_path, "w") as f:
            json.dump(payload, f, indent=2)
        return output_path

    def receive(self, source: str) -> Dict[str, Any]:
        with open(source, "r") as f:
            return json.load(f)


class DBSync:
    def __init__(self, db_path: str = "privy.db", config_path: str = "infra/db/sync_config.yaml"):
        self.db_path = db_path
        self.config = self._load_config(config_path)
        self.transport = self._get_transport()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        if not os.path.exists(config_path):
            return {
                "transport": "json_file",
                "conflict_default": "latest_wins",
                "alert_on_unknown_tables": True,
                "table_overrides": {}
            }
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _get_transport(self) -> SyncTransport:
        transport_type = self.config.get("transport", "json_file")
        if transport_type == "json_file":
            return JSONFileTransport()
        # Future: TailscaleTransport, ServerTransport, PostgresTransport
        raise ValueError(f"Unknown transport: {transport_type}")

    def get_table_policy(self, table_name: str) -> SyncPolicy:
        """Get sync policy for a table, with config override."""
        if table_name in self.config.get("table_overrides", {}):
            override = self.config["table_overrides"][table_name]
            return SyncPolicy(override)
        if table_name in TABLE_REGISTRY:
            return TABLE_REGISTRY[table_name]
        # Auto-classify unknown tables
        columns = self._get_table_columns(table_name)
        policy = classify_unknown_table(table_name, columns)
        if self.config.get("alert_on_unknown_tables", True):
            print(f"⚠️ New table detected: {table_name}")
            print(f"   Auto-classified as: {policy.value}")
            print(f"   Override in: infra/db/sync_config.yaml")
        return policy

    def _get_table_columns(self, table_name: str) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return columns

    def get_table_inventory(self) -> Dict[str, Dict[str, Any]]:
        """Get all tables with their policies and row counts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        inventory = {}
        for table in tables:
            policy = self.get_table_policy(table)
            count = self._get_row_count(table)
            inventory[table] = {
                "policy": policy.value,
                "row_count": count,
                "columns": self._get_table_columns(table)
            }
        return inventory

    def _get_row_count(self, table_name: str) -> int:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def export_tables(self, tables: Optional[List[str]] = None, output_path: str = "sync.json") -> str:
        """Export SHARED tables (or specified subset) to JSON."""
        inventory = self.get_table_inventory()
        
        if tables is None:
            tables = [name for name, info in inventory.items() 
                     if info["policy"] == SyncPolicy.SHARED.value]
        
        data = {}
        for table in tables:
            if table not in inventory:
                print(f"⚠️ Table not found: {table}")
                continue
            policy = inventory[table]["policy"]
            if policy == SyncPolicy.INSTANCE.value:
                print(f"⏭️ Skipping INSTANCE table: {table}")
                continue
            if policy == SyncPolicy.CACHE.value:
                print(f"⏭️ Skipping CACHE table: {table}")
                continue
            data[table] = self._export_table_data(table)

        manifest = SyncManifest(
            timestamp=datetime.now().isoformat(),
            instance=os.getenv("INSTANCE_ROLE", "unknown"),
            schema_version="1.0",
            tables=list(data.keys())
        )

        payload = {
            "manifest": {
                "timestamp": manifest.timestamp,
                "instance": manifest.instance,
                "schema_version": manifest.schema_version,
                "tables": manifest.tables
            },
            "data": data
        }

        return self.transport.send(payload, output_path)

    def _export_table_data(self, table_name: str) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def import_tables(self, source: str, dry_run: bool = True, conflict: Optional[str] = None) -> Dict[str, Any]:
        """Import tables from sync source, with dry-run and conflict resolution."""
        payload = self.transport.receive(source)
        manifest = payload["manifest"]
        data = payload["data"]

        report = {
            "added": 0,
            "updated": 0,
            "conflicts": 0,
            "skipped": 0,
            "changes": []
        }

        if dry_run:
            print("🔍 Dry-run mode — no changes will be applied")

        for table_name, rows in data.items():
            policy = self.get_table_policy(table_name)
            if policy == SyncPolicy.INSTANCE.value:
                report["skipped"] += len(rows)
                print(f"⏭️ Skipping INSTANCE table: {table_name}")
                continue
            if policy == SyncPolicy.CACHE.value:
                report["skipped"] += len(rows)
                print(f"⏭️ Skipping CACHE table: {table_name}")
                continue

            table_report = self._import_table_data(table_name, rows, dry_run, conflict)
            report["added"] += table_report["added"]
            report["updated"] += table_report["updated"]
            report["conflicts"] += table_report["conflicts"]
            report["changes"].append(table_report)

        return report

    def _import_table_data(self, table_name: str, rows: List[Dict[str, Any]], 
                           dry_run: bool, conflict: Optional[str]) -> Dict[str, Any]:
        """Import data for a single table with conflict resolution."""
        strategy_name = conflict or self.config.get("conflict_default", "latest_wins")
        strategy = ConflictStrategy(strategy_name)
        
        if table_name in CONFLICT_STRATEGY:
            strategy = CONFLICT_STRATEGY[table_name]

        report = {"added": 0, "updated": 0, "conflicts": 0, "table": table_name}

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for row in rows:
            if strategy == ConflictStrategy.MERGE_APPEND:
                # Insert all records (append-only)
                if not dry_run:
                    self._insert_row(cursor, table_name, row)
                report["added"] += 1
            else:  # LATEST_WINS
                # Check if exists, use updated_at if available
                if "updated_at" in row:
                    existing = self._find_by_id(cursor, table_name, row.get("id"))
                    if existing:
                        existing_updated = existing.get("updated_at")
                        if row["updated_at"] > existing_updated:
                            if not dry_run:
                                self._update_row(cursor, table_name, row)
                            report["updated"] += 1
                        else:
                            report["conflicts"] += 1
                        continue
                # Insert if not exists
                if not dry_run:
                    self._insert_row(cursor, table_name, row)
                report["added"] += 1

        if not dry_run:
            conn.commit()
        conn.close()

        # Post-import hook: rebuild Chroma if memory table was imported
        if table_name == "memory" and not dry_run and report["added"] + report["updated"] > 0:
            self._rebuild_chroma()

        return report

    def _rebuild_chroma(self):
        """Rebuild Chroma vector store from synced memory table."""
        try:
            import subprocess
            import sys
            
            print("🔄 Rebuilding Chroma from synced memory table...")
            result = subprocess.run(
                [sys.executable, "scripts/migrate_memories_to_chroma.py"],
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print("✅ Chroma rebuilt successfully")
            else:
                print(f"⚠️ Chroma rebuild failed: {result.stderr}")
        except Exception as e:
            print(f"⚠️ Chroma rebuild error: {e}")

    def _find_by_id(self, cursor, table_name: str, row_id: Any) -> Optional[Dict[str, Any]]:
        """Find a row by ID."""
        if row_id is None:
            return None
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = ?", (row_id,))
        row = cursor.fetchone()
        if row:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
        return None

    def _insert_row(self, cursor, table_name: str, row: Dict[str, Any]):
        """Insert a row into a table."""
        columns = list(row.keys())
        placeholders = ", ".join(["?"] * len(columns))
        values = [row[col] for col in columns]
        cursor.execute(f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})", values)

    def _update_row(self, cursor, table_name: str, row: Dict[str, Any]):
        """Update a row in a table."""
        if "id" not in row:
            return
        columns = [col for col in row.keys() if col != "id"]
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        values = [row[col] for col in columns] + [row["id"]]
        cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE id = ?", values)

    def diff(self, source: str) -> Dict[str, Any]:
        """Compare local DB with sync source without importing."""
        payload = self.transport.receive(source)
        remote_data = payload["data"]
        
        diff_report = {
            "only_local": [],
            "only_remote": [],
            "differing": []
        }

        local_inventory = self.get_table_inventory()
        local_tables = set(local_inventory.keys())
        remote_tables = set(remote_data.keys())

        diff_report["only_local"] = list(local_tables - remote_tables)
        diff_report["only_remote"] = list(remote_tables - local_tables)

        for table in local_tables & remote_tables:
            local_count = local_inventory[table]["row_count"]
            remote_count = len(remote_data[table])
            if local_count != remote_count:
                diff_report["differing"].append({
                    "table": table,
                    "local_count": local_count,
                    "remote_count": remote_count
                })

        return diff_report
