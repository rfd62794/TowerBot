"""Memory CRUD."""

from infra.db.schema import _exec


def save_memory(key: str, content: str, layer: str) -> None:
    _exec(
        "INSERT OR REPLACE INTO memory (key, content, layer, updated, active) "
        "VALUES (?, ?, ?, CURRENT_TIMESTAMP, 1)",
        (key, content, layer), commit=True,
    )


def update_memory(key: str, content: str) -> None:
    _exec(
        "UPDATE memory SET content = ?, updated = CURRENT_TIMESTAMP WHERE key = ?",
        (content, key), commit=True,
    )


def retire_memory(key: str) -> None:
    _exec("UPDATE memory SET active = 0 WHERE key = ?", (key,), commit=True)


def get_memories(query: str, limit: int = 5) -> list[dict]:
    like = f"%{query}%"
    rows = _exec(
        "SELECT key, content, layer FROM memory WHERE active = 1 "
        "AND (key LIKE ? OR content LIKE ?) ORDER BY updated DESC LIMIT ?",
        (like, like, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def list_memories(layer: str | None = None) -> list[dict]:
    if layer:
        rows = _exec(
            "SELECT key, content, layer FROM memory WHERE active = 1 AND layer = ? "
            "ORDER BY layer, key",
            (layer,),
        ).fetchall()
    else:
        rows = _exec(
            "SELECT key, content, layer FROM memory WHERE active = 1 "
            "ORDER BY layer, key"
        ).fetchall()
    return [dict(r) for r in rows]
