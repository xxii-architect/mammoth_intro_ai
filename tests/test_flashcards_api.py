from fastapi.testclient import TestClient

import api_server
from mammoth_os.tutor_delivery import build_lesson_flashcards


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


def test_lesson_cards_use_teaching_answers_not_objectives():
    lesson = {
        "title": "Nutrition",
        "objectives": ["Identify macronutrients"],
        "teaching_points": [
            "Identify macronutrients",
            "<think>private reasoning</think>Protein is a macronutrient used to build and repair tissue.",
            "Carbohydrates are a source of energy for the body.",
        ],
    }
    cards = build_lesson_flashcards(lesson)
    assert len(cards) == 2
    assert cards[0]["back"] == "Protein is a macronutrient used to build and repair tissue."
    assert cards[0]["front"] == "What is meant by Protein?"
    assert all("Identify" not in card["back"] and "<think>" not in card["back"] for card in cards)
    assert build_lesson_flashcards({"objectives": ["Identify macronutrients"]}) == []
    lesson["teaching_points"] = lesson["objectives"]
    lesson["content"] = "Protein is a macronutrient used to build and repair tissue."
    assert build_lesson_flashcards(lesson)[0]["back"] == lesson["content"]


def test_active_lesson_prefers_saved_answers_and_never_uses_other_decks(monkeypatch):
    state = {
        "lesson_id": "nutrition",
        "current_lesson": {"lesson_id": "nutrition", "title": "Nutrition"},
        "study_aids": [
            {"type": "flashcards", "lesson_id": "other", "data": {"cards": [{"q": "Other topic", "a": "Wrong deck"}]}},
            {"type": "flashcards", "lesson_id": "nutrition", "data": {"cards": [
                {"front": "Nutrition: What does this objective mean? (Learn protein)", "back": "Explain it in your own words."},
                {"q": "What does protein do?", "a": "Supports tissue growth and repair.", "source": {"title": "Nutrition lesson"}},
            ]}},
            {"type": "quiz", "lesson_id": "nutrition", "data": [{"question": "Explain protein without an answer"}]},
        ],
    }
    cards = api_server._flashcards_for_lesson(state, "nutrition")
    assert len(cards) == 1
    assert cards[0]["back"] == "Supports tissue growth and repair."
    assert cards[0]["source"]["title"] == "Nutrition lesson"
    assert api_server._normalize_flashcard_item("An objective, not a card") is None
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: {**state, "study_aids": state["study_aids"][:1]})
    import asyncio
    assert asyncio.run(api_server.get_flashcards())["cards"] == []
