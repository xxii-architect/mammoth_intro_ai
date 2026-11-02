import asyncio
import json

import pytest

from mammoth_os.agents.market_intel_agent import MarketIntelAgent
from mammoth_os.agents.research_agent import ResearchAgent
from mammoth_os.llm_completion import Completion

# Test excerpts, not assertions about today's real product availability.
QUERY = 'Does Black Rifle Coffee Co sell large or bulk bags of "Just Black" whole-bean coffee for our household?'
EXCERPT = "Black Rifle Coffee Just Black whole-bean coffee is listed in a 12-ounce bag. Select whole-bean or ground."
SOURCE = {"title": "Just Black coffee", "snippet": EXCERPT,
          "url": "https://www.blackriflecoffee.com/products/just-black", "source": "Manufacturer",
          "source_type": "web"}


def report(**changes):
    return {
        "request_kind": "product_research",
        "market_summary": "The excerpt lists a 12-ounce whole-bean option; bulk availability is not established.",
        "findings": [{"heading": "Documented variant", "content": "The Just Black excerpt lists a 12-ounce whole-bean bag. [S1]",
                      "source_support": ["S1"], "evidence": [{"source_id": "S1", "quote": EXCERPT}]}],
        "analysis": [{"heading": "Buying tradeoff", "detail": "Compare cost per ounce and how quickly your household finishes an opened bag."}],
        "key_trends": [], "competitive_landscape": [], "demand_signals": [], "white_space": "",
        "strategic_moves": ["Check the manufacturer's size selector for Just Black and confirm whole-bean before ordering."],
        "risks": ["A ground-coffee or different-roast listing would not answer this question."],
        "knowledge_gaps": "The excerpt does not establish a larger bag, current stock, price or shipping.",
        "confidence_note": "Only the supplied excerpt was checked; live checkout availability was not verified.",
        **changes,
    }


@pytest.fixture()
def model(monkeypatch):
    calls = []

    def install(value, finish_reason="stop"):
        class Client:
            async def generate_completion(self, prompt, **kwargs):
                calls.append((prompt, kwargs))
                return Completion(value if isinstance(value, str) else json.dumps(value),
                                  finish_reason=finish_reason)
        monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Client())

    install(report())
    return calls, install


def test_product_question_answers_evidence_not_business_templates(model):
    result = MarketIntelAgent().run({"prompt": QUERY, "sources": [SOURCE]})
    assert result["status"] == "ok"
    assert "12-ounce" in result["summary"]
    assert result["key_trends"] == result["competitive_landscape"] == []
    assert result["analysis"] and result["next_actions"]
    assert result["source_coverage"]["citation_coverage"] == 1
    assert result["confidence"] is None
    assert result["quality"]["fact_verification"] == "not_performed"
    assert result["web_sources_used"] == 0  # Supplied excerpts are not live searches.
    assert "practical production" not in json.dumps(result)
    assert "Boise" not in model[0][0][0]
    assert len(model[0]) == 1


def test_live_lookup_enabled_by_default_and_reuses_retrieval_contract(model, monkeypatch):
    calls = []

    async def collect(self, query, context):
        calls.append((query, context))
        return [SOURCE], []

    monkeypatch.setattr(ResearchAgent, "_collect_sources", collect)
    result = MarketIntelAgent().run(QUERY)
    assert result["status"] == "ok"
    assert result["web_sources_used"] == 1
    assert calls[0][0] == QUERY
    assert calls[0][1].get("allow_web_lookup") is not False


def test_no_sources_does_not_spend_model_call_or_invent_filler(model):
    result = MarketIntelAgent().run({"prompt": QUERY, "allow_web_lookup": False})
    assert result["status"] == "insufficient_evidence"
    assert result["quality"]["ready"] is False
    assert result["sources"] == result["next_actions"] == result["opportunities"] == []
    assert model[0] == []


@pytest.mark.parametrize("value,finish", [
    ("[LOCAL_ADAPTER] echo", "stop"), ("{", "length"), ({}, "stop"),
    (report(strategic_moves=[]), "stop"), (report(analysis=["placeholder"]), "stop"),
    (report(market_summary="Unable to parse LLM response."), "refusal"),
])
def test_invalid_or_offline_output_is_not_success(model, value, finish):
    model[1](value, finish)
    result = MarketIntelAgent().run({"prompt": QUERY, "sources": [SOURCE]})
    assert result["status"] == "failed"
    assert result["quality"]["ready"] is False
    assert result["findings"] == []
    assert "[LOCAL_ADAPTER]" not in result["summary"]


def test_fabricated_quote_does_not_verify_bulk_size(model):
    model[1](report(findings=[{
        "heading": "Bulk bag", "content": "Just Black has a 5-pound whole-bean bag. [S1]",
        "source_support": ["S1"], "evidence": [{"source_id": "S1", "quote": "Just Black is sold in a five-pound whole-bean bag."}],
    }]))
    result = MarketIntelAgent().run({"prompt": QUERY, "sources": [SOURCE]})
    assert result["status"] == "insufficient_evidence"
    assert result["findings"] == []
    assert "5-pound" not in result["summary"]


def test_unverified_findings_are_excluded_from_visible_answer(model):
    valid = report()["findings"][0]
    invalid = {"heading": "Stock", "content": "Just Black bulk bags are in stock today. [S1]",
               "source_support": ["S1"], "evidence": []}
    model[1](report(findings=[valid, invalid]))
    result = MarketIntelAgent().run({"prompt": QUERY, "sources": [SOURCE]})
    assert result["status"] == "partial"
    assert "in stock today" not in result["summary"]
    assert result["unverified_findings"]
    assert result["source_coverage"]["citation_coverage"] == 0.5


def test_market_analysis_keeps_relevant_depth(model):
    model[1](report(
        request_kind="market_analysis",
        key_trends=[{"trend": "Package format", "signal": "The listing distinguishes whole-bean and ground. [S1]",
                     "opportunity": "Test which format the intended buyers prefer.", "urgency": "Not assessed."}],
        competitive_landscape=[{"competitor": "Ground format", "strengths": "Listed as an option. [S1]",
                                "gaps": "Does not suit a household seeking whole-bean.", "threat_level": "Not assessed."}],
    ))
    result = MarketIntelAgent().run({"prompt": QUERY, "sources": [SOURCE]})
    assert result["status"] == "ok"
    assert result["key_trends"] and result["competitive_landscape"]
    assert result["opportunities"]


def test_sync_agent_inside_event_loop_preserves_contextvars(model):
    from contextvars import ContextVar
    tenant = ContextVar("market_test_tenant", default="none")
    values = []

    class Client:
        async def generate_completion(self, *args, **kwargs):
            values.append(tenant.get())
            return Completion(json.dumps(report()))

    async def run():
        tenant.set("tenant-a")
        return MarketIntelAgent().run({"prompt": QUERY, "sources": [SOURCE]})

    from unittest.mock import patch
    with patch("mammoth_os.llm_client.get_llm_client", return_value=Client()):
        assert asyncio.run(run())["status"] == "ok"
    assert values == ["tenant-a"]
