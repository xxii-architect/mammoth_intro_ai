import os
from typing import Optional, Any, Dict, List

# Lazy import of Supabase client
_supabase: Optional[Any] = None


# ---------------------------------------------------------
# CLIENT ACCESSORS
# ---------------------------------------------------------

def get_supabase() -> Optional[Any]:
    """
    Lazily create and return a Supabase client instance.
    Returns None if env vars are missing or package is unavailable.
    Safe for CLI, tests, and production.
    """
    global _supabase
    if _supabase is not None:
        return _supabase

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    # CLI mode or missing env vars → return None safely
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
    CLI should NOT call this directly.
    """
    client = get_supabase()
    if client is None:
        raise RuntimeError(
            "Supabase client not configured. "
            "Set SUPABASE_URL and SUPABASE_KEY."
        )
    return client


# ---------------------------------------------------------
# SAFE HELPERS (used by CLI + engines)
# ---------------------------------------------------------

def safe_schema(schema: str) -> Optional[Any]:
    """
    Safe wrapper for supabase.schema(schema).
    Returns None instead of crashing when supabase is missing.
    """
    client = get_supabase()
    if client is None:
        return None

    try:
        return client.schema(schema)
    except Exception:
        return None


def safe_execute(query) -> List[Dict[str, Any]]:
    """
    Safe wrapper for query.execute().
    Always returns a list.
    """
    try:
        resp = query.execute()
        return getattr(resp, "data", []) or []
    except Exception:
        return []


# ---------------------------------------------------------
# LESSONS / MODULES
# ---------------------------------------------------------

def get_lessons_for_module(module_id: str) -> List[Dict[str, Any]]:
    """
    Always return a list of lessons.
    CLI-safe: returns [] when Supabase is not configured.
    Tests patch require_supabase() so this still works.
    """
    schema = safe_schema("atlas")
    if schema is None:
        return []  # CLI fallback

    query = (
        schema
        .table("lessons")
        .select("*")
        .eq("module_id", module_id)
    )

    return safe_execute(query)


# ---------------------------------------------------------
# USER PROFILE
# ---------------------------------------------------------

def get_user_profile(user_id: str) -> Optional[Dict[str, Any]]:
    schema = safe_schema("atlas")
    if schema is None:
        return None  # CLI fallback

    query = (
        schema
        .table("profiles")
        .select("*")
        .eq("id", user_id)
    )

    rows = safe_execute(query)
    return rows[0] if rows else None


# ---------------------------------------------------------
# STREAK ENGINE SUPPORT
# ---------------------------------------------------------

def rpc_update_streak(user_id: str):
    client = get_supabase()
    if client is None:
        return None  # CLI fallback

    try:
        resp = client.rpc("update_streak", {"p_user_id": user_id}).execute()
        return getattr(resp, "data", None)
    except Exception:
        return None


# ---------------------------------------------------------
# LEADERBOARD SUPPORT
# ---------------------------------------------------------

def rpc_increment_user_xp(user_id: str, amount: int):
    client = get_supabase()
    if client is None:
        return None  # CLI fallback

    try:
        resp = client.rpc(
            "increment_user_xp",
            {"p_user_id": user_id, "p_xp_increment": amount}
        ).execute()
        return getattr(resp, "data", None)
    except Exception:
        return None


# ---------------------------------------------------------
# Module-level client (tests patch this)
# ---------------------------------------------------------

# DO NOT call get_supabase() at import time.
# This breaks tests and CLI because env vars are not set yet.
supabase = None
