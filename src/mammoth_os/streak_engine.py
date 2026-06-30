from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from mammoth_os.supabase_client import get_supabase


def get_user_streak(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the user's current streak record from atlas.leaderboard.
    Returns:
        {
            "user_id": "...",
            "streak": int,
            "last_active": "ISO8601 string"
        }
    or None if no record exists.
    """
    supabase = get_supabase()
    resp = (
        supabase
        .schema("atlas")
        .table("leaderboard")
        .select("streak, last_active")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    rows = getattr(resp, "data", []) or []
    return rows[0] if rows else None


def update_streak(user_id: str) -> int:
    """
    Update the user's streak based on last_active.
    Rules:
      - If no record exists → streak = 1
      - If last_active == today → streak unchanged
      - If last_active == yesterday → streak + 1
      - Else → streak = 1 (reset)
    Returns:
        new streak value (int)
    """
    supabase = get_supabase()
    record = get_user_streak(user_id)
    today = datetime.utcnow().date()

    # No record → initialize streak
    if not record:
        new_streak = 1
        _write_streak(supabase, user_id, new_streak)
        return new_streak

    last_active_str = record.get("last_active")
    current_streak = int(record.get("streak", 0))

    # Missing last_active → reset
    if not last_active_str:
        new_streak = 1
        _write_streak(supabase, user_id, new_streak)
        return new_streak

    last_active = datetime.fromisoformat(last_active_str).date()

    # Already active today → no change
    if last_active == today:
        return current_streak

    # Active yesterday → increment
    if last_active == today - timedelta(days=1):
        new_streak = current_streak + 1
        _write_streak(supabase, user_id, new_streak)
        return new_streak

    # Otherwise → reset
    new_streak = 1
    _write_streak(supabase, user_id, new_streak)
    return new_streak


def _write_streak(supabase, user_id: str, streak: int):
    """
    Internal helper to write streak + last_active to atlas.leaderboard.
    """
    payload = {
        "user_id": user_id,
        "streak": streak,
        "last_active": datetime.utcnow().isoformat(),
    }

    supabase.schema("atlas").table("leaderboard").upsert(payload).execute()
