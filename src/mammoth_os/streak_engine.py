# mammoth_os/streak_engine.py

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from mammoth_os.supabase_client import supabase


def get_user_streak(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the user's current streak record from atlas.leaderboard.
    """
    result = (
        supabase
        .schema("atlas")
        .from_("leaderboard")
        .select("streak, last_active")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    return result.data[0] if result.data else None # type: ignore


def update_streak(user_id: str) -> int:
    """
    Update the user's streak based on last_active date.
    Returns the new streak value.
    """
    record = get_user_streak(user_id)
    today = datetime.utcnow().date()

    # If no record exists, initialize streak = 1
    if not record:
        new_streak = 1
        _write_streak(user_id, new_streak)
        return new_streak

    last_active_str = record.get("last_active")
    current_streak = record.get("streak", 0)

    # If last_active is missing, reset to 1
    if not last_active_str:
        new_streak = 1
        _write_streak(user_id, new_streak)
        return new_streak

    last_active = datetime.fromisoformat(last_active_str).date()

    # If user already did something today → streak unchanged
    if last_active == today:
        return current_streak

    # If last_active was yesterday → streak +1
    if last_active == today - timedelta(days=1):
        new_streak = current_streak + 1
        _write_streak(user_id, new_streak)
        return new_streak

    # If last_active was 2+ days ago → reset streak
    new_streak = 1
    _write_streak(user_id, new_streak)
    return new_streak


def _write_streak(user_id: str, streak: int):
    """
    Internal helper to write streak + last_active to atlas.leaderboard.
    """
    payload = {
        "user_id": user_id,
        "streak": streak,
        "last_active": datetime.utcnow().isoformat(),
    }

    supabase.schema("atlas").from_("leaderboard").upsert(payload).execute()
