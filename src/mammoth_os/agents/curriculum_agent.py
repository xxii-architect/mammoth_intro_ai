"""
Mammoth OS — Curriculum Engine
Handles lesson retrieval, sequencing, completion, and agent-driven learning tasks.
"""

from typing import Dict, Any, List, Optional
from mammoth_os.supabase_client import get_supabase
from mammoth_os.autonomous_engine import AutonomousEngine # type: ignore
from mammoth_os.leaderboard_engine import sync_streak_and_xp # type: ignore


class CurriculumEngine:
    """
    High-level learning engine for Mammoth OS.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.engine = AutonomousEngine(user_id=user_id)

    # ---------------------------------------------------------
    # MODULE + LESSON FETCHING
    # ---------------------------------------------------------

    def get_module(self, module_id: str) -> Optional[Dict[str, Any]]:
        supabase = get_supabase()
        resp = (
            supabase
            .schema("atlas")
            .table("modules")
            .select("*")
            .eq("id", module_id)
            .limit(1)
            .execute()
        )
        rows = getattr(resp, "data", []) or []
        return rows[0] if rows else None

    def get_lessons(self, module_id: str) -> List[Dict[str, Any]]:
        supabase = get_supabase()
        resp = (
            supabase
            .schema("atlas")
            .table("lessons")
            .select("*")
            .eq("module_id", module_id)
            .order("order_index", ascending=True) # type: ignore
            .execute()
        )
        return getattr(resp, "data", []) or []

    # ---------------------------------------------------------
    # NEXT LESSON LOGIC
    # ---------------------------------------------------------

    def get_next_lesson(self, module_id: str) -> Optional[Dict[str, Any]]:
        lessons = self.get_lessons(module_id)

        supabase = get_supabase()
        progress_resp = (
            supabase
            .schema("atlas")
            .table("lesson_progress")
            .select("lesson_id")
            .eq("user_id", self.user_id)
            .execute()
        )
        completed_ids = {row["lesson_id"] for row in getattr(progress_resp, "data", []) or []}

        for lesson in lessons:
            if lesson["id"] not in completed_ids:
                return lesson

        return None  # module complete

    # ---------------------------------------------------------
    # COMPLETE LESSON
    # ---------------------------------------------------------

    def complete_lesson(self, lesson_id: str) -> Dict[str, Any]:
        supabase = get_supabase()

        # Mark lesson complete
        supabase.schema("atlas").table("lesson_progress").upsert({
            "user_id": self.user_id,
            "lesson_id": lesson_id,
        }).execute()

        # Award XP + update streak
        xp_result = sync_streak_and_xp(self.user_id, xp_gain=25)

        return {
            "lesson_id": lesson_id,
            "xp": xp_result["xp"],
            "rank": xp_result["rank"],
            "streak": xp_result["streak"],
        }

    # ---------------------------------------------------------
    # RUN LESSON THROUGH AGENT
    # ---------------------------------------------------------

    def run_lesson(self, lesson: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lessons specify which agent should handle them.
        Example lesson structure:
        {
            "id": "...",
            "module_id": "...",
            "title": "...",
            "content": "...",
            "agent": "reflection",
            "payload": {...}
        }
        """
        agent_name = lesson.get("agent", "reflection")
        payload = lesson.get("payload", {"content": lesson.get("content")})

        return self.engine.run_task(agent_name, payload)
