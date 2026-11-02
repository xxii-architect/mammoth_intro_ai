import asyncio
import json

import pytest

from mammoth_os.agents.reflection_agent import ReflectionAgent


@pytest.fixture(autouse=True)
def reflection_model(monkeypatch):
    class Model:
        async def generate(self, prompt, **kwargs):
            return json.dumps({
                "prompt_question": "Does the example fail before or after error handling?",
                "insight": "A missing worked example could explain the block, but a setup failure could look similar.",
                "action": "Run one concrete example and record the first failing step.",
            })
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())


def test_reflection_agent_personalizes_from_signals():
    agent = ReflectionAgent(user_id="learner-1")

    result = agent.run(
        {
            "topic": "ATLAS lessons",
            "lesson_title": "Intro to prompt debugging",
            "difficulty": "hard",
            "progress_score": 0.38,
            "struggle_tags": ["need examples", "error handling"],
        }
    )

    assert result["status"] == "ok"
    assert result["lesson_title"] == "Intro to prompt debugging"
    assert "need_examples" in result["signals"]
    assert "error_handling" in result["signals"]
    assert "review_foundations" in result["follow_up_tags"]
    assert result["confidence"] is None
    assert "signatures" not in result
    assert "example" in result["action"].lower()
    assert result["citations"]
    assert result["references"]
    assert result["source_coverage"]["citation_coverage"] == 0.0
    assert result["source_coverage"]["external_source_count"] == 0
    assert "interpretation_not_fact_verified" in result["quality_flags"]
    assert result["insight"] in result["summary"]
    assert result["action"] in result["summary"]
    assert result["prompt"] in result["summary"]
    assert "progressing steadily" not in result["summary"]


def test_reflection_agent_surfaces_summary_and_sources():
    agent = ReflectionAgent(user_id="learner-2")

    result = agent.run(
        {
            "topic": "UI scaffolding",
            "difficulty": "medium",
            "progress_score": 0.8,
        }
    )

    assert result["status"] == "ok"
    assert result["sources"]
    assert "difficulty=medium" in result["sources"][1]["summary"]
    assert result["reflection_summary"]
    assert result["recommendations"]


def test_reflection_runs_inside_an_event_loop():
    async def call():
        return ReflectionAgent().run({"topic": "Error handling"})
    assert asyncio.run(call())["status"] == "ok"


@pytest.mark.parametrize("response", [
    "[LOCAL_ADAPTER] echo", '{"insight": "partial"}',
    '{"prompt_question": "Why?", "insight": "Consistency beats intensity.", "action": "Keep going."}',
])
def test_reflection_rejects_placeholder_or_incomplete_output(monkeypatch, response):
    class Model:
        async def generate(self, *args, **kwargs):
            return response
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    result = ReflectionAgent().run({"topic": "Deployments fail during approval"})
    assert result["status"] == "failed"
    assert result["insight"] == ""
    assert result["quality"]["ready"] is False
    assert result["confidence"] is None
    assert "Consistency beats intensity" not in result["summary"]


def test_reflection_provider_error_not_embedded_in_content(monkeypatch):
    class Model:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("insufficient_quota private provider diagnostic")
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Model())
    result = ReflectionAgent().run({"topic": "Deployment"})
    assert result["status"] == "failed"
    assert "insufficient_quota" not in result["summary"]
    assert "private provider" not in str(result)


def test_reflection_missing_situation_does_not_invent_an_insight():
    result = ReflectionAgent().run({})
    assert result["status"] == "needs_context"
    assert not result["insight"]
