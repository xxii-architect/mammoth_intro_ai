import json

import pytest

from mammoth_os import research_quality as rq
from mammoth_os.agents.research_agent import ResearchAgent, SUMMARIZE_SYSTEM, CURRICULUM_SYSTEM


# --- reasoning stripping ----------------------------------------------------------

def test_strip_reasoning_removes_think_blocks_and_keeps_trace():
    clean, trace = rq.strip_reasoning("<think>plan the answer</think>\nThe market grew 4% in 2024.")
    assert clean == "The market grew 4% in 2024."
    assert trace == "plan the answer"


def test_strip_reasoning_handles_dangling_tags_and_alt_tag_names():
    clean, trace = rq.strip_reasoning("weighing options...</think>Final prose here.")
    assert clean == "Final prose here." and "weighing" in trace

    clean, trace = rq.strip_reasoning("Real content.\n<reasoning>cut off mid-thought")
    assert clean == "Real content." and "cut off" in trace

    clean, _ = rq.strip_reasoning("<Thinking>x</Thinking>Body.")
    assert clean == "Body."


def test_strip_reasoning_drops_meta_preamble_and_signoff_only_around_content():
    text = "Okay, let me write this section.\nHere's the section:\nAdoption accelerated in rural areas.\nLet me know if you want edits."
    clean, _ = rq.strip_reasoning(text)
    assert clean == "Adoption accelerated in rural areas."
    # a lone line is never stripped to nothing
    assert rq.strip_reasoning("Sure, this is the whole answer.")[0] == "Sure, this is the whole answer."


def test_strip_echoed_heading():
    assert rq.strip_echoed_heading("## Market Size\nBody text.", "Market Size") == "Body text."
    assert rq.strip_echoed_heading("Body text.", "Market Size") == "Body text."


def test_clean_string_fields_is_recursive_and_leaves_clean_text_alone():
    payload = {"a": "<think>x</think>Answer", "b": [{"c": "fine"}], "n": 3}
    assert rq.clean_string_fields(payload) == {"a": "Answer", "b": [{"c": "fine"}], "n": 3}


# --- completeness -------------------------------------------------------------------

def test_trim_to_last_sentence():
    text, trimmed = rq.trim_to_last_sentence("First sentence. Second sentence is complete. Third is cut of")
    assert trimmed is True and text.endswith("complete.")
    assert rq.trim_to_last_sentence("All good.") == ("All good.", False)
    # refuses to throw away most of the text
    assert rq.trim_to_last_sentence("Short. " + "x" * 200)[1] is False


# --- relevance + disambiguation ---------------------------------------------------

def test_filter_relevant_sources_drops_off_topic_and_disambiguation_pages():
    sources = [
        {"title": "Mercury (disambiguation)", "snippet": "Mercury may refer to: a planet, an element", "relevance_score": 0.5},
        {"title": "Retail trends", "snippet": "Outdoor retail sales in Idaho grew", "relevance_score": 0.4},
        {"title": "Cooking pasta", "snippet": "Boil water and add salt", "relevance_score": 0.1},
        {"title": "Provided memo", "snippet": "anything", "source_type": "provided"},
    ]
    kept, dropped = rq.filter_relevant_sources(sources, "outdoor retail growth in Idaho")
    assert [s["title"] for s in kept] == ["Provided memo", "Retail trends"]
    assert {d["drop_reason"] for d in dropped} == {"disambiguation_page", "off_topic"}


def test_zero_overlap_sources_are_kept_as_weak_when_little_else_exists():
    sources = [
        {"title": "Mercury (disambiguation)", "snippet": "Mercury may refer to: a planet"},
        {"title": "Adaptive learning", "snippet": "Systems personalize instruction using performance signals"},
    ]
    kept, dropped = rq.filter_relevant_sources(sources, "MammothOS ATLAS tutoring engine")
    assert [s["title"] for s in kept] == ["Adaptive learning"]
    assert kept[0]["relevance"] == "weak"
    assert [d["drop_reason"] for d in dropped] == ["disambiguation_page"]


