import asyncio

from mammoth_os.agent_registry import _normalize_runtime_payload
from mammoth_os.agents.brand_voice_agent import BrandVoiceAgent
from mammoth_os.agents.coding_agent import CodingAgent
from mammoth_os.agents.plant_the_seed_agent import PlantTheSeedAgent


def test_coding_runtime_payload_keeps_structure():
    payload = {
        "prompt": "Document the command center terminal flow",
        "context": {"source": "def run(): return 'ok'"},
        "files": ["src/ui/terminal.py"],
    }
    normalized = _normalize_runtime_payload("coding", payload)
    assert isinstance(normalized, dict)
    assert normalized["prompt"] == payload["prompt"]
    assert normalized["context"]["source"] == payload["context"]["source"]


def test_coding_docs_reject_placeholder_target_without_source():
    agent = CodingAgent()
    result = asyncio.run(agent.write_docs("unknown", source=""))
    assert result["status"] == "needs_context"
    assert "source" in result["message"].lower()


def test_brand_voice_summary_has_explicit_structure():
    result = BrandVoiceAgent().run({
        "content": "We shipped an approval-safe operator workflow with clearer onboarding and source-aware agent tasks.",
        "mode": "stakeholder_summary",
        "audience": "stakeholder",
        "constraints": ["preview-first", "approval-safe"],
        "tone": "rugged",
    })
    assert result["mode"] == "stakeholder_summary"
    assert "What changed" in result["output"]
    assert "Guardrails" in result["output"]


def test_coding_run_rejects_placeholder_target_without_source():
    result = CodingAgent().run({
        "prompt": "Generate a utility for parsing names",
        "target": "unknown",
        "context": {"source": ""},
        "files": [],
    })
    assert result["status"] == "needs_context"
    assert "real target" in result["summary"].lower()


def test_field_ops_runtime_payload_keeps_structure():
    payload = {
        "topic": "navigation",
        "environment": "forest",
        "hazards": ["fog"],
        "constraints": ["buddy-system"],
    }
    normalized = _normalize_runtime_payload("field_ops", payload)
    assert isinstance(normalized, dict)
    assert normalized["environment"] == "forest"
    assert normalized["hazards"] == ["fog"]


def test_plant_seed_rejects_placeholder_targets_without_real_context():
    result = PlantTheSeedAgent().run({"topic": "unknown", "context": "placeholder"})
    assert result["status"] == "needs_context"
    assert "needs a real lesson" in result["summary"].lower()
