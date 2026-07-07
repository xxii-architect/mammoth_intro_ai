# atlas_sync.py
from supabase import create_client, Client # type: ignore
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)  # type: ignore

def fetch_lessons(module: str):
    """Fetch all lessons for a given module."""
    result = (
        supabase.schema("atlas") # type: ignore
        .table("atlas_lessons")
        .select("*")
        .eq("module", module)
        .execute()
    )
    return result.data or []

def update_progress(user_id: str, lesson_id: str, status: str):
    """Update or insert user progress."""
    try:
        supabase.schema("atlas").table("atlas_progress").upsert({ # type: ignore
            "user_id": user_id,
            "lesson_id": lesson_id,
            "status": status
        }).execute()
        return f"✅ Progress updated: {status}"
    except Exception as e:
        return f"⚠️ Progress update failed: {e}"
