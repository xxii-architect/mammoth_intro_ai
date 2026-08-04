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
