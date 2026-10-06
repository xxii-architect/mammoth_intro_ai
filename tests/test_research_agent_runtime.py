import json
import urllib.error
import re
import pytest

from mammoth_os.agents.research_agent import ResearchAgent


@pytest.fixture(autouse=True)
def excerpt_client(monkeypatch):
    class Client:
        async def generate(self, message, **kwargs):
            excerpts = re.findall(r"^\[(S\d+)\] .*?: (.+)$", message, re.M)
            return json.dumps({"title": "Research", "findings": [
                {"heading": label, "content": quote + f" [{label}]", "source_support": [label],
                 "evidence": [{"source_id": label, "quote": quote}]}
                for label, quote in excerpts
            ]})
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Client())


class _FakeResponse:
    def __init__(self, payload):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_research_agent_uses_provided_sources_without_web_lookup():
    agent = ResearchAgent(router=None)
    result = agent.run(
        {
            "prompt": "Research practical cargo bike maintenance schedule",
            "allow_web_lookup": False,
            "sources": [
                {
                    "title": "Local mechanic notes",
                    "url": "https://example.com/notes",
                    "summary": "Monthly chain cleaning and quarterly brake checks reduce failures.",
                    "publisher": "Workshop Journal",
                }
            ],
        }
    )

    assert result["status"] == "ok"
    assert result["mode"] == "source_grounded_research_v2"
    assert result["sources"][0]["source_type"] == "provided"
    assert result["source_coverage"]["source_count"] == 1
    assert result["retrieval_errors"] == []
    assert "ranked_sources" in result
    assert result["workflow_hints"]["excerpt_checks_enabled"] is True
    assert result["confidence"] is None


