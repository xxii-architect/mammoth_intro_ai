import asyncio
import copy

import pytest
from fastapi import HTTPException

import api_server
import mammoth_os.llm_client as llm
from mammoth_os import tutor_delivery
from mammoth_os.learning_workspace import workspace_snapshot


@pytest.fixture
def learning(monkeypatch, tmp_path):
    state = {
        "active_account_id": "default", "tier": "pro", "lesson_id": "evidence-1",
        "current_lesson": {
            "title": "Evidence", "content": "## Primary evidence\n\nA primary source is an original record of an event.",
            "teaching_points": ["A primary source is an original record of an event."],
        },
        "current_exercise": {"prompt": "Explain how you verify a claim."},
        "last_submission": {"passed": False, "mastery_evidence": False,
                            "hint": "Include a primary source.", "criteria": [{"id": "evidence", "feedback": "An original source is missing."}]},
        "lesson_plan": {"difficulty": "beginner"}, "resume_packet": {"lesson_id": "evidence-1"},
    }
    prompts = []
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)
    monkeypatch.setattr(api_server, "_require_signed_in_api", lambda: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_hydrate_learner_state", lambda *args, **kwargs: {})
    monkeypatch.setattr(api_server, "_runtime_status_snapshot", lambda: {"state": "ready"})
    monkeypatch.setattr(api_server, "_remember_runtime_status", lambda *args: None)
    monkeypatch.setattr(api_server, "_runtime_metadata_from_client", lambda *args, **kwargs: {"active_adapter": "test-provider"})
    monkeypatch.setattr(api_server, "NOTES_FILE", tmp_path / "notes.json")
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_request_is_admin", lambda: False)
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda default="local": "learner-a")

    class Client:
        model = "test-model"

        async def generate(self, prompt, **kwargs):
            prompts.append(prompt)
            return "<think>Private reasoning must not appear inline.</think>Compare an original record with a later retelling."

    monkeypatch.setattr(llm, "get_llm_client", lambda config=None: Client())
    return state, prompts


def selection(state, **changes):
    return {"exercise_key": workspace_snapshot(state)["exercise_key"], "source": "lesson",
            "selection": "A primary source is an original record of an event.", **changes}


@pytest.mark.parametrize("action", ["explain", "example", "practice"])
def test_contextual_help_is_grounded_and_does_not_change_mastery(learning, action):
    state, prompts = learning
    before = copy.deepcopy(state)
    result = asyncio.run(api_server.atlas_chat({
        "contextual_help": {**selection(state), "action": action},
        "mode": "assistant", "regenerate_on_guard": True,
        "repo_context": {"root": "private-host-repo"},
    }))
    assert result["status"] == "ok" and result["mode"] == "tutor"
    assert len(prompts) == 1
    assert selection(state)["selection"] in prompts[0]
    assert "private-host-repo" not in prompts[0]
    assert "Private reasoning" not in result["reply"]
    assert "Private reasoning" in result["reasoning_trace"]
    assert result["quality"]["factual_verification"] == "not_verified"
    assert state["chat_history"][-1]["learning_context"]["section"] == "Primary evidence"
    for key in ("current_exercise", "last_submission", "current_lesson"):
        assert state[key] == before[key]


def test_remediation_uses_actual_feedback_without_asserting_a_diagnosis(learning):
    state, prompts = learning
    result = asyncio.run(api_server.atlas_chat({"contextual_help": {
        **selection(state, source="feedback", selection="Include a primary source."), "action": "remediate",
    }}))
    assert result["status"] == "ok"
    assert "not proof of its cause" in prompts[0]
    assert state["last_submission"]["passed"] is False
    assert state["last_submission"]["mastery_evidence"] is False


def test_quoted_lesson_text_is_not_mistaken_for_a_request_to_bypass_the_guard(learning):
    state, prompts = learning
    quote = 'A request saying "no explanation" omits the reasoning needed to evaluate a claim.'
    state["current_lesson"]["content"] = quote
    result = asyncio.run(api_server.atlas_chat({
        "contextual_help": {**selection(state, selection=quote), "action": "explain"},
    }))
    assert result["status"] == "ok" and len(prompts) == 1
    assert "do not provide direct final answers" in prompts[0]
    assert result["chat_history"][-1]["learning_context"]["quote"] == quote


