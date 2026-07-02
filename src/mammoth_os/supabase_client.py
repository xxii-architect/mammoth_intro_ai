import os
from supabase import create_client, Client

_supabase: Client | None = None

def get_supabase() -> Client:
    """
    Global Supabase client accessor.
    Creates the client once and reuses it.
    """
    global _supabase
    if _supabase is not None:
        return _supabase

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError("Supabase environment variables not set")

    _supabase = create_client(url, key)
    return _supabase


# -----------------------------
# LESSONS / MODULES
# -----------------------------

def get_lessons_for_module(module_id: str):
    supabase = get_supabase()
    resp = (
        supabase
        .schema("atlas")
        .table("lessons")
        .select("*")
        .eq("module_id", module_id)
        .execute()
    )
    return getattr(resp, "data", [])


# -----------------------------
# USER PROFILE
# -----------------------------

def get_user_profile(user_id: str):
    supabase = get_supabase()
    resp = (
        supabase
        .schema("atlas")
        .table("profiles")
        .select("*")
        .eq("id", user_id)
        .execute()
    )
    rows = getattr(resp, "data", [])
    return rows[0] if rows else None


# -----------------------------
# STREAK ENGINE SUPPORT
# -----------------------------

def rpc_update_streak(user_id: str):
    supabase = get_supabase()
    resp = supabase.rpc("update_streak", {"p_user_id": user_id}).execute()
    return getattr(resp, "data", None)


# -----------------------------
# LEADERBOARD SUPPORT
# -----------------------------

def rpc_increment_user_xp(user_id: str, amount: int):
    supabase = get_supabase()
    resp = supabase.rpc(
        "increment_user_xp",
        {"p_user_id": user_id, "p_xp_increment": amount}
    ).execute()
    return getattr(resp, "data", None)

# ---------------------------------------------------------
# Module-level Supabase client (required by Mammoth OS engines)
# ---------------------------------------------------------

supabase = get_supabase()