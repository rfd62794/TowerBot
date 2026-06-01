"""One-time cleanup script — cancel legacy NULL prompt tasks."""

from infra.db.schema import init_db, _exec

init_db()
cur = _exec(
    "UPDATE task_queue SET status='cancelled', result='legacy task — predates prompt schema' "
    "WHERE prompt IS NULL AND status='queued'",
    commit=True
)
print(f"Cancelled {cur.rowcount} legacy tasks")
