"""Message CRUD."""

from infra.db.schema import _exec


def add_message(thread_id: str, role: str, content: str) -> None:
    _exec(
        "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
        (thread_id, role, content), commit=True,
    )


def get_context(thread_id: str, n: int = 10) -> list[dict]:
    rows = _exec(
        "SELECT role, content FROM messages WHERE thread_id = ? "
        "ORDER BY id DESC LIMIT ?",
        (thread_id, n),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
