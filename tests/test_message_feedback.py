"""Thumbs up/down ratings on Mammoth Mind replies (mammoth.feedback.v1)."""

import asyncio
import json

import pytest

import api_server
from mammoth_os import message_feedback as fb


# ── pure module ─────────────────────────────────────────────────────────────

def _record(user="u1", key="run:r1", direction="down", prompt="Explain X", reply="bad", **extra):
    entry = {"message": reply, "agent_id": "assistant", "adapter": "deepseek", "model": "deepseek-chat", "created_at": "t0", **extra}
    return fb.build_record(user_id=user, account_id="default", key=key, direction=direction, assistant_entry=entry, prompt=prompt, now=extra.get("now", "2025-01-01T00:00:00+00:00"))


def test_message_key_prefers_run_id():
    assert fb.message_key(run_id="abc", created_at="t") == "run:abc"
    assert fb.message_key(created_at="t") == "ts:t"
    with pytest.raises(fb.FeedbackError):
        fb.message_key()


def test_direction_and_reason_validation():
    assert fb.normalize_direction("UP") == "up"
    assert fb.normalize_direction("none") == "none"
    with pytest.raises(fb.FeedbackError):
        fb.normalize_direction("meh")
    assert fb.normalize_reason("Off topic") == "off_topic"
    with pytest.raises(fb.FeedbackError):
        fb.normalize_reason("because")


def test_reason_only_kept_on_thumbs_down():
    up = fb.build_record(user_id="u", account_id="default", key="k", direction="up", assistant_entry={}, prompt="p", reason="incorrect", comment="x")
    assert up["reason"] == "" and up["comment"] == ""


def test_excerpts_are_capped():
    record = _record(prompt="p" * 9000, reply="r" * 9000)
    assert len(record["prompt_excerpt"]) == fb.PROMPT_EXCERPT_CHARS
    assert len(record["reply_excerpt"]) == fb.REPLY_EXCERPT_CHARS


def test_upsert_keeps_one_rating_per_user_and_message():
    records = fb.upsert([], _record(direction="up"))
    records = fb.upsert(records, _record(direction="down"))
    records = fb.upsert(records, _record(user="u2", direction="up"))
    assert len(records) == 2
    assert fb.find_rating(records, user_id="u1", account_id="default", key="run:r1")["direction"] == "down"


def test_store_is_bounded():
    records = []
    for i in range(12):
        records = fb.upsert(records, _record(key=f"run:{i}"), max_records=10)
    assert len(records) == 10
    assert records[-1]["message_key"] == "run:11"


def test_remove():
    records = fb.upsert([], _record())
    records, removed = fb.remove(records, user_id="u1", account_id="default", key="run:r1")
    assert removed and records == []


def test_summary_groups_by_model_and_reason():
    records = [_record(key="a", direction="up"), _record(key="b"), {**_record(key="c"), "reason": "incorrect"}]
    summary = fb.summarize(records)
    assert summary["totals"] == {"up": 1, "down": 2, "total": 3, "approval": 0.333, "raters": 1}
    assert summary["by_model"][0]["model"] == "deepseek-chat"
    assert summary["down_reasons"] == {"incorrect": 1, "unspecified": 1}


def test_filters_combine_agent_and_inclusive_utc_dates():
    records = [
        _record(key="a", agent_id="coding_agent", now="2026-10-04T18:00:00-06:00"),
        _record(key="b", agent_id="coding_agent", now="2026-10-05T23:59:59Z"),
        _record(key="c", agent_id="coding_agent", now="2026-10-06T00:00:00Z"),
        _record(key="d", agent_id="research_agent", now="2026-10-05T12:00:00Z"),
        {**_record(key="e", agent_id="coding_agent"), "updated_at": "invalid"},
    ]
    filtered = fb.filter_records(records, agent_id="coding_agent", date_from="2026-10-05", date_to="2026-10-05")
    assert [item["message_key"] for item in filtered] == ["a", "b"]
    assert len(fb.filter_records(records)) == 5


def test_filters_use_latest_update_and_allow_one_sided_dates():
    record = {**_record(now="2026-10-01T00:00:00Z"), "updated_at": "2026-10-05T12:00:00"}
    assert fb.filter_records([record], date_from="2026-10-05") == [record]
    assert fb.filter_records([record], date_to="2026-10-04") == []
    record["updated_at"] = ""
    assert fb.filter_records([record], date_to="2026-10-01") == [record]
    assert fb.filter_records([None, {**record, "direction": "none"}]) == []


