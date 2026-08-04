import asyncio
import importlib

import api_server


def test_atlas_modules_returns_catalog_and_active_module(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_load_atlas_state",
        lambda: {
            "module_id": "ham-radio",
            "topic": "Ham radio fundamentals call signs and emergency comms basics",
        },
    )

    result = asyncio.run(api_server.atlas_modules())

    assert result["status"] == "ok"
    assert len(result["modules"]) >= 5
    assert {item["id"] for item in result["modules"]} >= {
        "wilderness-survival",
        "hunting-fishing",
        "ham-radio",
        "emt-emergency-management",
        "horticulture-weather",
    }
    assert result["active_module"]["id"] == "ham-radio"


def test_atlas_lesson_uses_module_track_to_expand_curriculum_prompt(monkeypatch):
    state = {}
    saved = {}
    call_log = {}

    class DummySession:
        def __init__(self, user_id="default_user"):
            self.user_id = user_id
            self.curriculum = {"curriculum_id": "curr-1", "modules": [{"title": "Radio", "lessons": [{"lesson_id": "lesson-1", "title": "Check-in basics"}]}]}
            self.current_lesson = {"lesson_id": "lesson-1", "title": "Check-in basics", "objectives": ["Use disciplined call-sign etiquette"]}
            self.current_exercise = None
            self._curriculum_id = "curr-1"
            self._lesson_id = "lesson-1"

        def start_lesson(self, topic, difficulty="beginner", learner_context=None):
            call_log["topic"] = topic
            call_log["difficulty"] = difficulty
            call_log["learner_context"] = learner_context or {}
            self.current_exercise = {
                "exercise_id": "ex-1",
                "title": "Practice radio check-ins",
                "prompt": "Draft a disciplined radio check-in.",
                "starter_files": {"solution.py": "message = ''\n"},
                "expected_test": "assert True\n",
                "lesson_id": self._lesson_id,
            }
            return self.current_exercise

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda updated: saved.setdefault("state", dict(updated)))
    monkeypatch.setattr(api_server, "_append_lesson_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api_server,
        "_hydrate_learner_state",
        lambda current_state, **kwargs: current_state.setdefault(
            "learner_context",
            {"recommended_difficulty": "beginner", "preferred_pacing": "gentle"},
        ),
    )
    monkeypatch.setattr(
        api_server,
        "build_lesson_plan",
        lambda current_state, topic: {
            "difficulty": "beginner",
            "suggested_topic": topic,
            "rationale": "Keep it practical.",
        },
    )

    atlas_session = importlib.import_module("mammoth_os.atlas_session")
    monkeypatch.setattr(atlas_session, "ATLASSession", DummySession)

    result = asyncio.run(api_server.atlas_lesson({"module_id": "ham-radio"}))

    assert result["status"] == "ok"
    assert result["active_module"]["id"] == "ham-radio"
    assert "Ham Radio" in call_log["topic"]
    assert "Call-sign etiquette and net discipline basics" in call_log["topic"]
    assert call_log["learner_context"]["module_track"]["id"] == "ham-radio"
    assert saved["state"]["module_id"] == "ham-radio"
    assert saved["state"]["active_module"]["label"] == "Ham Radio"


def test_atlas_plan_steps_include_curriculum_and_tutor_for_lesson_flow():
    steps = api_server._build_atlas_plan_steps(
        {
            "module_id": "ham-radio",
            "topic": "Ham radio fundamentals",
            "current_lesson": {"title": "Check-in basics"},
            "current_exercise": {"prompt": "Draft a disciplined radio check-in."},
            "learner_context": {"recommended_difficulty": "beginner"},
        },
        plan_profile="atlas",
    )

    agent_ids = [step["agent_id"] for step in steps]
    assert "curriculum_agent" in agent_ids
    assert "tutor_agent" in agent_ids


def test_atlas_plan_autonomous_profile_adds_community_and_custodial_steps():
    steps = api_server._build_atlas_plan_steps(
        {
            "module_id": "ham-radio",
            "topic": "Ham radio fundamentals",
            "current_lesson": {"title": "Check-in basics"},
            "current_exercise": {"prompt": "Draft a disciplined radio check-in."},
            "learner_context": {"recommended_difficulty": "beginner"},
        },
        plan_profile="autonomous",
    )

    agent_ids = [step["agent_id"] for step in steps]
    assert "community_engine_agent" in agent_ids
    assert "custodial_agent" in agent_ids
