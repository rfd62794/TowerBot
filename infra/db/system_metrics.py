"""System metrics database functions."""

from infra.db.schema import _exec


def record_system_snapshot(
    ram_used_gb: float,
    ram_free_gb: float,
    disk_free_gb: float,
    cpu_percent: float,
    ollama_model: str = None,
    ollama_ram_gb: float = None
) -> None:
    """
    Record a system metrics snapshot.
    
    Args:
        ram_used_gb: RAM used in GB
        ram_free_gb: RAM free in GB
        disk_free_gb: Disk free in GB
        cpu_percent: CPU usage percentage
        ollama_model: Currently loaded Ollama model (optional)
        ollama_ram_gb: Ollama RAM usage in GB (optional)
    """
    _exec(
        """INSERT INTO system_metrics 
           (ram_used_gb, ram_free_gb, disk_free_gb, cpu_percent, ollama_model, ollama_ram_gb)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (ram_used_gb, ram_free_gb, disk_free_gb, cpu_percent, ollama_model, ollama_ram_gb),
        commit=True
    )


def get_recent_metrics(hours: int = 24) -> list:
    """
    Get recent system metrics.
    
    Args:
        hours: Look back this many hours
        
    Returns:
        List of metric dicts
    """
    rows = _exec(
        """SELECT * FROM system_metrics 
           WHERE recorded_at >= datetime('now', ? || ' hours')
           ORDER BY recorded_at DESC""",
        (f"-{hours}",)
    ).fetchall()
    
    return [dict(row) for row in rows]


def get_latest_metrics() -> dict | None:
    """
    Get the most recent system metrics snapshot.
    
    Returns:
        Dict of latest metrics, or None if no data
    """
    row = _exec(
        "SELECT * FROM system_metrics ORDER BY recorded_at DESC LIMIT 1"
    ).fetchone()
    
    return dict(row) if row else None


def get_average_metrics(hours: int = 24) -> dict:
    """
    Get average system metrics over a time window.
    
    Args:
        hours: Look back this many hours
        
    Returns:
        Dict with average values
    """
    row = _exec(
        """SELECT 
           AVG(ram_used_gb) as avg_ram_used,
           AVG(ram_free_gb) as avg_ram_free,
           AVG(disk_free_gb) as avg_disk_free,
           AVG(cpu_percent) as avg_cpu,
           COUNT(*) as samples
           FROM system_metrics
           WHERE recorded_at >= datetime('now', ? || ' hours')""",
        (f"-{hours}",)
    ).fetchone()
    
    if row:
        return {
            "avg_ram_used_gb": round(row["avg_ram_used"] or 0, 2),
            "avg_ram_free_gb": round(row["avg_ram_free"] or 0, 2),
            "avg_disk_free_gb": round(row["avg_disk_free"] or 0, 2),
            "avg_cpu_percent": round(row["avg_cpu"] or 0, 2),
            "samples": row["samples"] or 0
        }
    return {"avg_ram_used_gb": 0, "avg_ram_free_gb": 0, "avg_disk_free_gb": 0, "avg_cpu_percent": 0, "samples": 0}
