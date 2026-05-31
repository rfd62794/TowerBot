"""Post pipeline state management — blog post creation stages."""

from datetime import datetime
from infra.db.schema import _exec


def get_or_create_post(topic: str) -> dict:
    """
    Get existing post by topic or create new one at stage 0.

    Args:
        topic: Post topic/title

    Returns:
        Dict with post data (id, topic, stage, q1_prompt, research, skeleton, wp_post_id, wp_edit_url)
    """
    row = _exec(
        "SELECT * FROM post_pipeline WHERE topic = ?",
        (topic,)
    ).fetchone()

    if row:
        return dict(row)

    # Create new post at stage 0
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _exec(
        "INSERT INTO post_pipeline (topic, stage, created_at, updated_at) VALUES (?, 0, ?, ?)",
        (topic, now, now),
        commit=True
    )
    row = _exec(
        "SELECT * FROM post_pipeline WHERE topic = ?",
        (topic,)
    ).fetchone()
    return dict(row)


def get_most_advanced_post() -> dict | None:
    """
    Get the most advanced in-progress post (highest stage, most recent).

    Returns:
        Dict with post data or None if no posts exist
    """
    row = _exec(
        "SELECT * FROM post_pipeline ORDER BY stage DESC, updated_at DESC LIMIT 1"
    ).fetchone()
    return dict(row) if row else None


def update_post_stage(post_id: int, stage: int, **fields) -> None:
    """
    Update post stage and any additional fields.

    Args:
        post_id: Post ID
        stage: New stage (0-5)
        **fields: Additional fields to update (q1_prompt, research, skeleton, wp_post_id, wp_edit_url)
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Build dynamic update query
    valid_fields = {"q1_prompt", "research", "skeleton", "wp_post_id", "wp_edit_url"}
    updates = ["stage = ?", "updated_at = ?"]
    params = [stage, now]
    
    for field, value in fields.items():
        if field in valid_fields:
            updates.append(f"{field} = ?")
            params.append(value)
    
    params.append(post_id)
    
    sql = f"UPDATE post_pipeline SET {', '.join(updates)} WHERE id = ?"
    _exec(sql, params, commit=True)


def get_post_by_id(post_id: int) -> dict | None:
    """
    Get post by ID.

    Args:
        post_id: Post ID

    Returns:
        Dict with post data or None
    """
    row = _exec(
        "SELECT * FROM post_pipeline WHERE id = ?",
        (post_id,)
    ).fetchone()
    return dict(row) if row else None


def list_all_posts() -> list[dict]:
    """
    List all posts in pipeline.

    Returns:
        List of dicts with post data
    """
    rows = _exec(
        "SELECT * FROM post_pipeline ORDER BY stage DESC, updated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_post(post_id: int) -> None:
    """
    Delete post from pipeline.

    Args:
        post_id: Post ID
    """
    _exec(
        "DELETE FROM post_pipeline WHERE id = ?",
        (post_id,),
        commit=True
    )
