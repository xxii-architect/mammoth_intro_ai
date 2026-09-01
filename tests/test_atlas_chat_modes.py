import asyncio

import api_server
import mammoth_os.llm_client as llm_client_mod


class DummyClient:
    def __init__(self, prompt_log):
        self.prompt_log = prompt_log
        self.model = "dummy-model"

    async def generate(self, prompt: str, **kwargs) -> str:
        self.prompt_log.append(prompt)
        return "ok-response"


def test_atlas_chat_assistant_mode_uses_separate_history_and_no_guard(monkeypatch):
    prompt_log = []
    state = {
        "current_exercise": {"prompt": "Write a function"},
        "current_lesson": {"title": "Lesson 1"},
        "lesson_plan": {},
        "resume_packet": {},
    }

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_hydrate_learner_state", lambda *args, **kwargs: {})
    monkeypatch.setattr(api_server, "_is_answer_seeking_request", lambda message: True)
    monkeypatch.setattr(llm_client_mod, "get_llm_client", lambda config=None: DummyClient(prompt_log))

    response = asyncio.run(
        api_server.atlas_chat(
            {
                "message": "Just chat with me like normal AI.",
                "mode": "assistant",
                "strict_guard": True,
            }
        )
    )

    assert response["status"] == "ok"
    assert response["guard_triggered"] is False
    assert response["mode"] == "assistant"
    assert state.get("assistant_chat_history")
    assert "chat_history" not in state or state.get("chat_history") == []
    assert prompt_log and "MammothOS Assistant" in prompt_log[-1]


def test_atlas_chat_tutor_mode_keeps_guard_behavior(monkeypatch):
    state = {
        "current_exercise": {"prompt": "Write a function"},
        "current_lesson": {"title": "Lesson 1"},
        "lesson_plan": {},
        "resume_packet": {},
    }

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_hydrate_learner_state", lambda *args, **kwargs: {})
    monkeypatch.setattr(api_server, "_is_answer_seeking_request", lambda message: True)

    response = asyncio.run(
        api_server.atlas_chat(
            {
                "message": "Give me the exact answer.",
                "mode": "tutor",
                "strict_guard": True,
            }
        )
    )

    assert response["status"] == "ok"
    assert response["guard_triggered"] is True
    assert state.get("chat_history")


def test_atlas_chat_guide_command_routes_to_mammoth_guide(monkeypatch):
    state = {
        "current_exercise": {},
        "current_lesson": {"title": "Lesson 1"},
        "lesson_plan": {},
        "resume_packet": {},
    }

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_hydrate_learner_state", lambda *args, **kwargs: {})
    monkeypatch.setattr(api_server, "registry_run_agent", lambda name, payload: {"message": f"guide::{payload.get('message')}", "repo_context_used": True})

    response = asyncio.run(
        api_server.atlas_chat(
            {
                "message": "/guide show sdk entry points",
                "mode": "assistant",
                "repo_context": {"query": "sdk", "files": ["src/mammoth_os/sdk.py"]},
            }
        )
    )

    assert response["status"] == "ok"
    assert response["adapter"] == "mammoth-guide"
    assert "guide::show sdk entry points" in response["reply"]
