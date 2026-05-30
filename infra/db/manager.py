"""
core/db/manager.py

Single owner of all database access.
Manages connections, retries, and centralized SQL execution.
"""

import time
import sqlite3
from typing import Tuple, Optional

from infra.db.schema import _conn, _lock


class DBManager:
    """
    Single owner of all database access.

    Wraps _exec() with automatic retry on lock errors.
    All database access should go through db.exec().
    """

    def __init__(self, max_retries: int = 5, base_backoff: float = 0.1):
        self.max_retries = max_retries
        self.base_backoff = base_backoff

    def exec(
        self, sql: str, params: Tuple = (), commit: bool = False
    ) -> sqlite3.Cursor:
        """
        Execute SQL with automatic retry on lock errors.

        Args:
            sql: SQL statement to execute
            params: Parameters for the SQL statement
            commit: Whether to commit after execution

        Returns:
            sqlite3.Cursor

        Raises:
            sqlite3.OperationalError: If all retries fail
        """
        for attempt in range(self.max_retries):
            try:
                from infra.db.schema import _exec
                return _exec(sql, params, commit)
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < self.max_retries - 1:
                    # Exponential backoff
                    backoff = self.base_backoff * (2 ** attempt)
                    time.sleep(backoff)
                    continue
                # Re-raise if not a lock error or retries exhausted
                raise

    def exec_many(
        self, sql: str, params_list: list[Tuple], commit: bool = False
    ) -> None:
        """
        Execute SQL with multiple parameter sets.

        Args:
            sql: SQL statement to execute
            params_list: List of parameter tuples
            commit: Whether to commit after execution
        """
        with _lock:
            cursor = _conn.cursor()
            cursor.executemany(sql, params_list)
            if commit:
                _conn.commit()

    def get_connection(self) -> sqlite3.Connection:
        """Get the current database connection."""
        return _conn


# Singleton instance
db = DBManager()
