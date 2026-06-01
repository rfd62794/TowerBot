"""
pytest configuration — root conftest.py

Provides a `test_db` fixture that spins up a fresh in-memory SQLite database
for each test, then tears it down. Use it in any new pytest test that touches
the database to get full isolation from privy.db and from other tests.

Usage in a test file:
    def test_something(test_db):
        from infra.db.goals import add_commitment
        ...  # runs against :memory:, never touches privy.db

The fixture is opt-in (not autouse). Tests that don't declare it continue to
use whatever DB state is already initialised (backward-compatible with the
existing verify.py test suite).
"""

import sys
import os
import pytest

_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, ".env"))


@pytest.fixture()
def test_db():
    """
    Fresh in-memory SQLite DB for each test.

    Calls init_db(':memory:'), yields the connection, then closes it and
    resets the module-level _conn to None so the next test starts clean.
    """
    from infra.db import schema
    schema.init_db(":memory:")
    yield schema._conn
    if schema._conn:
        schema._conn.close()
        schema._conn = None
