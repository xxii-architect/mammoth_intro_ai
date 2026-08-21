import asyncio
import json

import api_server


def test_get_notes_normalizes_legacy_note_shape(monkeypatch, tmp_path):
    notes_file = tmp_path / "notes.json"
    notes_file.write_text(json.dumps([
        {
            "id": "legacy-note-1",
            "title": "Legacy note",
            "body": "Remember the recovery flow",
            "updated_at": "2026-08-18T08:44:46.861119+00:00",
        }
    ]), encoding="utf-8")
    monkeypatch.setattr(api_server, "NOTES_FILE", notes_file)

    notes = asyncio.run(api_server.get_notes())

    assert len(notes) == 1
    assert notes[0]["content"] == "Remember the recovery flow"
    assert notes[0]["created_at"] == "2026-08-18T08:44:46.861119+00:00"
    assert notes[0]["source"] == "personal"
    assert notes[0]["subsystem"] == "general"


def test_upsert_note_creates_frontend_safe_note_record(monkeypatch, tmp_path):
    notes_file = tmp_path / "notes.json"
    notes_file.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(api_server, "NOTES_FILE", notes_file)

    created = asyncio.run(api_server.upsert_note({
        "content": "Agent visibility follow-up",
        "source": "personal",
    }))

    assert created["title"] == "Agent visibility follow-up"
    assert created["body"] == "Agent visibility follow-up"
    assert created["content"] == "Agent visibility follow-up"
    assert created["created_at"]
    assert created["updated_at"]
    assert created["type"] == "personal_note"

    stored = json.loads(notes_file.read_text(encoding="utf-8"))
    assert stored[0]["created_at"] == created["created_at"]
    assert stored[0]["content"] == "Agent visibility follow-up"
