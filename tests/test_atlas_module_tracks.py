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
    assert len(result["modules"]) >= 20
    assert {item["id"] for item in result["modules"]} >= {
        "wilderness-survival",
        "hunting-fishing",
        "ham-radio",
        "emt-emergency-management",
        "horticulture-weather",
        "human-systems-neurobiology",
        "environmental-human-dynamics",
        "mind-body-resilience",
        "personal-finance",
        "python-programming",
        "fitness-training",
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


def test_atlas_lesson_noncode_track_returns_text_submission_contract(monkeypatch):
    state = {}

    class DummySession:
        def __init__(self, user_id="default_user"):
            self.user_id = user_id
            self.curriculum = {"curriculum_id": "curr-1", "modules": [{"title": "EMT", "lessons": [{"lesson_id": "lesson-1", "title": "Scene safety"}]}]}
            self.current_lesson = {"lesson_id": "lesson-1", "title": "Scene safety", "objectives": ["Assess scene safety", "Prioritize immediate care"]}
            self.current_exercise = None
            self._curriculum_id = "curr-1"
            self._lesson_id = "lesson-1"

        def start_lesson(self, topic, difficulty="beginner", learner_context=None):
            self.current_exercise = {
                "exercise_id": "ex-1",
                "title": "Scene safety",
                "prompt": "generic placeholder",
                "starter_files": {"solution.py": "def solution():\n    pass\n"},
                "expected_test": "assert True\n",
                "lesson_id": self._lesson_id,
            }
            return self.current_exercise

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda updated: None)
    monkeypatch.setattr(api_server, "_append_lesson_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api_server,
        "_hydrate_learner_state",
        lambda current_state, **kwargs: current_state.setdefault("learner_context", {"recommended_difficulty": "beginner"}),
    )
    monkeypatch.setattr(
        api_server,
        "build_lesson_plan",
        lambda current_state, topic: {"difficulty": "beginner", "suggested_topic": topic},
    )

    atlas_session = importlib.import_module("mammoth_os.atlas_session")
    monkeypatch.setattr(atlas_session, "ATLASSession", DummySession)

    result = asyncio.run(api_server.atlas_lesson({"module_id": "emt-emergency-management"}))

    assert result["status"] == "ok"
    assert result["active_module"]["id"] == "emt-emergency-management"
    assert result["exercise"]["submission_mode"] == "text"
    assert result["exercise"]["lesson_type"] == "knowledge"
    assert result["exercise"]["starter_files"] == {}
    assert "Teach this topic in plain language" in result["exercise"]["prompt"]
    assert "starter_response" in result["exercise"]


def test_atlas_lesson_preserves_llm_generated_text_exercise_contract(monkeypatch):
    state = {}

    class DummySession:
        def __init__(self, user_id="default_user"):
            self.user_id = user_id
            self.curriculum = {"curriculum_id": "curr-1", "modules": [{"title": "Ham Radio", "lessons": [{"lesson_id": "lesson-1", "title": "Check-in basics"}]}]}
            self.current_lesson = {
                "lesson_id": "lesson-1",
                "title": "Check-in basics",
                "objectives": ["Use call signs clearly", "Keep transmissions concise"],
                "summary": "Learn how to make a clean beginner-friendly radio check-in.",
                "content": "Start with your call sign, identify who you are calling, and keep the message short.",
                "teaching_points": ["Use your call sign", "State the purpose", "Close the message cleanly"],
                "examples": ["Example: 'Kilo Bravo 9, radio check on the local repeater.'"],
                "source": "llm_generated",
            }
            self.current_exercise = None
            self._curriculum_id = "curr-1"
            self._lesson_id = "lesson-1"

        def start_lesson(self, topic, difficulty="beginner", learner_context=None):
            self.current_exercise = {
                "exercise_id": "ex-1",
                "title": "Radio Check-In Walkthrough",
                "prompt": "Write a short beginner-friendly radio check-in for a local net.",
                "starter_files": {},
                "starter_response": "Call sign:\nPurpose:\nMain message:\nClose-out:\n",
                "expected_test": "Lesson rubric:\n- Uses a call sign\n- States a clear purpose\n- Keeps the message concise",
                "generation_method": "llm",
                "lesson_id": self._lesson_id,
            }
            return self.current_exercise

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda updated: None)
    monkeypatch.setattr(api_server, "_append_lesson_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api_server,
        "_hydrate_learner_state",
        lambda current_state, **kwargs: current_state.setdefault("learner_context", {"recommended_difficulty": "beginner"}),
    )
    monkeypatch.setattr(
        api_server,
        "build_lesson_plan",
        lambda current_state, topic: {"difficulty": "beginner", "suggested_topic": topic},
    )

    atlas_session = importlib.import_module("mammoth_os.atlas_session")
    monkeypatch.setattr(atlas_session, "ATLASSession", DummySession)

    result = asyncio.run(api_server.atlas_lesson({"module_id": "ham-radio"}))

    assert result["status"] == "ok"
    assert result["exercise"]["prompt"] == "Write a short beginner-friendly radio check-in for a local net."
    assert "Call sign:" in result["exercise"]["starter_response"]
    assert result["exercise"]["lesson_examples"]


