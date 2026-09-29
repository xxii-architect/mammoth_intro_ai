from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from mammoth_os.supabase_client import get_supabase


def _require_supabase():
    client = get_supabase()
    if client is None:
        raise RuntimeError(
            "Supabase not configured. Set SUPABASE_URL and one of: SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY"
        )
    return client


def get_user_streak(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the user's current streak record from atlas.leaderboard.
    """
    supabase = _require_supabase()
    resp = (
        supabase
        .schema("atlas")  # type: ignore
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
    """
    supabase = _require_supabase()
    record = get_user_streak(user_id)
    today = datetime.now(timezone.utc).date()

    if not record:
        new_streak = 1
        _write_streak(supabase, user_id, new_streak)
        return new_streak

    last_active_str = record.get("last_active")
    current_streak = int(record.get("streak", 0))

    if not last_active_str:
        new_streak = 1
        _write_streak(supabase, user_id, new_streak)
        return new_streak

    last_active = datetime.fromisoformat(last_active_str).date()

    if last_active == today:
        return current_streak

    if last_active == today - timedelta(days=1):
        new_streak = current_streak + 1
        _write_streak(supabase, user_id, new_streak)
        return new_streak

    new_streak = 1
    _write_streak(supabase, user_id, new_streak)
    return new_streak


def _write_streak(supabase, user_id: str, streak: int):
    payload = {
        "user_id": user_id,
        "streak": streak,
        "last_active": datetime.now(timezone.utc).isoformat(),
    }

    supabase.schema("atlas").table("leaderboard").upsert(payload).execute()