def test_research_agent_fetches_web_sources_when_enabled(monkeypatch):
    def _fake_urlopen(req, timeout=0):
        url = req.full_url
        if "wikipedia.org" in url:
            return _FakeResponse(
                {
                    "title": "Rainwater harvesting",
                    "extract": "Rainwater harvesting captures and stores rain for reuse.",
                    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Rainwater_harvesting"}},
                }
            )
        return _FakeResponse(
            {
                "AbstractText": "Rainwater harvesting can lower utility usage when maintained properly.",
                "AbstractURL": "https://duckduckgo.com/rainwater-harvesting",
                "Heading": "Rainwater harvesting",
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    result = ResearchAgent(router=None).run("Research rainwater harvesting best practices for small farms")

    assert result["status"] == "ok"
    assert len(result["sources"]) >= 2
    assert any(source["source_type"] == "web" for source in result["sources"])
    assert all("source_id" in citation for citation in result["citations"])
    assert all("url" in reference for reference in result["references"])
    assert result["source_coverage"]["citation_coverage"] > 0
    assert "evidence_ranked" in result["quality_flags"]
    assert "alignment_score" in result["contradiction_report"]


def test_research_agent_uses_wikipedia_search_when_exact_summary_misses(monkeypatch):
    def _fake_urlopen(req, timeout=0):
        url = req.full_url
        if "w/api.php" in url:
            return _FakeResponse(
                {
                    "query": {
                        "search": [
                            {"title": "Mammoth"},
                            {"title": "Adaptive learning"},
                        ]
                    }
                }
            )
        if "page/summary/MammothOS%20ATLAS%20tutoring%20engine" in url:
            raise urllib.error.HTTPError(url, 404, "not found", hdrs=None, fp=None)
        if "page/summary/Adaptive_learning" in url:
            return _FakeResponse(
                {
                    "title": "Adaptive learning",
                    "extract": "Adaptive learning systems personalize instruction using learner performance signals.",
                    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Adaptive_learning"}},
                }
            )
        return _FakeResponse({"AbstractText": "", "AbstractURL": "", "Heading": ""})

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    result = ResearchAgent(router=None).run({"prompt": "MammothOS ATLAS tutoring engine", "max_sources": 3})

    # A nearby Wikipedia topic is not evidence about MammothOS.
    assert result["status"] == "insufficient_evidence"


def test_research_agent_surfaces_retrieval_errors_when_sources_fail(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise urllib.error.URLError("network unavailable")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    result = ResearchAgent(router=None).run({"prompt": "Research off-grid refrigeration options", "max_sources": 3})

    assert result["status"] == "insufficient_evidence"
    assert result["sources"] == []
    assert result["findings"] == []
    assert "missing_external_sources" in result["quality_flags"]
    assert "retrieval_errors_present" in result["quality_flags"]
    assert result["retrieval_errors"]


def test_research_agent_does_not_claim_keyword_based_contradiction_detection():
    result = ResearchAgent(router=None).run(
        {
            "prompt": "Research whether the safety protocol should increase or decrease fuel usage checks.",
            "allow_web_lookup": False,
            "sources": [
                {
                    "title": "Ops note A",
                    "summary": "The latest recommendation is to increase fuel usage checks for safety.",
                    "publisher": "Ops Team",
                },
                {
                    "title": "Ops note B",
                    "summary": "The old protocol says to decrease fuel usage checks under stable conditions.",
                    "publisher": "Legacy Handbook",
                },
            ],
        }
    )

    assert result["status"] == "ok"
    assert result["contradiction_report"]["status"] == "not_assessed"
    assert "cross_source_conflicts_detected" not in result["quality_flags"]


@pytest.mark.parametrize("reference", ["this curriculum", "current lesson", "the current course", "active topic", "the active lesson"])
def test_nutrition_context_rejects_curriculum_inspection_pages(monkeypatch, reference):
    seen = []
    def retrieve(queries):
        seen.extend(queries)
        return [
            {"title": "Ofsted curriculum inspection", "snippet": "Inspection of curriculum teaching quality.", "source_type": "web"},
            {"title": "Nutrition and protein", "snippet": "Dietary protein supplies amino acids for body tissues.", "source_type": "web", "url": "https://example.com/nutrition"},
        ], []
    monkeypatch.setattr(ResearchAgent, "_retrieve_sources", lambda self, queries: retrieve(queries))
    prompt = f"Dive deeper into {reference}"
    result = ResearchAgent().run({"prompt": prompt, "context": {"lesson": {"subject": "Nutrition", "title": "Macronutrients"}}})
    assert seen[0].startswith("Nutrition")
    assert result["prompt"] == prompt
    assert len(result["sources"]) == 1
    assert "protein" in result["sources"][0]["title"]
    assert result["sources_filtered"][0]["reason"] == "off_topic"


def test_context_reference_requires_subject_without_paid_call(monkeypatch):
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: pytest.fail("Should not call a provider"))
    assert ResearchAgent().run("Research this curriculum")["status"] == "needs_context"


def test_long_form_respects_no_web_and_provided_sources(monkeypatch):
    agent = ResearchAgent()
    monkeypatch.setattr(agent, "_retrieve_sources", lambda queries: pytest.fail("No web lookup allowed"))
    result = agent.run({"prompt": "Nutrition", "intent": "research_long_form", "allow_web_lookup": False})
    assert result["status"] == "insufficient_evidence"
    sources, errors = agent._run_async(agent._collect_sources("Nutrition", {
        "allow_web_lookup": False, "sources": [{"title": "Nutrition", "summary": "Protein supplies amino acids."}],
    }))
    assert sources[0]["source_type"] == "provided"
    assert not errors


def test_fabricated_quotes_and_unknown_citations_are_excluded(monkeypatch):
    class Client:
        async def generate(self, *args, **kwargs):
            return json.dumps({"findings": [
                {"content": "Protein supplies amino acids [S1]", "source_support": ["S1"], "evidence": [{"source_id": "S1", "quote": "Protein supplies amino acids."}]},
                {"content": "Protein cures illness [S1]", "evidence": [{"source_id": "S1", "quote": "Protein cures illness permanently."}]},
                {"content": "Protein supplies amino acids [S99]", "evidence": [{"source_id": "S1", "quote": "Protein supplies amino acids."}]},
            ], "executive_summary": "Protein cures illness."})
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Client())
    result = ResearchAgent().run({"prompt": "Nutrition", "sources": [{"title": "Protein", "summary": "Protein supplies amino acids."}]})
    assert result["status"] == "partial"
    assert len(result["findings"]) == 1
    assert len(result["unverified_findings"]) == 2
    assert result["source_coverage"]["citation_coverage"] == pytest.approx(1 / 3)
    assert "cures" not in result["executive_summary"]
    assert len(result["citations"]) == 1


def test_summarize_supplied_text_never_sends_it_to_search(monkeypatch):
    monkeypatch.setattr(ResearchAgent, "_retrieve_sources", lambda *args: pytest.fail("Supplied text must not be searched"))
    result = ResearchAgent().run({"prompt": "Summarize this text", "intent": "summarize", "content": "Monthly chain cleaning and quarterly brake checks reduce failures."})
    assert result["status"] == "ok"
    assert result["sources"][0]["source_type"] == "provided"
    assert result["key_points"]


def test_provider_error_is_failed_not_embedded_in_report(monkeypatch):
    class Client:
        async def generate(self, *args, **kwargs):
            raise RuntimeError("insufficient_quota private-provider-diagnostic")
    monkeypatch.setattr("mammoth_os.llm_client.get_llm_client", lambda: Client())
    result = ResearchAgent().run({"prompt": "Nutrition", "sources": [{"title": "Protein", "summary": "Protein supplies amino acids for tissue repair."}]})
    assert result["status"] == "error"
    assert "private-provider" not in str(result)


def test_docx_keeps_traces_separate_and_labels_review_status(monkeypatch, tmp_path):
    from docx import Document
    monkeypatch.setenv("MAMMOTH_GENERATED_DOCS_DIR", str(tmp_path))
    filename = ResearchAgent()._generate_docx(
        "Nutrition", "A source-aware draft.",
        [{"heading": "Protein", "content": "Protein supplies amino acids.", "trace": "PRIVATE MODEL REASONING"}],
        "", [], "Nutrition",
    )
    text = "\n".join(paragraph.text for paragraph in Document(tmp_path / filename).paragraphs)
    assert "Draft for review" in text
    assert "PRIVATE MODEL REASONING" not in text
