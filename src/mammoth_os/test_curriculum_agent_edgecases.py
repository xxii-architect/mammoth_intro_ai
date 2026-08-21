from mammoth_os.agents.curriculum_agent import CurriculumAgent
import json


class _FakeResp:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_subject_extraction_colon():
    agent = CurriculumAgent(router=None)
    res = agent.run("Calculus: limits and continuity")
    assert res["status"] == "ok"
    assert res["curriculum"]["subject"].lower().startswith("calculus")


def test_subject_extraction_for_phrase():
    agent = CurriculumAgent(router=None)
    res = agent.run("A short course for Data Science.")
    assert res["status"] == "ok"
    assert res["curriculum"]["subject"].lower().startswith("data science")


def test_estimated_minutes_consistency():
    agent = CurriculumAgent(router=None)
    res = agent.run("Biology: cells")
    curriculum = res["curriculum"]
    total = curriculum["estimated_total_minutes"]
    sum_modules = sum(m["estimated_minutes"] for m in curriculum["modules"])
    assert total == sum_modules


def test_supabase_curriculum_preferred_when_available(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")

    modules_payload = [
        {"id": "m1", "title": "Python Foundations", "description": "python basics", "order_index": 1},
    ]
    lessons_payload = [
        {"id": "l1", "module_id": "m1", "title": "Variables", "content": "Intro", "order_index": 1},
        {"id": "l2", "module_id": "m1", "title": "Loops", "content": "for/while", "order_index": 2},
    ]

    calls = {"n": 0}

    def _fake_urlopen(req, timeout=8):
        calls["n"] += 1
        if calls["n"] == 1:
            return _FakeResp(modules_payload)
        return _FakeResp(lessons_payload)

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    agent = CurriculumAgent(router=None)
    res = agent.run("Python: starter course")
    cur = res["curriculum"]
    assert cur.get("source") == "mammoth.supabase"
    assert len(cur["modules"]) == 1
    assert cur["modules"][0]["title"] == "Python Foundations"
    assert len(cur["modules"][0]["lessons"]) == 2


def test_supabase_failure_falls_back_to_template(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")

    def _boom(*_args, **_kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("urllib.request.urlopen", _boom)

    agent = CurriculumAgent(router=None)
    res = agent.run("Chemistry: atoms")
    cur = res["curriculum"]
    # Template fallback still returns the 3x3 structure.
    assert len(cur["modules"]) == 3
    assert all(len(m["lessons"]) == 3 for m in cur["modules"])
