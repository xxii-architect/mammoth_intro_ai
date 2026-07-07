import os
from typing import Optional, Any, Dict, List

# Lazy import of Supabase client
_supabase: Optional[Any] = None


def get_supabase() -> Optional[Any]:
    """
    Lazily create and return a Supabase client instance.
    Returns None if env vars are missing or package is unavailable.
    """
    global _supabase
    if _supabase is not None:
        return _supabase

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        return None

    try:
        from supabase import create_client  # type: ignore
    except Exception:
        return None

    _supabase = create_client(url, key)
    return _supabase


def require_supabase() -> Any:
    """
    Return a Supabase client or raise a clear error.
    Tests patch this function to return FakeSupabase.
    """
    client = get_supabase()
    if client is None:
        raise RuntimeError(
            "Supabase client not configured. "
            "Set SUPABASE_URL and SUPABASE_KEY."
        )
    return client


# ---------------------------------------------------------
# LESSONS / MODULES
# ---------------------------------------------------------

def get_lessons_for_module(module_id: str) -> List[Dict[str, Any]]:
    """
    Always return a list of lessons.
    Tests expect resp.data to exist, so we normalize the return shape.
    """
    client = require_supabase()
    resp = (
        client
        .schema("atlas")  # type: ignore
        .table("lessons")
        .select("*")
        .eq("module_id", module_id)
        .execute()
    )

    # Normalize: ALWAYS return a list
    data = getattr(resp, "data", [])
    return data or []


# ---------------------------------------------------------
# USER PROFILE
# ---------------------------------------------------------

def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    client = require_supabase()
    resp = (
        client
        .schema("atlas")  # type: ignore
        .table("profiles")
        .select("*")
        .eq("id", user_id)
        .execute()
    )

    rows = getattr(resp, "data", []) or []
    return rows[0] if rows else None


# ---------------------------------------------------------
# STREAK ENGINE SUPPORT
# ---------------------------------------------------------

def rpc_update_streak(user_id: str):
    client = require_supabase()
    resp = client.rpc("update_streak", {"p_user_id": user_id}).execute()
    return getattr(resp, "data", None)


# ---------------------------------------------------------
# LEADERBOARD SUPPORT
# ---------------------------------------------------------

def rpc_increment_user_xp(user_id: str, amount: int):
    client = require_supabase()
    resp = client.rpc(
        "increment_user_xp",
        {"p_user_id": user_id, "p_xp_increment": amount}
    ).execute()
    return getattr(resp, "data", None)


# ---------------------------------------------------------
# Module-level client (tests patch this)
# ---------------------------------------------------------

# DO NOT call get_supabase() at import time.
# This breaks tests and CI because env vars are not set yet.
supabase = None
