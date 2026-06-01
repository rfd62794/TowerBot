"""Bot state management for dev mode and pause mechanism."""

from datetime import datetime
from typing import Optional
from infra.db.schema import _exec


def get_dev_mode() -> bool:
    """Check if dev mode is active."""
    row = _exec("SELECT dev_mode FROM bot_state WHERE id = 1").fetchone()
    if not row:
        # Initialize bot_state if not exists
        _exec("""
            INSERT INTO bot_state (id, dev_mode, paused_at, auto_resume_at)
            VALUES (1, 0, NULL, NULL)
        """, commit=True)
        return False
    return bool(row[0])


def set_dev_mode(active: bool, duration_minutes: Optional[int] = None) -> None:
    """
    Set dev mode state.
    
    Args:
        active: True to enable dev mode, False to disable
        duration_minutes: Optional auto-resume duration in minutes
    """
    paused_at = datetime.now() if active else None
    auto_resume_at = None
    
    if active and duration_minutes:
        from datetime import timedelta
        auto_resume_at = datetime.now() + timedelta(minutes=duration_minutes)
    
    _exec("""
        UPDATE bot_state
        SET dev_mode = ?,
            paused_at = ?,
            auto_resume_at = ?
        WHERE id = 1
    """, (1 if active else 0, paused_at.isoformat() if paused_at else None, 
         auto_resume_at.isoformat() if auto_resume_at else None), commit=True)


def get_pause_status() -> dict:
    """Get current pause status."""
    row = _exec("SELECT dev_mode, paused_at, auto_resume_at FROM bot_state WHERE id = 1").fetchone()
    if not row:
        return {"paused": False, "paused_at": None, "auto_resume_at": None}
    
    dev_mode, paused_at, auto_resume_at = row
    
    # Check if auto-resume time has passed
    if dev_mode and auto_resume_at:
        try:
            if datetime.fromisoformat(auto_resume_at) < datetime.now():
                # Auto-resume
                set_dev_mode(False)
                return {"paused": False, "paused_at": None, "auto_resume_at": None}
        except:
            pass
    
    return {
        "paused": bool(dev_mode),
        "paused_at": paused_at,
        "auto_resume_at": auto_resume_at
    }
