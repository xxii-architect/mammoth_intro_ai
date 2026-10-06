import json

import api_server


def test_build_resume_packet_handles_legacy_study_aids_and_notes(monkeypatch, tmp_path):
    notes_file = tmp_path / "notes.json"
    notes_file.write_text(json.dumps([
        {
            "id": "n1",
            "title": "Loop lesson notes",
            "body": "python loops -- remember accumulator patterns",
            "updated_at": "2026-08-03T10:00:00+00:00",
        }
    ]), encoding="utf-8")
    monkeypatch.setattr(api_server, "NOTES_FILE", notes_file)

    state = {
        "topic": "python loops",
        "lesson_id": "lesson-1",
        "current_lesson": {
            "lesson_id": "lesson-1",
            "title": "Python Loops",
            "objectives": ["Practice iteration", "Track totals"],
        },
        "current_exercise": {
            "lesson_id": "lesson-1",
            "prompt": "Write a loop that sums numbers.",
        },
        "lesson_history": [
            {
                "lesson_id": "lesson-1",
                "lesson": {"lesson_id": "lesson-1", "title": "Python Loops", "objectives": ["Practice iteration"]},
                "exercise": {"lesson_id": "lesson-1", "prompt": "Write a loop that sums numbers."},
                "resume_summary": "Legacy summary from older state shape",
                "created_at": "2026-08-03T10:00:00+00:00",
            }
        ],
        "study_aids": [
            {
                "type": "flashcards",
                "lesson_id": "lesson-1",
                "data": {"cards": [{"front": "What is a loop?", "back": "A repeated control structure."}]},
            }
        ],
    }

    packet = api_server._build_resume_packet(state, "lesson-1")

    assert packet["lesson_id"] == "lesson-1"
    assert packet["notes"][0]["title"] == "Loop lesson notes"
    assert packet["flashcards"][0]["front"] == "What is a loop?"
    assert "Legacy summary" in packet["prior_work_summary"]
    assert packet["resource_counts"]["total"] >= 2


def test_resume_packet_uses_historical_submission_for_previous_lesson(monkeypatch, tmp_path):
    notes_file = tmp_path / "notes.json"
    notes_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(api_server, "NOTES_FILE", notes_file)

    state = {
        "lesson_id": "lesson-2",
        "current_lesson": {
            "lesson_id": "lesson-2",
            "title": "Python Functions",
            "objectives": ["Return values"],
        },
        "current_exercise": {
            "lesson_id": "lesson-2",
            "prompt": "Write a function.",
        },
        "last_submission": {
            "passed": True,
            "hint": "Current lesson passed",
        },
        "lesson_history": [
            {
                "lesson_id": "lesson-1",
                "lesson": {
                    "lesson_id": "lesson-1",
                    "title": "Python Variables",
                    "objectives": ["Store values"],
                },
                "exercise": {
                    "lesson_id": "lesson-1",
                    "prompt": "Assign a variable.",
                },
                "last_submission": {
                    "passed": False,
                    "hint": "Need to keep the assigned value.",
                },
                "created_at": "2026-08-03T09:30:00+00:00",
                "updated_at": "2026-08-03T09:45:00+00:00",
            },
            {
                "lesson_id": "lesson-2",
                "lesson": {
                    "lesson_id": "lesson-2",
                    "title": "Python Functions",
                    "objectives": ["Return values"],
                },
                "exercise": {
                    "lesson_id": "lesson-2",
                    "prompt": "Write a function.",
                },
                "created_at": "2026-08-03T10:00:00+00:00",
            },
        ],
    }

    packet = api_server._build_resume_packet(state, "lesson-1")

    assert packet["lesson_title"] == "Python Variables"
    assert "still needs work" in packet["summary"].lower()
    assert "Need to keep the assigned value." in packet["summary"]
    assert "Returning to Python Variables." in packet["prior_work_summary"]


def test_lesson_notes_rebuilds_resources_without_unrelated_plan_fallback(monkeypatch, tmp_path):
    import asyncio

    notes_file = tmp_path / "notes.json"
    notes_file.write_text(json.dumps([
        {"id": "plan-4f70ef91", "title": "Python Loops plan", "body": '{"steps": ["task"]}', "type": "plan"},
        {"id": "unrelated", "title": "Bed Rock BBQ", "body": "Operational run report"},
        {"id": "learning", "title": "Python Loops", "body": "A loop repeats a block of code."},
        {"id": "foreign", "user_id": "another-user", "title": "Python Loops", "body": "Private learner notes"},
        {"id": "linked", "type": "lesson_note", "title": "My takeaway", "body": "Iteration repeats work.", "metadata": {"lesson_id": "lesson-1"}},
        {"id": "json-lesson", "type": "lesson_note", "title": "Python Loops data", "body": '{"values": [1, 2, 3]}', "metadata": {"lesson_id": "lesson-1"}},
        {"id": "legacy-plan", "title": "Python Loops", "body": '{"plan_id": "hidden-plan", "steps": []}'},
    ]), encoding="utf-8")
    monkeypatch.setattr(api_server, "NOTES_FILE", notes_file)
    monkeypatch.setattr(api_server, "_current_request_user_id", lambda: "local")
    state = {
        "lesson_id": "lesson-1", "topic": "Python Loops",
        "current_lesson": {"lesson_id": "lesson-1", "title": "Python Loops"},
        "lesson_history": [
            {"lesson_id": "plan-33e70909", "lesson": {"title": "M1911 plan"}},
            {"lesson_id": "lesson-1", "lesson": {"lesson_id": "lesson-1", "title": "Python Loops"},
             "resume_packet": {"notes": [{"id": "plan-4f70ef91", "preview": '{"steps": []}'}]}},
        ],
    }
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    result = asyncio.run(api_server.atlas_lesson_notes())
    assert len(result["lessons"]) == 1
    notes = result["lessons"][0]["resume_packet"]["notes"]
    assert {note["id"] for note in notes} == {"learning", "linked", "json-lesson"}
    assert "plan-" not in json.dumps(result)
    empty = {**state, "lesson_id": "new", "topic": "Batteries", "current_lesson": {"lesson_id": "new", "title": "Batteries"}}
    assert api_server._matching_notes_for_lesson(empty, "new") == []


def test_operational_runs_cannot_be_appended_as_lessons():
    state = {}
    api_server._append_lesson_history(state, {"lesson_id": "plan-unrelated", "title": "Plan"}, {})
    assert state["lesson_history"] == []