@pytest.mark.parametrize("filters", [
    {"date_from": "2026-02-30"},
    {"date_to": "20261005"},
    {"date_from": "2026-10-06", "date_to": "2026-10-05"},
])
def test_invalid_filters_raise(filters):
    with pytest.raises(fb.FeedbackError):
        fb.filter_records([], **filters)


def test_filtering_happens_before_regression_deduplication():
    records = [
        _record(key="a", agent_id="coding_agent", reply="coding"),
        _record(key="b", agent_id="research_agent", reply="research"),
    ]
    cases = fb.build_regression_cases(fb.filter_records(records, agent_id="coding_agent"))
    assert len(cases) == 1 and cases[0]["reports"] == 1
    assert cases[0]["rejected_reply"] == "coding"


def test_regression_cases_dedupe_by_prompt_and_skip_upvotes():
    records = [
        {**_record(key="a", prompt="Explain  X", reply="old"), "updated_at": "2025-01-01"},
        {**_record(key="b", prompt="explain x", reply="new"), "updated_at": "2025-02-01"},
        _record(key="c", prompt="Other", direction="up"),
        _record(key="d", prompt="Third"),
    ]
    cases = fb.build_regression_cases(records)
    assert [c["prompt"] for c in cases] == ["explain x", "Third"]
    assert cases[0]["reports"] == 2 and cases[0]["rejected_reply"] == "new"


# ── API ─────────────────────────────────────────────────────────────────────

def test_http_filters_apply_to_summary_and_cases(chat, monkeypatch):
    from fastapi.testclient import TestClient

    records = [
        _record(key="a", agent_id="coding_agent", now="2026-10-05T12:00:00Z"),
        _record(key="b", agent_id="research_agent", now="2026-10-05T12:00:00Z"),
        _record(key="c", agent_id="coding_agent", now="2026-10-04T12:00:00Z"),
    ]
    chat.write_text(json.dumps(records), encoding="utf-8")
    monkeypatch.setattr(api_server, "_AUTH_REQUIRED", False)
    with TestClient(api_server.app) as client:
        params = {"agent_id": "coding_agent", "date_from": "2026-10-05", "date_to": "2026-10-05"}
        summary = client.get("/api/message-feedback/summary", params=params)
        assert summary.status_code == 200
        assert summary.json()["totals"]["total"] == 1
        assert summary.json()["available_agents"] == ["coding_agent", "research_agent"]
        cases = client.get("/api/message-feedback/regression-cases", params=params)
        assert cases.status_code == 200
        assert cases.json()["cases"][0]["reports"] == 1
        for path in ("/api/message-feedback/summary", "/api/message-feedback/regression-cases"):
            invalid = client.get(path, params={"date_from": "wrong"})
            assert invalid.status_code == 400
            assert "YYYY-MM-DD" in invalid.json()["error"]


def test_filtered_endpoints_still_require_admin(chat, as_user):
    as_user("user-a")
    filters = {"agent_id": "coding_agent", "date_from": "2026-10-05"}
    assert asyncio.run(api_server.message_feedback_summary(**filters)).status_code == 403
    assert asyncio.run(api_server.message_feedback_regression_cases(**filters)).status_code == 403


@pytest.fixture()
def chat(monkeypatch, tmp_path):
    feedback_file = tmp_path / "message_feedback.json"
    feedback_file.write_text("[]", encoding="utf-8")
    state = {"mammoth_chat_history": [
        {"role": "user", "message": "A's question", "created_at": "t1", "user_id": "user-a", "account_id": "default"},
        {"role": "assistant", "message": "A's answer", "created_at": "t2", "adapter": "deepseek", "model": "m", "user_id": "user-a", "account_id": "default"},
        {"role": "user", "message": "B's secret question", "created_at": "t3", "user_id": "user-b", "account_id": "default"},
        {"role": "assistant", "message": "B's secret answer", "created_at": "t4", "run_id": "run-b", "user_id": "user-b", "account_id": "default"},
    ]}
    monkeypatch.setattr(api_server, "MESSAGE_FEEDBACK_FILE", feedback_file)
    monkeypatch.setattr(api_server, "_load_atlas_state", lambda: state)
    monkeypatch.setattr(api_server, "_active_account_id", lambda payload: "default")
    monkeypatch.setattr(api_server, "_load_thread_messages", lambda user_id, thread_id: [])
    return feedback_file