def test_atlas_library_snapshot_surfaces_persisted_chunks(monkeypatch):
    state = {
        "topic": "Wilderness navigation survival and safety fundamentals",
        "module_id": "wilderness-survival",
        "active_module": {"id": "wilderness-survival", "label": "Wilderness Navigation + Survival"},
        "curriculum": {
            "source": "llm_enriched",
            "modules": [
                {
                    "module_id": "m1",
                    "title": "Module 1",
                    "lessons": [
                        {
                            "lesson_id": "lesson-1",
                            "title": "Map and Compass Basics",
                            "content": "Orient the map and identify major terrain features before moving.",
                            "teaching_points": ["Orient the map", "Use terrain features"],
                            "examples": ["Example 1"],
                            "source": "llm_generated",
                        },
                        {
                            "lesson_id": "lesson-2",
                            "title": "Route Planning",
                            "content": "Plan conservative routes and check hazards.",
                            "teaching_points": ["Plan conservative routes"],
                            "examples": [],
                            "source": "template",
                        },
                    ],
                }
            ],
        },
    }

    class FakeRetriever:
        async def load_lesson_chunks(self, lesson_id):
            if lesson_id == "lesson-1":
                return [{"lesson_id": lesson_id, "chunk_index": 0, "chunk_text": "Orient the map."}]
            return []

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_hydrate_learner_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "get_retriever", lambda: FakeRetriever())

    result = asyncio.run(api_server.atlas_library())

    assert result["status"] == "ok"
    assert result["curriculum_source"] == "llm_enriched"
    assert result["totals"]["lessons"] == 2
    assert result["totals"]["persisted_lessons"] == 1
    assert result["modules"][0]["lessons"][0]["persisted"] is True
    assert result["modules"][0]["lessons"][0]["chunk_count"] == 1
    assert result["modules"][0]["lessons"][1]["persisted"] is False