@pytest.mark.parametrize("changes,status", [
    ({"selection": "A fabricated passage."}, 400), ({"selection": "x" * 4001}, 400),
    ({"source": "host"}, 400), ({"exercise_key": "old"}, 409),
    ({"action": "remediate"}, 400), ({"action": "unknown"}, 400),
])
def test_invalid_context_fails_before_a_model_call(learning, changes, status):
    state, prompts = learning
    with pytest.raises(HTTPException) as error:
        asyncio.run(api_server.atlas_chat({"contextual_help": {**selection(state), "action": "explain", **changes}}))
    assert error.value.status_code == status
    assert prompts == []
    assert "chat_history" not in state


def test_formatted_lesson_text_matches_the_rendered_selection(learning):
    state, _ = learning
    state["current_lesson"]["content"] = "## Sources\n\nA **primary source** is an [original record](https://example.test/record)."
    context = tutor_delivery.contextual_selection(state, selection(state, selection="A primary source is an original record."))
    assert context["section"] == "Sources"
    assert context["source_urls"] == ["https://example.test/record"]


def test_context_selection_handles_missing_optional_lists_and_italic_text(learning):
    state, _ = learning
    state["current_lesson"].update(content="A *primary source* is an original record.", teaching_points=None, examples=7)
    state["last_submission"]["criteria"] = None
    assert tutor_delivery.contextual_selection(state, selection(state, selection="A primary source is an original record."))["source"] == "lesson"
    assert tutor_delivery.contextual_selection(state, selection(state, source="feedback", selection="Include a primary source."))["source"] == "feedback"


def test_context_selection_accepts_authoritative_legacy_exercise_teaching_fields(learning):
    state, _ = learning
    state["current_lesson"] = {"title": "Evidence"}
    state["current_exercise"]["lesson_body"] = "Original records preserve first-hand evidence."
    state["current_exercise"]["lesson_examples"] = ["A signed field log records the original observation."]
    assert tutor_delivery.contextual_selection(state, selection(state, selection=state["current_exercise"]["lesson_body"]))["source"] == "lesson"
    assert tutor_delivery.contextual_selection(state, selection(state, selection=state["current_exercise"]["lesson_examples"][0]))["source"] == "lesson"


def test_unavailable_model_is_an_explicit_failure_without_a_successful_reply(learning, monkeypatch):
    state, _ = learning

    class Unavailable:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("insufficient_quota: private diagnostics")

    monkeypatch.setattr(llm, "get_llm_client", lambda config=None: Unavailable())
    with pytest.raises(HTTPException) as error:
        asyncio.run(api_server.atlas_chat({"contextual_help": {**selection(state), "action": "explain"}}))
    assert error.value.status_code == 503
    assert "insufficient_quota" not in error.value.detail
    assert "chat_history" not in state


def test_local_echo_is_not_presented_as_successful_tutoring(learning, monkeypatch):
    state, _ = learning
    monkeypatch.setattr(llm, "get_llm_client", lambda config=None: llm.LocalAdapter())
    with pytest.raises(HTTPException) as error:
        asyncio.run(api_server.atlas_chat({"contextual_help": {**selection(state), "action": "explain"}}))
    assert error.value.status_code == 503


def test_late_contextual_help_cannot_restore_an_old_lesson(learning, monkeypatch):
    state, _ = learning

    class Slow:
        model = "test-model"

        async def generate(self, *args, **kwargs):
            state["current_exercise"] = {"prompt": "The learner moved to a different exercise."}
            return "A helpful response generated for the previous exercise."

    monkeypatch.setattr(llm, "get_llm_client", lambda config=None: Slow())
    with pytest.raises(HTTPException) as error:
        asyncio.run(api_server.atlas_chat({"contextual_help": {**selection(state), "action": "explain"}}))
    assert error.value.status_code == 409
    assert state["current_exercise"]["prompt"] == "The learner moved to a different exercise."
    assert "chat_history" not in state


