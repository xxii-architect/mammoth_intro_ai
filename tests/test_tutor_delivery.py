import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

import api_server
from mammoth_os import tutor_delivery
from mammoth_os.atlas_session import ATLASSession, LessonGateError


CODE_EXERCISE = {
    "exercise_id": "ex-1",
    "lesson_id": "lesson-2",
    "title": "Add two numbers",
    "prompt": "Write solution(a, b) that returns the sum.",
    "expected_test": (
        "from solution import solution\n\n"
        "def test_add():\n"
        "    assert solution(2, 3) == 5\n"
        "    assert solution(-1, 1) == 0\n"
    ),
}

CURRICULUM = {
    "modules": [
        {
            "module_id": "module-1",
            "title": "Module 1",
            "lessons": [
                {"lesson_id": "lesson-1", "title": "Intro"},
                {"lesson_id": "lesson-2", "title": "Functions", "objectives": ["Define a function", "Return values"]},
                {"lesson_id": "lesson-3", "title": "Loops"},
            ],
        }
    ]
}


def _failing(stderr="AssertionError: assert 4 == 5"):
    return {"passed": False, "result": {"stderr": stderr}}


# --- manifest -----------------------------------------------------------------

def test_manifest_derives_examples_criteria_and_prereqs_from_real_data():
    lesson = CURRICULUM["modules"][0]["lessons"][1]
    manifest = tutor_delivery.build_lesson_manifest(lesson, CODE_EXERCISE, CURRICULUM)

    assert manifest["contract"] == tutor_delivery.MANIFEST_CONTRACT
    assert manifest["lesson_id"] == "lesson-2"
    assert manifest["prerequisites"] == ["Intro"]
    assert manifest["objectives"] == ["Define a function", "Return values"]
    assert manifest["submission_mode"] == "code"
    assert manifest["sample_data"] == ["solution(2, 3)", "solution(-1, 1)"]
    assert manifest["expected_output"] == ["solution(2, 3) -> 5", "solution(-1, 1) -> 0"]
    assert manifest["success_criteria"][0] == "All provided tests pass."
    assert "`solution(2, 3)` returns `5`." in manifest["success_criteria"]


def test_manifest_does_not_invent_content_when_data_is_missing():
    manifest = tutor_delivery.build_lesson_manifest({"lesson_id": "x", "title": "Reading"}, {}, None)
    assert manifest["has_exercise"] is False
    assert manifest["prerequisites"] == []
    assert manifest["sample_data"] == []
    assert manifest["expected_output"] == []
    assert manifest["success_criteria"] == []
    assert manifest["estimated_minutes"] is None


def test_manifest_prefers_explicit_fields_and_handles_text_rubrics():
    exercise = {
        "prompt": "Explain recursion.",
        "submission_mode": "text",
        "expected_test": "- Mentions a base case\n- Mentions the recursive step\n",
    }
    manifest = tutor_delivery.build_lesson_manifest(
        {"lesson_id": "r", "prerequisites": ["Functions"], "estimated_minutes": "15"}, exercise
    )
    assert manifest["prerequisites"] == ["Functions"]
    assert manifest["success_criteria"] == ["Mentions a base case", "Mentions the recursive step"]
    assert manifest["sample_data"] == []
    assert manifest["estimated_minutes"] == 15


def test_manifest_tolerates_unparseable_tests():
    manifest = tutor_delivery.build_lesson_manifest({"lesson_id": "x"}, {"prompt": "p", "expected_test": "assert ((("})
    assert manifest["sample_data"] == []
    assert manifest["success_criteria"] == ["All provided tests pass."]


# --- telemetry / stall ----------------------------------------------------------

def test_repeated_identical_error_flags_stall_with_targeted_suggestion():
    telemetry = {}
    tutor_delivery.record_attempt(telemetry, "l1", _failing())
    entry = tutor_delivery.record_attempt(telemetry, "l1", _failing("AssertionError: assert 7 == 5"))
    signal = tutor_delivery.stall_signal(entry)

    assert entry["attempts"] == 2
    assert entry["repeat_error_streak"] == 2  # numbers are normalized out of the fingerprint
    assert signal["stalled"] is True
    assert "same error" in signal["suggestion"]


