import api_server


def test_build_atlas_observability_summarizes_eval_plan_and_guard_metrics(monkeypatch, tmp_path):
    monkeypatch.setattr(api_server, "MAMMOTH_DIR", tmp_path)
    monkeypatch.setattr(
        api_server,
        "_load_activity_events",
        lambda: [
            {"message": "ATLAS tutor plan generated", "agent_id": "tutor_agent", "created_at": "2026-08-03T10:00:00+00:00"},
            {"message": "Eval completed", "agent_id": "tutor_agent", "created_at": "2026-08-03T10:05:00+00:00"},
        ],
    )

    sandbox_path = tmp_path / "sandbox_runs.jsonl"
    sandbox_path.write_text('{"passed": true}\n{"passed": false}\n', encoding="utf-8")

    state = {
        "learner_model": {
            "recent_outcomes": [
                {"passed": True},
                {"passed": False},
                {"passed": True},
            ]
        },
        "fab_usage_events": [
            {"guard_triggered": True},
            {"guard_triggered": False},
            {"guard_triggered": False},
        ],
        "plan_history": [
            {
                "plan_id": "plan-1",
                "objective": "Implement a lesson helper",
                "plan_status": "completed",
                "plan_profile": "coding",
                "created_at": "2026-08-03T10:02:00+00:00",
            }
        ],
    }
    eval_history = [
        {"generated_at": "2026-08-03T10:01:00+00:00", "summary": {"pass_count": 3, "fail_count": 0}, "checks": [{}, {}, {}]},
        {"generated_at": "2026-08-03T10:04:00+00:00", "summary": {"pass_count": 2, "fail_count": 1}, "checks": [{}, {}, {}]},
    ]

    observability = api_server._build_atlas_observability(state, eval_history=eval_history)

    assert observability["metrics"]["learner_pass_rate"] == 67
    assert observability["metrics"]["eval_pass_rate"] == 83
    assert observability["metrics"]["plan_runs"] == 1
    assert observability["metrics"]["fab_guard_rate"] == 33
    assert observability["metrics"]["sandbox_success_rate"] == 50
    assert observability["latest_plan"]["status"] == "completed"
    assert len(observability["recent_activity"]) == 2
