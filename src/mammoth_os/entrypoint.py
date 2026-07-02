"""
Mammoth OS — EntryPoint
Unified interface for Command Center V3, CLI tools, and API calls.
"""

from typing import Dict, Any

from mammoth_os.cortex.router import CortexRouter
from mammoth_os.curriculum_engine import CurriculumEngine # type: ignore
from mammoth_os.leaderboard_engine import get_leaderboard, get_streak # type: ignore
from mammoth_os.autonomous_engine import AutonomousEngine # type: ignore


class MammothOS:
    """
    Public interface for the entire Mammoth OS system.
    Command Center V3 calls ONLY this class.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.router = CortexRouter(user_id=user_id)
        self.curriculum = CurriculumEngine(user_id=user_id)
        self.engine = AutonomousEngine(user_id=user_id)

    # ---------------------------------------------------------
    # AGENT EXECUTION
    # ---------------------------------------------------------

    def run_agent(self, agent_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.engine.run_task(agent_name, payload)

    def run_intent(self, intent: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.router.route(intent, payload)

    # ---------------------------------------------------------
    # CURRICULUM
    # ---------------------------------------------------------

    def next_lesson(self, module_id: str) -> Dict[str, Any] | None:
        return self.curriculum.get_next_lesson(module_id)

    def run_next_lesson(self, module_id: str) -> Dict[str, Any]:
        lesson = self.curriculum.get_next_lesson(module_id)
        if not lesson:
            return {"ok": True, "message": "Module complete."}
        return self.curriculum.run_lesson(lesson)

    def complete_lesson(self, lesson_id: str) -> Dict[str, Any]:
        return self.curriculum.complete_lesson(lesson_id)

    # ---------------------------------------------------------
    # LEADERBOARD + STREAK
    # ---------------------------------------------------------

    def leaderboard(self) -> Dict[str, Any]:
        return get_leaderboard()

    def streak(self) -> Dict[str, Any]:
        return get_streak(self.user_id)

    # ---------------------------------------------------------
    # VISUAL / BRAND / MARKET INTEL (direct agent calls)
    # ---------------------------------------------------------

    def visual(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_agent("visual_engine", payload)

    def brand_voice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_agent("brand_voice", payload)

    def market_intel(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_agent("market_intel", payload)

    def field_ops(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_agent("field_ops", payload)

    def plant_seed(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_agent("plant_the_seed", payload)

    def reflection(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_agent("reflection", payload)

    def community(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self.run_agent("community_engine", payload)
