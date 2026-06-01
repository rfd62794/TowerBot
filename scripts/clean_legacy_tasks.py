"""One-time cleanup script — cancel legacy NULL prompt tasks."""

from infra.db import get_db

with get_db() as db:
    db.execute("""
        UPDATE task_queue 
        SET status='cancelled', 
            result='legacy task — predates prompt schema'
        WHERE prompt IS NULL 
        AND status='queued'
    """)
    db.commit()
    print(f"Cancelled {db.rowcount} legacy tasks")