def test_atlas_next_moves_to_next_module_and_updates_progress_state(monkeypatch):
    state = {
        "topic": "python fundamentals",
        "module_id": "module-1",
        "lesson_id": "lesson-2",
        "curriculum": {
            "modules": [
                {
                    "module_id": "module-1",
                    "title": "Module 1",
                    "lessons": [
                        {"lesson_id": "lesson-1", "title": "Intro"},
                        {"lesson_id": "lesson-2", "title": "Variables"},
                    ],
                },
                {
                    "module_id": "module-2",
                    "title": "Module 2",
                    "lessons": [
                        {"lesson_id": "lesson-3", "title": "Functions"},
                    ],
                },
            ]
        },
    }

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda updated: None)
    monkeypatch.setattr(api_server, "_append_lesson_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda *args, **kwargs: None)

    result = asyncio.run(api_server.atlas_next())

    assert result["status"] == "ok"
    assert result["module_id"] == "module-2"
    assert result["lesson_id"] == "lesson-3"
    assert state["module_id"] == "module-2"
    assert state["lesson_id"] == "lesson-3"
    assert state["active_module"]["id"] == "module-2"


def test_atlas_lesson_noncode_track_sanitizes_python_seed_payload(monkeypatch):
    state = {}

    class DummySession:
        def __init__(self, user_id="default_user"):
            self.user_id = user_id
            self.curriculum = {
                "curriculum_id": "curr-1",
                "modules": [{"title": "Wilderness", "lessons": [{"lesson_id": "lesson-1", "title": "Lesson 1 — Python Environment Setup"}]}],
            }
            self.current_lesson = {
                "lesson_id": "lesson-1",
                "title": "Lesson 1 — Python Environment Setup",
                "objectives": ["Understand Lesson 1 — Python Environment Setup", "Apply lesson concepts in code"],
                "content": "Install Python and pip in a virtualenv.",
                "summary": "Python setup basics.",
            }
            self.current_exercise = None
            self._curriculum_id = "curr-1"
            self._lesson_id = "lesson-1"

        def start_lesson(self, topic, difficulty="beginner", learner_context=None):
            self.current_exercise = {
                "exercise_id": "ex-1",
                "title": "Lesson 1 — Python Environment Setup",
                "prompt": "Implement a Python helper function called solution.",
                "starter_files": {"solution.py": "def solution():\n    pass\n"},
                "expected_test": "assert True\n",
                "lesson_id": self._lesson_id,
            }
            return self.current_exercise

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda updated: None)
    monkeypatch.setattr(api_server, "_append_lesson_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        api_server,
        "_hydrate_learner_state",
        lambda current_state, **kwargs: current_state.setdefault("learner_context", {"recommended_difficulty": "beginner"}),
    )
    monkeypatch.setattr(
        api_server,
        "build_lesson_plan",
        lambda current_state, topic: {"difficulty": "beginner", "suggested_topic": topic},
    )

    atlas_session = importlib.import_module("mammoth_os.atlas_session")
    monkeypatch.setattr(atlas_session, "ATLASSession", DummySession)

    result = asyncio.run(api_server.atlas_lesson({"module_id": "wilderness-survival"}))

    assert result["status"] == "ok"
    assert "python environment setup" not in result["exercise"]["title"].lower()
    assert "python helper function" not in result["exercise"]["prompt"].lower()
    assert result["exercise"]["submission_mode"] == "text"


def test_atlas_submit_text_submission_scores_topic_specific_response(monkeypatch):
    state = {
        "topic": "EMT and emergency management triage and incident fundamentals",
        "module_id": "emt-emergency-management",
        "curriculum": {"modules": []},
        "current_lesson": {
            "lesson_id": "lesson-1",
            "title": "EMT + Emergency Mgmt — Foundations Lesson 1",
            "objectives": ["Assess scene safety", "Prioritize patient communication"],
        },
        "current_exercise": {
            "exercise_id": "ex-1",
            "submission_mode": "text",
            "lesson_type": "knowledge",
            "prompt": "Teach this topic in plain language.",
        },
        "curriculum_id": "curr-1",
        "lesson_id": "lesson-1",
    }

    saved = {}
    memory_calls = {"awaited": False, "items": []}

    class FakeMemoryEngine:
        async def store(self, content, memory_type="semantic", metadata=None):
            memory_calls["awaited"] = True
            memory_calls["items"].append(
                {
                    "content": content,
                    "memory_type": memory_type,
                    "metadata": dict(metadata or {}),
                }
            )
            return "memory-1"

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda updated: saved.setdefault("state", dict(updated)))
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_record_submission_on_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_MEMORY_ENGINE", FakeMemoryEngine())
    monkeypatch.setattr(
        api_server,
        "_hydrate_learner_state",
        lambda current_state, **kwargs: current_state.setdefault("learner_context", {"adaptive_coaching": {"hint_depth": "guided"}}),
    )

    result = asyncio.run(
        api_server.atlas_submit(
            {
                "response": (
                    "EMT scene safety starts with checking for hazards, controlling the area, and communicating calmly with the patient. "
                    "A beginner should prioritize scene safety first, then patient communication, then basic triage steps and escalation."
                )
            }
        )
    )

    assert result["status"] == "ok"
    assert result["result"]["submission_mode"] == "text"
    assert result["result"]["passed"] is True
    assert result["result"]["score"] >= 0.5
    assert saved["state"]["last_submission"]["submission_mode"] == "text"
    assert memory_calls["awaited"] is True
    assert memory_calls["items"][0]["memory_type"] == "atlas_outcome"


def test_atlas_regenerate_route_is_registered():
    routes = [
        route
        for route in api_server.app.routes
        if getattr(route, "path", None) == "/api/atlas/regenerate"
    ]
    assert routes
    assert any("POST" in (getattr(route, "methods", set()) or set()) for route in routes)


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
