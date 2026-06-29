# leaderboard_engine.py
from __future__ import annotations
from datetime import datetime
from typing import Optional, Dict, Any, List, TypedDict
import logging

from postgrest.exceptions import APIError  # type: ignore
from mammoth_os.supabase_client import supabase
from mammoth_os.streak_engine import update_streak

# Configure module logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)


class XPResult(TypedDict):
    xp: int
    rank: str


# ---------------------------------------------------------
# ATOMIC XP INCREMENT (Postgres RPC)
# ---------------------------------------------------------
def increment_xp_atomic(user_id: str, amount: int) -> XPResult:
    """
    Calls the Postgres atomic XP increment function.
    Returns: {"xp": int, "rank": str}
    """
    try:
        result = supabase.rpc(
            "increment_user_xp",
            {"p_user_id": user_id, "p_xp_increment": amount}
        ).execute()

        if not result.data:
            raise RuntimeError("RPC returned no data")

        xp = int(result.data[0]["xp"]) # type: ignore
        rank = str(result.data[0]["rank"]) # type: ignore

        return {"xp": xp, "rank": rank}

    except Exception as e:
        logger.exception("Atomic XP increment failed for user %s", user_id)
        raise RuntimeError(f"Atomic XP increment failed: {e}") from e


# ---------------------------------------------------------
# LEGACY FALLBACK (non‑atomic)
# ---------------------------------------------------------
def legacy_add_xp(user_id: str, amount: int) -> int:
    """
    Old non‑atomic XP updater.
    Only used if RPC fails.
    """
    record = get_leaderboard_record(user_id)
    current_xp = int(record.get("xp", 0)) if record else 0
    new_xp = current_xp + int(amount)

    payload = {
        "user_id": user_id,
        "xp": new_xp,
        "rank": record.get("rank", "Novice") if record else "Novice",
        "last_active": datetime.utcnow().isoformat() + "Z",
    }

    try:
        supabase.schema("atlas").from_("community_stats").upsert(
            payload, on_conflict="user_id"
        ).execute()
    except Exception as e:
        logger.exception("Legacy upsert failed for user %s", user_id)
        raise RuntimeError(f"Legacy XP upsert failed: {e}") from e

    return new_xp


# ---------------------------------------------------------
# PUBLIC XP API (uses atomic RPC)
# ---------------------------------------------------------
def add_xp(user_id: str, amount: int) -> int:
    """
    Add XP using the atomic RPC.
    Falls back to legacy upsert if RPC fails.
    Returns the new XP value.
    """
    try:
        result = increment_xp_atomic(user_id, amount)
        logger.info("Atomic XP update for %s -> xp=%s rank=%s", user_id, result["xp"], result["rank"])
        return result["xp"]
    except Exception as e:
        logger.warning("RPC failed, falling back to legacy XP update: %s", e)
        return legacy_add_xp(user_id, amount)


# ---------------------------------------------------------
# READ LEADERBOARD RECORD
# ---------------------------------------------------------
def get_leaderboard_record(user_id: str) -> Optional[Dict[str, Any]]:
    try:
        result = (
            supabase
            .schema("atlas")
            .from_("leaderboard")
            .select("*")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
    except Exception as e:
        logger.exception("Failed to read leaderboard for user %s", user_id)
        raise RuntimeError(f"Failed to read leaderboard for {user_id}: {e}") from e

    data = getattr(result, "data", None)
    return data[0] if data else None


# ---------------------------------------------------------
# STREAK + XP SYNC
# ---------------------------------------------------------
def sync_streak_and_xp(user_id: str, xp_gain: int = 10) -> Dict[str, Any]:
    try:
        new_streak = update_streak(user_id)
    except Exception as e:
        logger.exception("Failed to update streak for user %s", user_id)
        new_streak = None

    new_xp = add_xp(user_id, xp_gain)

    # Rank now comes from DB, not Python
    record = get_leaderboard_record(user_id)
    rank = record.get("rank", "Novice") if record else "Novice"

    return {
        "user_id": user_id,
        "streak": new_streak,
        "xp": new_xp,
        "rank": rank,
    }


# ---------------------------------------------------------
# TOP LEADERBOARD
# ---------------------------------------------------------
def get_top_leaderboard(limit: int = 20) -> List[Dict[str, Any]]:
    try:
        result = (
            supabase
            .schema("atlas")
            .from_("leaderboard")
            .select("*")
            .order("xp", desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as e:
        logger.exception("Failed to read top leaderboard")
        raise RuntimeError(f"Failed to read top leaderboard: {e}") from e

    return getattr(result, "data", []) or []
