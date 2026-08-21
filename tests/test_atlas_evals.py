import api_server


def test_atlas_evals_reports_pass_fail_summary(monkeypatch):
    state = {
        "topic": "Python basics",
        "lesson_id": "lesson-1",
        "current_lesson": {"title": "Functions", "lesson_id": "lesson-1"},
        "current_exercise": {"prompt": "Write a function that adds two numbers."},
    }

    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_read_json", lambda *args, **kwargs: [])
    monkeypatch.setattr(api_server, "_write_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(api_server, "set_onboarding_profile", lambda *args, **kwargs: {"onboarding": {"experience_level": "intermediate"}})
    monkeypatch.setattr(api_server, "update_learner_model", lambda *args, **kwargs: {"mastery": {}, "confidence": {}})
    monkeypatch.setattr(api_server, "build_learner_context", lambda *args, **kwargs: {"recommended_difficulty": "beginner"})
    monkeypatch.setattr(api_server, "_build_submit_adaptation", lambda *args, **kwargs: {"next_step": "Try one smaller assertion"})
    monkeypatch.setattr(api_server, "_build_resume_packet", lambda *args, **kwargs: {"summary": "Resume packet built."})

    result = api_server._run_atlas_evals(state)

    assert result["status"] == "ok"
    assert result["summary"]["pass_count"] >= 2
    assert len(result["checks"]) == 3
