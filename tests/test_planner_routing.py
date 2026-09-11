"""
test_planner_routing.py
Integration tests for /api/plan agent slug routing.
Run with: pytest tests/test_planner_routing.py -v
"""
import pytest
import requests

BASE = "http://localhost:8000"
TIMEOUT = 30
BANNED_SLUGS = {"tutor", "brand_voice", "reflection", "mammoth_guide"}
GOALS = [
    "Build a mammoth landing page with hero, features, and CTA sections",
    "Research mammoth competitors and summarize findings",
    "Write a Python script to process CSV data and output a summary report",
    "Create a social media campaign plan for a product launch",
]

def _plan(goal: str, constraints: dict = None) -> dict:
    body = {"goal": goal, "execute": False}
    if constraints:
        body["constraints"] = constraints
    resp = requests.post(f"{BASE}/api/plan", json=body, timeout=TIMEOUT)
    assert resp.status_code == 200, f"HTTP {resp.status_code} for goal={goal!r}: {resp.text[:300]}"
    return resp.json()

def test_plan_returns_planned_status():
    for goal in GOALS:
        data = _plan(goal)
        assert data.get("status") == "planned", f"Bad status {data.get('status')!r} for: {goal!r}"

def test_plan_returns_at_least_one_task():
    for goal in GOALS:
        assert len(_plan(goal).get("tasks", [])) >= 1, f"No tasks for: {goal!r}"

def test_plan_has_plan_id():
    assert _plan(GOALS[0]).get("plan_id"), "plan_id missing"

def test_no_banned_slugs_in_any_plan():
    for goal in GOALS:
        tasks = _plan(goal).get("tasks", [])
        slugs = [t.get("agent") for t in tasks]
        bad = BANNED_SLUGS & set(slugs)
        assert not bad, f"Banned slugs {bad} in plan for {goal!r}: {slugs}"

def test_all_tasks_have_agent_and_title():
    for goal in GOALS:
        for task in _plan(goal).get("tasks", []):
            assert task.get("agent"), f"Missing agent in task for {goal!r}: {task}"
            assert task.get("title"), f"Missing title in task for {goal!r}: {task}"

def test_plans_are_goal_specific():
    goal_a = "Build a mammoth landing page with hero, features, and CTA sections"
    goal_b = "Research mammoth competitors and summarize findings"
    ta = {t.get("title") for t in _plan(goal_a).get("tasks", [])}
    tb = {t.get("title") for t in _plan(goal_b).get("tasks", [])}
    assert ta != tb, f"Identical task titles for different goals.\nA: {sorted(ta)}\nB: {sorted(tb)}"

def test_plan_titles_reference_goal_content():
    goal = "Build a mammoth landing page with hero, features, and CTA sections"
    keywords = {"landing", "hero", "feature", "cta", "mammoth", "page"}
    all_titles = " ".join(t.get("title", "").lower() for t in _plan(goal).get("tasks", []))
    assert keywords & set(all_titles.split()), f"No goal keyword in titles: {all_titles}"

def test_dag_depends_on_ordering():
    for goal in GOALS:
        seen = set()
        for task in _plan(goal).get("tasks", []):
            for dep in task.get("depends_on", []):
                assert dep in seen, f"Forward/missing dep {dep!r} in task {task.get('task_id')!r} ({goal!r})"
            if task.get("task_id"):
                seen.add(task["task_id"])

def test_task_ids_are_unique():
    for goal in GOALS:
        ids = [t.get("task_id") for t in _plan(goal).get("tasks", [])]
        assert len(ids) == len(set(ids)), f"Duplicate task_ids in plan for {goal!r}: {ids}"

def test_use_curriculum_flag_does_not_error():
    resp = requests.post(f"{BASE}/api/plan",
        json={"goal": "Teach me Python basics", "execute": False,
              "constraints": {"use_curriculum": True}}, timeout=60)
    assert resp.status_code == 200
    assert resp.json().get("status") == "planned"

def test_no_tutor_without_curriculum_flag():
    resp = requests.post(f"{BASE}/api/plan",
        json={"goal": "Teach me Python basics", "execute": False}, timeout=60)
    assert resp.status_code == 200
    slugs = [t.get("agent") for t in resp.json().get("tasks", [])]
    assert "tutor" not in slugs, f"Tutor without use_curriculum: {slugs}"
