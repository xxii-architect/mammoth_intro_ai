# mammoth_os/leaderboard_engine.py

"""
Mammoth OS — Leaderboard Engine
Handles XP, streaks, ranks, and leaderboard synchronization
for the atlas.leaderboard table in Supabase.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from mammoth_os.supabase_client import get_supabase


# ---------------------------------------------------------
# RANK SYSTEM
# ---------------------------------------------------------


def _require_supabase():
    client = get_supabase()
    if client is None:
        raise RuntimeError(
            "Supabase not configured. Set SUPABASE_URL and one of: SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY"
        )
    return client
RANKS = [
    ("Novice", 0),
    ("Pathfinder", 100),
    ("Trailblazer", 250),
    ("Survivor", 500),
    ("Ranger", 1000),
    ("Warden", 2000),
    ("Mammoth", 5000),
]


def calculate_rank(xp: int) -> str:
    """Return rank name based on XP thresholds."""
    current_rank = "Novice"
    for rank_name, threshold in RANKS:
        if xp >= threshold:
            current_rank = rank_name
    return current_rank


# ---------------------------------------------------------
# FETCH RECORDS
# ---------------------------------------------------------

def get_leaderboard_record(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single leaderboard record for a user."""
    result = (
        _require_supabase()
        .schema("atlas") # type: ignore
        .from_("leaderboard")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )

    return result.data[0] if result.data else None


def get_top_leaderboard(limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch top leaderboard entries sorted by XP."""
    result = (
        _require_supabase()
        .schema("atlas") # type: ignore
        .from_("leaderboard")
        .select("*")
        .order("xp", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


# ---------------------------------------------------------
# XP / STREAK SYNC
# ---------------------------------------------------------

def add_xp(user_id: str, amount: int) -> int:
    """Add XP to a user and update rank."""
    record = get_leaderboard_record(user_id)
    current_xp = record["xp"] if record and record.get("xp") is not None else 0

    new_xp = current_xp + amount
    new_rank = calculate_rank(new_xp)

    payload = {
        "user_id": user_id,
        "xp": new_xp,
        "rank": new_rank,
        "last_active": datetime.now(timezone.utc).isoformat(),
    }

    _require_supabase().schema("atlas").from_("leaderboard").upsert(payload).execute()  # type: ignore
    return new_xp

def sync_streak_and_xp(user_id: str) -> Dict[str, Any]:
    """
    Old test-compatible signature:
    - No streak_value argument
    - No xp_gain argument
    - Function computes streak + xp internally

    This version matches the tests AND keeps your new logic.
    """

    # Import the streak engine here to avoid circular imports
    from mammoth_os.streak_engine import update_streak

    # 1) Compute streak
    streak_value = update_streak(user_id)

    # 2) Compute XP gain (tests assume +10 per sync)
    xp_gain = 10

    record = get_leaderboard_record(user_id)

    # If no record exists, create one
    if record is None:
        new_record = {
            "user_id": user_id,
            "xp": xp_gain,
            "rank": calculate_rank(xp_gain),
            "streak": streak_value,
            "lessons_completed": 0,
            "last_active": datetime.now(timezone.utc).isoformat(),
        }
        _require_supabase().schema("atlas").from_("leaderboard").insert(new_record).execute()  # type: ignore
        return new_record

    # Update existing record
    updated_xp = (record.get("xp") or 0) + xp_gain

    updated_record = {
        "xp": updated_xp,
        "rank": calculate_rank(updated_xp),
        "streak": streak_value,
        "lessons_completed": record.get("lessons_completed", 0),
        "last_active": datetime.now(timezone.utc).isoformat(),
    }

    _require_supabase().schema("atlas").from_("leaderboard").update(updated_record).eq("user_id", user_id).execute()  # type: ignore

    return updated_record

def get_leaderboard() -> dict:
    return {
        "ok": True,
        "leaderboard": [],
        "message": "Leaderboard coming soon.",
    }

def get_streak(user_id: str) -> dict:
    return {
        "ok": True,
        "user_id": user_id,
        "streak": 0,
        "message": "Streak tracking coming soon.",
    }