def test_consecutive_distinct_failures_flag_stall():
    telemetry = {}
    for stderr in ("NameError: x", "TypeError: y", "ValueError: z"):
        entry = tutor_delivery.record_attempt(telemetry, "l1", _failing(stderr))
    signal = tutor_delivery.stall_signal(entry)
    assert signal["stalled"] is True
    assert any("3 failed attempts" in reason for reason in signal["reasons"])
    assert "Shrink the problem" in signal["suggestion"]


def test_pass_clears_stall_and_records_passed_at():
    telemetry = {}
    for _ in range(3):
        tutor_delivery.record_attempt(telemetry, "l1", _failing())
    entry = tutor_delivery.record_attempt(telemetry, "l1", {"passed": True})
    assert entry["passed_at"]
    assert tutor_delivery.stall_signal(entry)["stalled"] is False


def test_idle_time_without_progress_flags_stall():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    telemetry = {}
    entry = tutor_delivery.record_attempt(telemetry, "l1", _failing(), now=start)
    signal = tutor_delivery.stall_signal(entry, now=start + timedelta(minutes=45))
    assert signal["stalled"] is True
    assert any("no progress" in reason for reason in signal["reasons"])


def test_telemetry_is_bounded():
    telemetry = {}
    for idx in range(10):
        tutor_delivery.record_attempt(telemetry, f"l{idx}", _failing(), max_lessons=5)
    assert len(telemetry) == 5
    assert "l9" in telemetry and "l0" not in telemetry


# --- gate -----------------------------------------------------------------------

def test_gate_blocks_unpassed_exercise_and_allows_override():
    gate = tutor_delivery.comprehension_gate(lesson_id="l1", exercise=CODE_EXERCISE)
    assert gate["allowed"] is False
    assert gate["reason"] == "not_attempted"

    override = tutor_delivery.comprehension_gate(lesson_id="l1", exercise=CODE_EXERCISE, override=True)
    assert override["allowed"] is True and override["overridden"] is True


def test_gate_allows_passed_or_ungraded_lessons():
    assert tutor_delivery.comprehension_gate(lesson_id="l1", exercise={})["allowed"] is True
    assert tutor_delivery.comprehension_gate(
        lesson_id="l1", exercise=CODE_EXERCISE, history_submission={"passed": True}
    )["allowed"] is True
    assert tutor_delivery.comprehension_gate(
        lesson_id="l1", exercise=CODE_EXERCISE, telemetry_entry={"attempts": 1, "passed_at": "2025-01-01T00:00:00+00:00"}
    )["allowed"] is True


# --- retrieval hygiene ----------------------------------------------------------

def test_clean_chunks_dedupes_and_labels_sources():
    chunks = [
        {"lesson_id": "l1", "chunk_index": 0, "chunk_text": "Functions let you reuse code blocks."},
        {"lesson_id": "l1", "chunk_index": 1, "chunk_text": "Functions  let you reuse code blocks."},
        {"lesson_id": "l1", "chunk_index": 2, "chunk_text": "   "},
        {"lesson_id": "l1", "chunk_index": 3, "chunk_text": "Loops repeat work until a condition changes."},
    ]
    cleaned = tutor_delivery.clean_chunks(chunks)
    assert [c["chunk_index"] for c in cleaned] == [0, 3]
    assert cleaned[0]["source_label"] == "Lesson l1 · part 1"


def test_clean_chunks_caps_total_context():
    chunks = [{"chunk_text": f"chunk number {word} " * 10} for word in ("alpha", "beta", "gamma")]
    cleaned = tutor_delivery.clean_chunks(chunks, max_total_chars=250)
    assert len(cleaned) == 1


def test_retriever_rerank_removes_duplicates():
    from mammoth_os.rag_retrieval import LessonChunkRetriever

    retriever = LessonChunkRetriever.__new__(LessonChunkRetriever)
    chunks = [
        {"chunk_index": 0, "chunk_text": "Same text here", "score": 0.9},
        {"chunk_index": 1, "chunk_text": "Same text here", "score": 0.8},
        {"chunk_index": 2, "chunk_text": "Different", "score": 0.1},
    ]
    ranked = retriever.rerank_chunks(chunks, {}, top_k=5)
    assert [c["chunk_index"] for c in ranked] == [0, 2]


