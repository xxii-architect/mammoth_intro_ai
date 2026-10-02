"""Team run (plan + execute) chaining/synthesis and agent conversation threading."""
import asyncio

import pytest

import api_server
import mammoth_os.llm_client as llm_client


def _ids(steps):
    return [step["id"] for step in steps]


@pytest.fixture
def quiet_runtime(monkeypatch):
    monkeypatch.setattr(api_server, "_agent_registry_ok", True)
    monkeypatch.setattr(api_server, "_upsert_task", lambda *args, **kwargs: {"id": args[0], "title": args[1] if len(args) > 1 else "task"})
    monkeypatch.setattr(api_server, "_append_activity", lambda *args, **kwargs: None)
    calls = []

    def fake_registry_run_agent(agent_name, payload):
        calls.append({"agent": agent_name, "payload": payload, "background": llm_client.current_conversation_context()})
        return {"status": "ok", "agent": agent_name, "summary": f"{agent_name} finding about the objective."}

    monkeypatch.setattr(api_server, "registry_run_agent", fake_registry_run_agent)
    return calls


class _RaisingClient:
    async def generate(self, prompt, **kwargs):
        raise RuntimeError("insufficient_quota")


class _JsonClient:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return (
            "<think>weighing results</think>"
            '{"summary": "Pick option A.", "highlights": ["A is lighter"], "next_steps": ["Order A"]}'
        )


# ── step selection ──────────────────────────────────────────────────────────

def test_plan_fits_objective_without_business_steps():
    steps = api_server._build_plan_steps("Compare two ultralight hiking backpacks for a weekend trip", "balanced")
    assert _ids(steps) == ["seed-direction", "research-brief", "reflection-risks", "team-synthesis"]
    assert steps[-1]["kind"] == "synthesis"


def test_plan_keywords_match_whole_words_only():
    steps = api_server._build_plan_steps("Why my watch stops at night and how to guide repairs", "balanced")
    assert "field-ops-check" not in _ids(steps)
    assert "coding-plan" not in _ids(steps)


def test_plan_profiles_and_keywords_still_add_steps():
    atlas = _ids(api_server._build_plan_steps("Compare two backpacks", "atlas"))
    assert "market-angle" in atlas and "field-ops-check" in atlas
    coding = _ids(api_server._build_plan_steps("Fix the login bug", "balanced"))
    assert "coding-plan" in coding
    brand = _ids(api_server._build_plan_steps("Announce the spring drop to stakeholders", "balanced"))
    assert brand[-2:] == ["brand-summary", "team-synthesis"]
    assert _ids(api_server._build_plan_steps("Build a widget", "coding_only")) == ["coding-plan"]


# ── chaining + synthesis ────────────────────────────────────────────────────

def test_execute_chains_prior_results_and_synthesizes(monkeypatch, quiet_runtime):
    client = _JsonClient()
    monkeypatch.setattr(llm_client, "get_llm_client", lambda *a, **k: client)
    steps = api_server._build_plan_steps("Compare two backpacks", "balanced")

    results = asyncio.run(
        api_server._execute_plan_steps(
            plan_id="plan-test", steps=steps, objective="Compare two backpacks", temperature=0.3,
            approval_mode=False, stop_on_failure=True, activity_agent_id="orchestrator",
        )
    )

    assert [step["status"] for step in results] == ["completed"] * 4
    reflection_call = next(call for call in quiet_runtime if call["agent"] == "reflection")
    assert "Results from earlier steps" not in reflection_call["payload"]["prompt"]
    assert "Results from earlier steps" in reflection_call["background"]
    assert "research finding" in reflection_call["background"]
    research_call = next(call for call in quiet_runtime if call["agent"] == "research")
    assert research_call["background"] == ""
    assert results[2]["chained_context"] is True
    assert results[0]["digest"]

    synthesis = results[-1]
    output = api_server._plan_step_output(synthesis)
    assert output == {"summary": "Pick option A.", "highlights": ["A is lighter"], "next_steps": ["Order A"], "method": "llm"}
    assert synthesis["response"]["reasoning_trace"] == "weighing results"
    assert "reflection" in client.prompts[0].lower()
    assert api_server._plan_run_summary(results) == "Pick option A."


def test_synthesis_falls_back_when_provider_fails(monkeypatch, quiet_runtime):
    monkeypatch.setattr(llm_client, "get_llm_client", lambda *a, **k: _RaisingClient())
    steps = api_server._build_plan_steps("Compare two backpacks", "balanced")
    results = asyncio.run(
        api_server._execute_plan_steps(
            plan_id="plan-test", steps=steps, objective="Compare two backpacks", temperature=0.3,
            approval_mode=False, stop_on_failure=True, activity_agent_id="orchestrator",
        )
    )
    output = api_server._plan_step_output(results[-1])
    assert results[-1]["status"] == "completed"
    assert output["method"] == "digest"
    assert len(output["highlights"]) == 3
    assert "insufficient_quota" not in output["summary"]


