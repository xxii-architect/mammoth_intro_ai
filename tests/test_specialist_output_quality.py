import json

import pytest

import api_server
from mammoth_os.agents.brand_voice_agent import BrandVoiceAgent
from mammoth_os.agents.community_engine_agent import CommunityEngineAgent
from mammoth_os.agents.field_ops_agent import FieldOpsAgent
from mammoth_os.llm_completion import Completion


@pytest.mark.parametrize("agent,payload", [
    (BrandVoiceAgent, {"content": "Explain preview-first onboarding.", "mode": "rewrite"}),
    (FieldOpsAgent, {"prompt": "Prioritize a warehouse stock count.", "include_weather": False}),
    (CommunityEngineAgent, {"prompt": "Run a beginner Python workshop.", "theme": "ai_learning"}),
])
@pytest.mark.parametrize("response,finish", [
    ("[LOCAL_ADAPTER] echo", "stop"),
    ("{}", "stop"),
    ("insufficient_quota", "stop"),
    ('{"output": "Draft copy.", "summary": "A concise rewrite.", "tone_notes": "Direct."}', "length"),
])
def test_unavailable_generation_never_becomes_a_canned_success(monkeypatch, agent, payload, response, finish):
    calls = []

    class Model:
        async def generate_completion(self, *args, **kwargs):
            calls.append(kwargs)
            return Completion(response, finish_reason=finish)

    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    result = agent().run(payload)
    assert result["status"] == "failed"
    assert result["quality"]["ready"] is False
    assert len(calls) == 1
    assert "insufficient_quota" not in json.dumps(result)
    assert "[LOCAL_ADAPTER]" not in json.dumps(result)


@pytest.mark.parametrize("runtime", ["market_intel", "field_ops", "brand_voice", "community_engine"])
@pytest.mark.parametrize("status,ready", [
    ("failed", False), ("insufficient_evidence", False), ("needs_context", False), ("ok", False),
])
def test_specialist_execution_contract_cannot_claim_unavailable_results(runtime, status, ready):
    output = {"status": status, "summary": "No validated result is available for this request.",
              "quality": {"ready": ready}}
    envelope = api_server._normalize_agent_output(runtime, output)
    policy = api_server._execution_policy_for_run({}, {}, runtime_agent=runtime)
    verification = api_server._verify_execution_contract(envelope, policy)
    assert verification["passed"] is False
    assert any(check["name"] == "analysis_available" for check in verification["failed_checks"])


def test_brand_voice_retains_actual_copy_and_separates_trace(monkeypatch):
    class Model:
        async def generate_completion(self, prompt, **kwargs):
            assert "home gardeners" in prompt and "No military metaphors" in prompt
            return Completion("<think>Private model text.</think>\n" + json.dumps({
                "output": "Start with one planter. Watch what grows.",
                "summary": "A short, practical gardening caption.",
                "tone_notes": "Calm, plain language.",
            }))
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    result = BrandVoiceAgent().run({
        "content": "Start a small garden.", "mode": "caption", "audience": "home gardeners",
        "tone": "calm", "constraints": ["No military metaphors"],
    })
    assert result["status"] == "ok"
    assert result["output"] == "Start with one planter. Watch what grows."
    assert result["reasoning_trace"] == "Private model text."
    assert "Private" not in result["output"]
    assert api_server._render_chat_result({"output": result}) == result["output"]


def test_community_generation_receives_the_actual_brief(monkeypatch):
    prompts = []

    class Model:
        async def generate(self, prompt, **kwargs):
            prompts.append(prompt)
            return json.dumps({
                "challenge": "Build a CSV reader and compare the parsed rows with your partner.",
                "prompt": "Share a three-row fixture and the output of your reader.",
                "social_callout": "Beginners can pair up and compare their results.",
            })
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    result = CommunityEngineAgent().run({
        "prompt": "A CSV exercise for new Python learners.", "theme": "ai_learning",
        "audience": "beginners", "constraints": ["No paid tools"], "mode": "workshop",
    })
    assert result["status"] == "ok"
    assert all(text in prompts[0] for text in ("CSV exercise", "No paid tools", "workshop", "beginners"))
    assert "CSV reader" in result["challenge"]