def test_contextual_help_merges_with_newer_history_instead_of_overwriting_it(learning, monkeypatch):
    state, _ = learning
    state["chat_history"] = [{"role": "assistant", "message": "Existing conversation."}]

    class Concurrent:
        model = "test-model"

        async def generate(self, *args, **kwargs):
            state["chat_history"].append({"role": "assistant", "message": "A concurrent answer."})
            state["unrelated_change"] = "Retain me"
            return "A helpful contextual explanation."

    monkeypatch.setattr(llm, "get_llm_client", lambda config=None: Concurrent())
    result = asyncio.run(api_server.atlas_chat({"contextual_help": {**selection(state), "action": "explain"}}))
    assert len(result["chat_history"]) == 4
    assert state["chat_history"][1]["message"] == "A concurrent answer."
    assert state["unrelated_change"] == "Retain me"


def test_preview_is_read_only_and_linked_cards_use_the_existing_store(learning):
    state, prompts = learning
    context = selection(state)
    preview = asyncio.run(api_server.atlas_study_preview({"learning_selection": context}))
    assert preview["status"] == "draft" and preview["model_calls"] == 0
    assert preview["cards"][0]["back"] == context["selection"]
    assert "study_aids" not in state
    saved = asyncio.run(api_server.create_flashcards({
        "learning_selection": context, "reviewed": True, "authorship": "source-derived", "cards": preview["cards"],
        "lesson_id": "untrusted-other-lesson",
    }))
    assert saved["lesson_id"] == state["lesson_id"]
    card = asyncio.run(api_server.get_flashcards())["cards"][0]
    assert card["learning_context"]["quote"] == context["selection"]
    assert card["learning_context"]["authorship"] == "source-derived"
    assert len(state["study_aids"]) == 1
    assert prompts == []


def test_reviewed_note_is_in_existing_notes_with_lesson_provenance(learning):
    state, prompts = learning
    note = asyncio.run(api_server.upsert_note({
        "learning_selection": selection(state), "reviewed": True, "authorship": "learner",
        "body": "My takeaway about original records.",
    }))
    assert note["type"] == "lesson_note" and note["user_id"] == "learner-a"
    context = note["metadata"]["learning_context"]
    assert context["lesson_id"] == state["lesson_id"]
    assert context["authorship"] == "learner"
    assert asyncio.run(api_server.get_notes())[0]["id"] == note["id"]
    assert api_server._matching_notes_for_lesson(state, state["lesson_id"])[0]["learning_context"] == context
    assert prompts == []


def test_linked_note_canonicalizes_body_and_content(learning):
    state, _ = learning
    note = asyncio.run(api_server.upsert_note({
        "learning_selection": selection(state), "reviewed": True, "authorship": "learner",
        "body": " Reviewed note. ", "content": "x" * 13000,
    }))
    assert note["body"] == note["content"] == "Reviewed note."


def test_note_tier_gate_stays_authoritative(learning):
    state, _ = learning
    state["tier"] = "explorer"
    result = asyncio.run(api_server.upsert_note({
        "learning_selection": selection(state), "reviewed": True, "authorship": "learner", "body": "Draft",
    }))
    assert result.status_code == 403


def test_linked_note_cannot_be_read_by_another_user_or_local_account(learning, monkeypatch):
    state, _ = learning
    asyncio.run(api_server.upsert_note({
        "learning_selection": selection(state), "reviewed": True, "authorship": "learner", "body": "Private linked note.",
    }))
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda default="local": "learner-b")
    assert asyncio.run(api_server.get_notes()) == []
    assert api_server._matching_notes_for_lesson(state, state["lesson_id"]) == []
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda default="local": "learner-a")
    state["active_account_id"] = "another-account"
    assert asyncio.run(api_server.get_notes()) == []


@pytest.mark.parametrize("kind", ["note", "card"])
def test_review_is_required_for_linked_study_saves(learning, kind):
    state, _ = learning
    body = {"learning_selection": selection(state), "authorship": "learner", "body": "Draft",
            "cards": [{"front": "Question?", "back": "Answer."}]}
    handler = api_server.upsert_note if kind == "note" else api_server.create_flashcards
    with pytest.raises(HTTPException) as error:
        asyncio.run(handler(body))
    assert error.value.status_code == 400