@pytest.fixture()
def as_user(monkeypatch):
    tokens = []

    def _set(user_id, is_admin=False):
        monkeypatch.setattr(api_server, "_AUTH_REQUIRED", True)
        tokens.append((api_server._REQUEST_USER_ID, api_server._REQUEST_USER_ID.set(user_id)))
        tokens.append((api_server._REQUEST_IS_ADMIN, api_server._REQUEST_IS_ADMIN.set(is_admin)))

    yield _set
    for var, token in reversed(tokens):
        var.reset(token)


def _rate(**body):
    return asyncio.run(api_server.rate_chat_message(body))


def test_anonymous_cannot_rate_or_list(chat, as_user):
    as_user("anonymous")
    assert _rate(created_at="t2", direction="up").status_code == 401
    assert asyncio.run(api_server.list_message_feedback()).status_code == 401


def test_rating_uses_server_side_excerpts(chat, as_user):
    as_user("user-a")
    result = _rate(created_at="t2", direction="down", reason="incorrect", comment="wrong year", prompt="spoofed")
    assert result["rating"]["direction"] == "down"
    stored = json.loads(chat.read_text(encoding="utf-8"))
    assert stored[0]["prompt_excerpt"] == "A's question"
    assert stored[0]["reply_excerpt"] == "A's answer"
    assert stored[0]["provider"] == "deepseek"
    listed = asyncio.run(api_server.list_message_feedback())["ratings"]
    assert listed == [{"message_key": "ts:t2", "direction": "down", "reason": "incorrect", "comment": "wrong year", "thread_id": "", "updated_at": stored[0]["updated_at"]}]


def test_cannot_rate_another_users_message(chat, as_user):
    as_user("user-a")
    response = _rate(run_id="run-b", direction="down")
    assert response.status_code == 404
    assert json.loads(chat.read_text(encoding="utf-8")) == []


def test_rerating_replaces_and_none_removes(chat, as_user):
    as_user("user-a")
    _rate(created_at="t2", direction="up")
    _rate(created_at="t2", direction="down")
    assert [r["direction"] for r in json.loads(chat.read_text(encoding="utf-8"))] == ["down"]
    _rate(created_at="t2", direction="none")
    assert json.loads(chat.read_text(encoding="utf-8")) == []


def test_invalid_input_is_400(chat, as_user):
    as_user("user-a")
    assert _rate(created_at="t2", direction="sideways").status_code == 400
    assert _rate(direction="up").status_code == 400


def test_ratings_list_is_scoped_to_requester(chat, as_user):
    as_user("user-a")
    _rate(created_at="t2", direction="up")
    as_user("user-b")
    _rate(run_id="run-b", direction="down")
    assert [r["message_key"] for r in asyncio.run(api_server.list_message_feedback())["ratings"]] == ["run:run-b"]


def test_summary_and_cases_are_admin_only(chat, as_user):
    as_user("user-a")
    _rate(created_at="t2", direction="down")
    assert asyncio.run(api_server.message_feedback_summary()).status_code == 403
    assert asyncio.run(api_server.message_feedback_regression_cases()).status_code == 403
    as_user("owner", is_admin=True)
    assert asyncio.run(api_server.message_feedback_summary())["totals"]["down"] == 1
    cases = asyncio.run(api_server.message_feedback_regression_cases())["cases"]
    assert cases[0]["prompt"] == "A's question"


def test_account_export_includes_own_ratings_and_only_own_deletion_requests(chat, as_user, monkeypatch):
    as_user("user-a")
    _rate(created_at="t2", direction="up")
    as_user("user-b")
    _rate(run_id="run-b", direction="down")

    async def _user(request):
        return {"id": "user-a", "email": "a@example.com"}

    monkeypatch.setattr(api_server, "_require_auth_user", _user)
    monkeypatch.setattr(api_server, "_load_json_file", lambda path: [])
    monkeypatch.setattr(api_server, "_load_notifications", lambda: [])
    monkeypatch.setattr(api_server, "_append_audit_event", lambda **kwargs: None)
    monkeypatch.setattr(api_server, "_load_deletion_requests", lambda: [
        {"user_id": "user-a", "status": "pending"},
        {"user_id": "user-b", "status": "pending"},
    ])
    response = asyncio.run(api_server.export_account_data(None))
    export = json.loads(response.body)
    assert [r["message_key"] for r in export["message_feedback"]] == ["ts:t2"]
    assert [r["user_id"] for r in export["deletion_requests"]] == ["user-a"]
