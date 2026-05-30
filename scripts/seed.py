"""seed.py — populate privy.db from context.yaml.

Run once before first launch (and any time context.yaml changes):
    uv run python seed.py

Idempotent: uses INSERT OR REPLACE keyed on memory.key, so rerunning
updates existing rows instead of duplicating them. Zero API calls.
"""

import os
import sqlite3
from datetime import datetime

import yaml

BASE = os.path.dirname(os.path.abspath(__file__))
CONTEXT_PATH = os.path.join(BASE, "..", "config", "context.yaml")
DB_PATH = os.path.join(BASE, "..", "privy.db")

# Mirror of the schema in privybot.py so seeding works on a fresh DB.
MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE,
    content TEXT,
    layer TEXT,
    created DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    active INTEGER DEFAULT 1
);
"""


def seed():
    with open(CONTEXT_PATH, encoding="utf-8") as f:
        ctx = yaml.safe_load(f)

    db = sqlite3.connect(DB_PATH)
    db.executescript(MEMORY_SCHEMA)

    now = datetime.now().isoformat(sep=" ", timespec="seconds")
    count = 0

    # Flatten every list section into memory rows.
    for section, items in ctx.items():
        if section == "identity":
            continue  # handled separately below
        if isinstance(items, list):
            for item in items:
                db.execute(
                    "INSERT INTO memory (key, content, layer, updated, active) "
                    "VALUES (?, ?, ?, ?, 1) "
                    "ON CONFLICT(key) DO UPDATE SET "
                    "content=excluded.content, layer=excluded.layer, "
                    "updated=excluded.updated, active=1",
                    (item["key"], item["content"], item["layer"], now),
                )
                count += 1

    # Save identity as a single structured memory.
    identity = ctx.get("identity", {})
    if identity:
        identity_text = "; ".join(f"{k}: {v}" for k, v in identity.items())
        db.execute(
            "INSERT INTO memory (key, content, layer, updated, active) "
            "VALUES (?, ?, ?, ?, 1) "
            "ON CONFLICT(key) DO UPDATE SET "
            "content=excluded.content, layer=excluded.layer, "
            "updated=excluded.updated, active=1",
            ("robert_identity", identity_text, "personal", now),
        )
        count += 1

    db.commit()
    db.close()
    print(f"Seeded privy.db successfully — {count} memories written.")
    print("Run: uv run python privybot.py")


if __name__ == "__main__":
    seed()
