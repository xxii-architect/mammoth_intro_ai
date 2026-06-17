import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")

supabase = create_client(url, key)

def create_user(email: str, display_name: str, avatar_url: str = None):
    data = {
        "email": email,
        "display_name": display_name,
        "avatar_url": avatar_url
    }
    return supabase.table("mammoth.users").insert(data).execute()

def get_user_by_email(email: str):
    return (
        supabase.table("mammoth.users")
        .select("*")
        .eq("email", email)
        .execute()
    )

def get_user_by_id(user_id: str):
    return (
        supabase.table("mammoth.users")
        .select("*")
        .eq("id", user_id)
        .execute()
    )

def update_user(user_id: str, updates: dict):
    return (
        supabase.table("mammoth.users")
        .update(updates)
        .eq("id", user_id)
        .execute()
    )

# -------------------------
# MODULES TABLE
# -------------------------

def create_module(title: str, description: str, order_index: int):
    data = {
        "title": title,
        "description": description,
        "order_index": order_index
    }
    return supabase.table("mammoth.modules").insert(data).execute()

def get_all_modules():
    return (
        supabase.table("mammoth.modules")
        .select("*")
        .order("order_index")
        .execute()
    )

# -------------------------
# LESSONS TABLE
# -------------------------

def create_lesson(module_id: str, title: str, content: str, order_index: int):
    data = {
        "module_id": module_id,
        "title": title,
        "content": content,
        "order_index": order_index
    }
    return supabase.table("mammoth.lessons").insert(data).execute()

def get_lessons_for_module(module_id: str):
    return (
        supabase.table("mammoth.lessons")
        .select("*")
        .eq("module_id", module_id)
        .order("order_index")
        .execute()
    )

# -------------------------
# PROGRESS TABLE
# -------------------------

def mark_lesson_complete(user_id: str, lesson_id: str):
    data = {
        "user_id": user_id,
        "lesson_id": lesson_id
    }
    return supabase.table("mammoth.progress").insert(data).execute()

def get_user_progress(user_id: str):
    return (
        supabase.table("mammoth.progress")
        .select("lesson_id, completed_at")
        .eq("user_id", user_id)
        .execute()
    )

# -------------------------
# NOTES TABLE
# -------------------------

def add_note(user_id: str, lesson_id: str, content: str):
    data = {
        "user_id": user_id,
        "lesson_id": lesson_id,
        "content": content
    }
    return supabase.table("mammoth.notes").insert(data).execute()

def get_notes_for_lesson(user_id: str, lesson_id: str):
    return (
        supabase.table("mammoth.notes")
        .select("*")
        .eq("user_id", user_id)
        .eq("lesson_id", lesson_id)
        .execute()
    )

# -------------------------
# ACTIVITY LOG TABLE
# -------------------------

def log_action(user_id: str, action: str, metadata: dict = None):
    data = {
        "user_id": user_id,
        "action": action,
        "metadata": metadata
    }
    return supabase.table("mammoth.activity_log").insert(data).execute()

# -------------------------
# AI SESSIONS TABLE
# -------------------------

def save_ai_session(user_id: str, prompt: str, response: str, tokens_used: int, metadata: dict = None):
    data = {
        "user_id": user_id,
        "prompt": prompt,
        "response": response,
        "tokens_used": tokens_used,
        "metadata": metadata
    }
    return supabase.table("mammoth.ai_sessions").insert(data).execute()

def get_ai_sessions_for_user(user_id: str):
    return (
        supabase.table("mammoth.ai_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

