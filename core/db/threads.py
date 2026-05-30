"""Thread CRUD."""

from core.db.schema import _exec


def create_thread(thread_id: str) -> None:
    _exec("INSERT INTO threads (id) VALUES (?)", (thread_id,), commit=True)


def update_thread_name(thread_id: str, name: str) -> None:
    _exec("UPDATE threads SET name = ? WHERE id = ?", (name, thread_id), commit=True)


def update_thread_active(thread_id: str) -> None:
    _exec(
        "UPDATE threads SET last_active = CURRENT_TIMESTAMP WHERE id = ?",
        (thread_id,), commit=True,
    )


def list_threads(limit: int = 10) -> list[dict]:
    rows = _exec(
        "SELECT id, name, created, last_active FROM threads "
        "ORDER BY last_active DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
