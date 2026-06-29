# src/mammoth_os/streak_engine.py

import logging
from mammoth_os.supabase_client import get_supabase

logger = logging.getLogger(__name__)

def get_user_streak(user_id: str):
    supabase = get_supabase()
    resp = supabase.schema("atlas").table("streaks").select("*").eq("user_id", user_id).execute()
    rows = getattr(resp, "data", []) or []
    return rows[0] if rows else None

def update_streak(user_id: str):
    supabase = get_supabase()
    record = get_user_streak(user_id)

    if record:
        new_streak = int(record.get("streak", 0)) + 1
        supabase.schema("atlas").table("streaks").update({"streak": new_streak}).eq("user_id", user_id).execute()
        return {"status": "ok", "streak": new_streak}

    supabase.schema("atlas").table("streaks").insert({"user_id": user_id, "streak": 1}).execute()
    return {"status": "ok", "streak": 1}