def test_entity_mismatch_demotes_but_never_drops():
    sources = [
        {"title": "Mammoth", "snippet": "The woolly mammoth is an extinct species", "relevance_score": 0.6},
        {"title": "Mammoth Mind tutor", "snippet": "Mammoth Mind is an AI tutor product", "relevance_score": 0.4},
    ]
    kept, dropped = rq.filter_relevant_sources(sources, "What does Mammoth Mind do?")
    assert not dropped
    assert kept[0]["title"] == "Mammoth Mind tutor"
    assert kept[1]["entity_match"] == "partial"


# --- dedupe -------------------------------------------------------------------------

def test_dedupe_items_and_sections():
    findings = [
        {"heading": "A", "content": "Sales of trail gear rose sharply across Idaho in 2024"},
        {"heading": "B", "content": "Across Idaho, sales of trail gear rose sharply in 2024"},
        {"heading": "C", "content": "Labor shortages constrain retail expansion"},
    ]
    assert [f["heading"] for f in rq.dedupe_items(findings)] == ["A", "C"]

    para = "Regional outdoor retailers benefit from tourism growth, stronger trail infrastructure, and rising local participation rates."
    sections = [
        {"heading": "One", "content": para + "\n\nUnique first-section analysis about supply chains and inventory risk management practices."},
        {"heading": "Two", "content": para + "\n\nDistinct second-section discussion of pricing power, margins, and competitive pressure dynamics."},
        {"heading": "Three", "content": para},
    ]
    cleaned, removed = rq.dedupe_sections(sections)
    assert removed == 1  # section Two's repeat; section Three keeps its only paragraph
    assert para not in cleaned[1]["content"]
    assert cleaned[2]["content"] == para


def test_fallback_headings_are_topic_specific_not_market_boilerplate():
    headings = rq.fallback_section_headings("Wildfire evacuation planning", 6)
    assert len(headings) == 6
    assert all("Brands" not in h for h in headings)
    assert "Wildfire evacuation planning" in headings[0]


# --- prompt contracts -----------------------------------------------------------------

def test_summarize_and_curriculum_prompts_no_longer_demand_findings():
    assert "findings[]" not in SUMMARIZE_SYSTEM
    assert "findings[]" not in CURRICULUM_SYSTEM
    assert "key_points[]" in SUMMARIZE_SYSTEM
    assert "core_concepts[]" in CURRICULUM_SYSTEM


# --- agent pipelines with a scripted LLM ----------------------------------------------

class ScriptedClient:
    def __init__(self, responder):
        self.responder = responder
        self.calls = []

    async def generate(self, message, system_prompt="", **kwargs):
        self.calls.append({"message": message, "system": system_prompt, **kwargs})
        return self.responder(message, system_prompt, len(self.calls))


@pytest.fixture
def scripted(monkeypatch):
    holder = {}

    def install(responder):
        client = ScriptedClient(responder)
        monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: client)
        holder["client"] = client
        return client

    return install


def test_research_mode_strips_leaked_reasoning_and_filters_sources(scripted):
    payload = {
        "title": "Idaho outdoor retail",
        "executive_summary": "<think>should I hedge?</think>Demand is growing.",
        "findings": [
            {"heading": "Growth", "content": "Outdoor retail sales in Idaho grew [S1]", "source_support": ["S1"]},
            {"heading": "Growth again", "content": "In Idaho, outdoor retail sales grew [S1]", "source_support": ["S1"]},
        ],
        "key_facts": ["Fact one", "Fact one"],
    }
    client = scripted(lambda msg, sys, n: "<think>planning the brief</think>\n```json\n" + json.dumps(payload) + "\n```")
    result = ResearchAgent().run({
        "prompt": "outdoor retail growth in Idaho",
        "context": {"sources": [
            {"title": "Idaho retail report", "summary": "Outdoor retail sales in Idaho grew 6%", "url": "https://example.com/a"},
        ]},
    })

    assert result["status"] == "ok"
    assert result["executive_summary"] == "Demand is growing."
    assert "planning the brief" in result["reasoning_trace"]
    assert "should I hedge?" in result["reasoning_trace"]
    assert len(result["findings"]) == 1
    assert result["key_facts"] == ["Fact one"]
    assert "reasoning_stripped" in result["quality_flags"]
    assert "{{" not in client.calls[0]["message"]


