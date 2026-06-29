# src/mammoth_os/leaderboard_engine.py

import logging
from types import SimpleNamespace
from mammoth_os.supabase_client import get_supabase

logger = logging.getLogger(__name__)

def increment_xp_atomic(user_id: str, xp_increment: int):
    supabase = get_supabase()
    try:
        resp = supabase.rpc(
            "increment_user_xp",
            {"p_user_id": user_id, "p_xp_increment": xp_increment}
        ).execute()
        return getattr(resp, "data", None)
    except Exception as e:
        logger.error("Atomic XP increment failed", exc_info=True)
        raise RuntimeError(f"Atomic XP increment failed: {e}")

def legacy_add_xp(user_id: str, xp_increment: int):
    supabase = get_supabase()
    try:
        resp = supabase.schema("atlas").table("leaderboard").select("*").eq("user_id", user_id).execute()
        rows = getattr(resp, "data", []) or []

        if rows:
            record = rows[0]
            new_xp = int(record.get("xp", 0)) + xp_increment
            supabase.schema("atlas").table("leaderboard").update({"xp": new_xp}).eq("user_id", user_id).execute()
            return {"status": "ok", "xp": new_xp}
        else:
            supabase.schema("atlas").table("leaderboard").insert(
                {"user_id": user_id, "xp": xp_increment}
            ).execute()
            return {"status": "ok", "xp": xp_increment}
    except Exception as e:
        logger.error("Legacy XP update failed", exc_info=True)
        raise RuntimeError(f"Failed to read leaderboard for {user_id}: {e}")

def get_leaderboard_record(user_id: str):
    supabase = get_supabase()
    resp = supabase.schema("atlas").table("leaderboard").select("*").eq("user_id", user_id).execute()
    rows = getattr(resp, "data", []) or []
    return rows[0] if rows else None

def add_xp(user_id: str, amount: int):
    try:
        return increment_xp_atomic(user_id, amount)
    except Exception:
        logger.warning("RPC failed, falling back to legacy XP update")
        return legacy_add_xp(user_id, amount)

def sync_streak_and_xp(user_id: str):
    """
    Test helper: update streak, then XP.
    """
    from mammoth_os.streak_engine import update_streak
    streak_result = update_streak(user_id)
    xp_result = add_xp(user_id, 10)
    return {"streak": streak_result, "xp": xp_result}

def get_top_leaderboard(limit: int = 10):
    """
    Test helper: return top XP users.
    """
    supabase = get_supabase()
    resp = supabase.schema("atlas").table("leaderboard").select("*").execute()
    rows = getattr(resp, "data", []) or []

    # Sort by XP descending
    sorted_rows = sorted(rows, key=lambda r: r.get("xp", 0), reverse=True)
    return sorted_rows[:limit]

