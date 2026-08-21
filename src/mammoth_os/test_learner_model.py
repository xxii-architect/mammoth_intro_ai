import json
import os
import tempfile

from mammoth_os.learner_model import build_learner_context, load_learner_model, update_learner_model


def test_update_learner_model_tracks_success_and_failure(tmp_path):
    storage_path = str(tmp_path)
    state = update_learner_model(
        "student-1",
        lesson={"title": "Python basics"},
        exercise={"title": "Return the sum"},
        result={"passed": True, "result": {"passed": True}},
        topic="Python basics",
        storage_path=storage_path,
    )
    assert state["attempts"] == 1
    assert state["streak"] == 1
    assert state["mastery"]["python-basics"] >= 0.5

    failed_state = update_learner_model(
        "student-1",
        lesson={"title": "Python basics"},
        exercise={"title": "Return the sum"},
        result={"passed": False, "result": {"passed": False, "stderr": "AssertionError"}},
        topic="Python basics",
        storage_path=storage_path,
    )
    assert failed_state["attempts"] == 2
    assert failed_state["streak"] == 0
    assert failed_state["error_patterns"]["assertion_error"] >= 1

    context = build_learner_context(failed_state)
    assert context["recommended_difficulty"] in {"beginner", "intermediate", "advanced"}
    assert context["weakest_concepts"]
    assert context["latest_mastery_delta"] is not None
    assert context["latest_confidence_delta"] is not None
    assert context["adaptive_coaching"]["hint_depth"] in {"foundational", "guided", "strategic"}
    assert context["adaptive_coaching"]["challenge_level"] in {"support", "balanced", "stretch"}


def test_load_learner_model_returns_default_shape(tmp_path):
    model = load_learner_model("student-2", storage_path=str(tmp_path))
    assert model["mastery"] == {}
    assert model["attempts"] == 0