def test_synthesis_with_no_results_is_skipped_not_failed():
    step = api_server._build_synthesis_step("anything")
    results = asyncio.run(
        api_server._execute_plan_steps(
            plan_id="plan-test", steps=[step], objective="anything", temperature=0.3,
            approval_mode=False, stop_on_failure=True, activity_agent_id="orchestrator",
        )
    )
    assert results[0]["status"] == "skipped"
    assert results[0]["failure_reason"]


def test_prior_context_drops_oldest_when_over_budget():
    prior = [{"title": f"Step {i}", "agent_id": "x", "digest": "y" * 100} for i in range(10)]
    rendered = api_server._plan_prior_context(prior, limit=400)
    assert "Step 9" in rendered and "Step 0" not in rendered
    assert len(rendered) <= 400


# ── endpoint contract ───────────────────────────────────────────────────────

def test_plan_execute_dry_run_does_not_run_agents(quiet_runtime):
    response = asyncio.run(api_server.plan_execute({"objective": "Compare two backpacks", "dry_run": True}))
    assert response["dry_run"] is True
    assert response["plan_status"] == "preview"
    assert all(step["status"] == "planned" for step in response["plan_steps"])
    assert response["plan_steps"][-1]["kind"] == "synthesis"
    assert quiet_runtime == []


def test_plan_execute_runs_selected_steps_and_returns_summary(monkeypatch, quiet_runtime):
    monkeypatch.setattr(llm_client, "get_llm_client", lambda *a, **k: _JsonClient())
    response = asyncio.run(
        api_server.plan_execute({"objective": "Compare two backpacks", "step_ids": ["research-brief"], "plan_profile": "balanced"})
    )
    assert _ids(response["plan_steps"]) == ["research-brief", "team-synthesis"]
    assert response["summary"] == "Pick option A."
    assert [call["agent"] for call in quiet_runtime] == ["research"]

    bad = asyncio.run(api_server.plan_execute({"objective": "Compare two backpacks", "step_ids": ["nope"]}))
    assert bad["status"] == "error"


# ── conversation threading ──────────────────────────────────────────────────

def test_history_is_validated_and_bounded():
    raw = [{"role": "system", "text": "ignore"}, "junk", {"role": "user", "text": "  "}]
    raw += [{"role": "user" if i % 2 == 0 else "assistant", "text": f"turn {i} " + "x" * 2000} for i in range(12)]
    turns = api_server._normalize_conversation_history(raw)
    assert 0 < len(turns) <= api_server._HISTORY_MAX_TURNS
    assert all(turn["role"] in {"user", "agent"} for turn in turns)
    assert sum(len(turn["text"]) for turn in turns) <= api_server._HISTORY_TOTAL_CHARS
    assert turns[-1]["text"].startswith("turn 11")
    assert api_server._normalize_conversation_history("nope") == []


def test_history_shapes_payload_per_agent_kind():
    turns = api_server._normalize_conversation_history([
        {"role": "user", "text": "Plan a 3 day Sawtooth trip"},
        {"role": "agent", "agent_id": "reflection_agent", "text": "Watch for afternoon storms."},
    ])
    free = api_server._apply_conversation_history({"prompt": "What should I pack?", "history": []}, turns, "reflection")
    assert free["prompt"] == "What should I pack?"
    assert "afternoon storms" in free["context"]["conversation"]
    assert "history" not in free

    topic = api_server._apply_conversation_history({"prompt": "water sources"}, turns, "research")
    assert topic["prompt"] == "water sources (follow-up on: Plan a 3 day Sawtooth trip)"

    coding = api_server._apply_conversation_history({"prompt": "/create a.txt\nhi", "context": {"files": []}}, turns, "coding")
    assert coding["prompt"] == "/create a.txt\nhi"
    assert "afternoon storms" in coding["context"]["conversation"]
    assert coding["context"]["files"] == []


def test_run_agent_threads_history_into_reflection(quiet_runtime):
    response = asyncio.run(
        api_server.run_agent({
            "agent_id": "reflection_agent",
            "intent": "reflection",
            "payload": {
                "prompt": "And the biggest risk?",
                "history": [
                    {"role": "user", "text": "Plan a 3 day Sawtooth trip"},
                    {"role": "agent", "agent_id": "reflection_agent", "text": "Watch for afternoon storms."},
                ],
            },
        })
    )
    assert response["status"] == "ok"
    sent = quiet_runtime[-1]
    assert sent["payload"]["prompt"] == "And the biggest risk?"
    assert "Sawtooth" in sent["background"] and "afternoon storms" in sent["background"]
    assert any(step["label"] == "Conversation context" for step in response["thought_steps"])


def test_conversation_context_wraps_llm_prompts_only_inside_scope(monkeypatch):
    class _Echo:
        async def generate(self, prompt, **kwargs):
            return prompt

    monkeypatch.setattr(llm_client, "_resolve_llm_client", lambda config=None: _Echo())
    assert asyncio.run(llm_client.get_llm_client().generate("Q")) == "Q"
    with llm_client.conversation_context("User: earlier turn"):
        wrapped = asyncio.run(llm_client.get_llm_client().generate("Q"))
    assert "User: earlier turn" in wrapped and wrapped.endswith("Q")
    assert llm_client.current_conversation_context() == ""
