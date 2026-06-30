# adaptive_engine.py
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
supabase: Client = create_client(url, key)  # type: ignore


def analyze_performance(user_id: str):
    """Analyze user performance and suggest next difficulty."""
    result = (
        supabase.schema("atlas")
        .table("adaptive_metrics")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )
    data = result.data or []
    if not data:
        return "medium"

    # 🧩 Safe numeric conversion helpers
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _to_seconds(value):
        try:
            # Supabase interval fields often come back as dicts like {"seconds": 1234}
            if isinstance(value, dict) and "seconds" in value:
                return int(value["seconds"])
            return int(value) # type: ignore
        except (TypeError, ValueError):
            return 0

    avg_score = sum(_to_float(row.get("performance_score")) for row in data) / len(data) # type: ignore
    avg_time = sum(_to_seconds(row.get("completion_time")) for row in data) / len(data) # type: ignore

    if avg_score > 85 and avg_time < 600:
        return "hard"
    elif avg_score < 60 or avg_time > 1800:
        return "easy"
    else:
        return "medium"


def suggest_next_lesson(user_id: str):
    """Suggest next lesson based on adaptive difficulty."""
    difficulty = analyze_performance(user_id)
    lessons = (
        supabase.schema("atlas")
        .table("atlas_lessons")
        .select("*")
        .eq("module", difficulty)
        .execute()
    )
    if not lessons.data:
        return f"No lessons found for difficulty '{difficulty}'."
    next_lesson = lessons.data[0]
    return f"🧭 Suggested next lesson: {next_lesson['lesson_title']} ({difficulty})" # type: ignore