def test_summarize_mode_asks_for_key_points_not_findings(scripted):
    client = scripted(lambda msg, sys, n: json.dumps({"tldr": "Answer.", "key_points": ["a point here", "b point there"]}))
    result = ResearchAgent().run({"prompt": "summarize trail permits", "intent": "summarize", "context": {"allow_web_lookup": False}})
    assert result["tldr"] == "Answer."
    assert "key_points[]" in client.calls[0]["message"]
    assert "findings[]" not in client.calls[0]["message"]


def test_long_form_pipeline_dedupes_trims_retries_and_reports_quality(scripted, monkeypatch):
    agent = ResearchAgent()
    monkeypatch.setattr(agent, "_retrieve_sources", lambda queries: ([
        {"title": "Wildfire evacuation", "snippet": "Evacuation planning for wildfire zones", "source": "Web", "url": "https://e.com"},
        {"title": "Evacuation planning guide", "snippet": "Planning wildfire evacuation drills for counties", "source": "Web", "url": "https://g.com"},
        {"title": "Pasta", "snippet": "Boil water", "source": "Web", "url": "https://p.com"},
    ], []))
    monkeypatch.setattr(agent, "_generate_docx", lambda *args, **kwargs: None)

    repeated = "Evacuation routes must be mapped in advance, rehearsed with residents, and published through multiple channels."
    attempts = {"section_3": 0}

    def responder(msg, system, n):
        if "Conclusion brief" in msg:
            return "Here's the conclusion:\nPreparedness saves lives."
        if "outline" in msg.lower():
            return json.dumps({"title": "Wildfire evacuation", "abstract": "Abstract.", "sections": [
                {"heading": "Routes", "brief": ""}, {"heading": "Alerts", "brief": ""}, {"heading": "Shelters", "brief": ""},
            ]})
        if "Section 1:" in msg:
            return "<think>outline my points</think>Routes\n" + repeated + "\n\nRoute capacity analysis shows bottlenecks at two bridges near the county line."
        if "Section 2:" in msg:
            return repeated + "\n\nAlert systems should combine sirens, text messages, and door-to-door outreach. The last sentence is cut o"
        if "Section 3:" in msg:
            attempts["section_3"] += 1
            return "<think>only thinking, no prose" if attempts["section_3"] == 1 else "Shelters need backup power and water supplies."
        if "Section" in msg:
            raise RuntimeError("provider down")
        return "Here's the conclusion:\nPreparedness saves lives."

    scripted(responder)
    result = agent._run_async(agent._long_form_pipeline("Wildfire evacuation planning", {}))

    sections = {sec["heading"]: sec for sec in result["sections"]}
    assert len(result["sections"]) == 6
    assert "Routes\n" not in sections["Routes"]["content"]
    assert sections["Routes"]["trace"] == "outline my points"
    assert repeated not in sections["Alerts"]["content"]
    assert sections["Alerts"]["content"].endswith("outreach.")
    assert sections["Shelters"]["retried"] is True and sections["Shelters"]["status"] == "ok"
    failed = [sec for sec in result["sections"] if sec["status"] == "failed"]
    assert failed and all(sec["content"] == "" for sec in failed)
    assert all("Brands" not in sec["heading"] for sec in result["sections"])
    assert result["conclusion"] == "Preparedness saves lives."
    assert sorted(s["title"] for s in result["sources"]) == ["Evacuation planning guide", "Wildfire evacuation"]
    quality = result["quality"]
    assert quality["duplicate_paragraphs_removed"] == 1
    assert quality["sections_trimmed"] >= 1
    assert quality["sections_retried"] == 1
    assert quality["sections_failed"] == len(failed)
    assert quality["sources_filtered"] == 1


def test_relevance_uses_light_stemming():
    kept, dropped = rq.filter_relevant_sources(
        [{"title": "Learning", "snippet": "Learning is the process of acquiring knowledge"}],
        "benefits of spaced repetition for adult learners",
    )
    assert kept and not dropped
