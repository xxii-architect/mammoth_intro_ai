from fastapi.testclient import TestClient

import api_server


def test_get_flashcards_returns_ui_shape_from_stored_cards(monkeypatch):
    state = {
        "lesson_id": "",
        "topic": "off-grid power",
        "study_aids": [
            {
                "id": "aid-1",
                "type": "flashcards",
                "lesson_id": "",
                "lesson_title": "off-grid power",
                "data": {
                    "cards": [
                        {"front": "What is a battery bank?", "back": "A group of batteries wired together.", "source": {"title": "Field Manual", "url": "https://example.com/manual"}},
                        {"q": "What is inverter efficiency?", "a": "How much DC converts to usable AC."},
                    ]
                },
            }
        ],
        "current_lesson": {},
        "current_exercise": {},
    }

    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {"id": "user-alpha", "email": "alpha@example.com", "is_admin": False} if token == "token-alpha" else None)

    client = TestClient(api_server.app)
    response = client.get("/api/flashcards", headers={"Authorization": "Bearer token-alpha"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert len(payload["cards"]) == 2
    assert payload["cards"][0]["q"] == "What is a battery bank?"
    assert payload["cards"][0]["a"] == "A group of batteries wired together."
    assert payload["cards"][0]["source"]["title"] == "Field Manual"


def test_create_flashcards_accepts_qa_shape_and_persists(monkeypatch):
    state = {"study_aids": [], "lesson_id": "lesson-42", "current_lesson": {"title": "Energy Basics"}}

    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_save_atlas_state", lambda payload: None)
    monkeypatch.setattr(api_server, "_resolve_supabase_user", lambda token: {"id": "user-alpha", "email": "alpha@example.com", "is_admin": False} if token == "token-alpha" else None)

    client = TestClient(api_server.app)
    response = client.post(
        "/api/flashcards",
        headers={"Authorization": "Bearer token-alpha"},
        json={
            "topic": "off-grid power",
            "cards": [
                {"q": "What is depth of discharge?", "a": "The percentage of battery capacity used."},
                {"front": "Why size for winter?", "back": "Lower solar input requires extra capacity."},
            ],
            "generated_by": "atlas",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["count"] == 2
    assert payload["cards"][0]["q"] == "What is depth of discharge?"
    assert payload["cards"][1]["a"] == "Lower solar input requires extra capacity."

    assert len(state["study_aids"]) == 1
    saved = state["study_aids"][0]
    assert saved["type"] == "flashcards"
    assert saved["lesson_id"] == "lesson-42"
    assert saved["lesson_title"] == "off-grid power"
    assert saved["data"]["topic"] == "off-grid power"
    assert len(saved["data"]["cards"]) == 2