# --- ATLASSession / SDK -----------------------------------------------------------

def _session_on_lesson_2():
    session = ATLASSession(user_id="u1")
    session.curriculum = CURRICULUM
    session.current_lesson = CURRICULUM["modules"][0]["lessons"][1]
    session.current_exercise = dict(CODE_EXERCISE)
    session._lesson_id = "lesson-2"
    return session


def test_session_require_mastery_raises_until_override(monkeypatch):
    session = _session_on_lesson_2()
    with pytest.raises(LessonGateError) as excinfo:
        session.next_lesson(require_mastery=True)
    assert excinfo.value.gate["reason"] == "not_attempted"

    monkeypatch.setattr(session, "_load_lesson", lambda lesson: {"lesson_id": lesson["lesson_id"]})
    assert session.next_lesson()["lesson_id"] == "lesson-3"  # legacy behaviour is unchanged


def test_session_manifest_and_telemetry_round_trip(tmp_path):
    session = _session_on_lesson_2()
    tutor_delivery.record_attempt(session.lesson_telemetry, "lesson-2", _failing())
    assert session.lesson_manifest()["prerequisites"] == ["Intro"]

    path = tmp_path / "state.json"
    session.save_state(str(path))
    assert "lesson_telemetry" in json.loads(path.read_text())
    restored = ATLASSession.load_state(str(path))
    assert restored.lesson_telemetry["lesson-2"]["attempts"] == 1
    assert restored.stall_status()["attempts"] == 1


def test_mammoth_mind_sdk_exposes_manifest_and_stall():
    from mammoth_os.sdk import MammothMind

    fab = MammothMind(session=_session_on_lesson_2())
    assert fab.lesson_manifest()["lesson_id"] == "lesson-2"
    assert fab.stall_status()["stalled"] is False


# --- HTTP API ---------------------------------------------------------------------

@pytest.fixture
def api_state(monkeypatch):
    state = {
        "topic": "python",
        "module_id": "module-1",
        "lesson_id": "lesson-2",
        "curriculum": CURRICULUM,
        "current_lesson": CURRICULUM["modules"][0]["lessons"][1],
        "current_exercise": dict(CODE_EXERCISE),
    }
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda updated: None)
    monkeypatch.setattr(api_server, "_append_lesson_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_sync_resume_packet", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "_append_audit_event", lambda *args, **kwargs: None)
    return state


def test_api_next_is_gated_until_passed_or_overridden(api_state):
    gated = asyncio.run(api_server.atlas_next({}))
    assert gated["status"] == "gated"
    assert gated["gate"]["reason"] == "not_attempted"
    assert api_state["lesson_id"] == "lesson-2"

    advanced = asyncio.run(api_server.atlas_next({"override": True}))
    assert advanced["status"] == "ok"
    assert advanced["lesson_id"] == "lesson-3"
    assert advanced["gate"]["overridden"] is True
    assert advanced["lesson_manifest"]["lesson_id"] == "lesson-3"


def test_api_next_allows_advance_after_pass(api_state):
    tutor_delivery.record_attempt(api_state.setdefault("lesson_telemetry", {}), "lesson-2", {"passed": True})
    advanced = asyncio.run(api_server.atlas_next())
    assert advanced["status"] == "ok"
    assert advanced["lesson_id"] == "lesson-3"


def test_api_status_decoration_includes_manifest_and_stall(api_state, monkeypatch):
    monkeypatch.setattr(api_server, "_load_eval_history", lambda: [])
    monkeypatch.setattr(api_server, "_build_atlas_observability", lambda state, eval_history=None: {})
    decorated = api_server._decorate_atlas_state(api_state)
    assert decorated["lesson_manifest"]["sample_data"] == ["solution(2, 3)", "solution(-1, 1)"]
    assert decorated["lesson_stall"]["stalled"] is False
