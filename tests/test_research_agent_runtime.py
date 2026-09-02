import json
import urllib.error

from mammoth_os.agents.research_agent import ResearchAgent


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
    assert result["workflow_hints"]["contradiction_scan_enabled"] is True


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


def test_research_agent_surfaces_retrieval_errors_when_sources_fail(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise urllib.error.URLError("network unavailable")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    result = ResearchAgent(router=None).run({"prompt": "Research off-grid refrigeration options", "max_sources": 3})

    assert result["status"] == "ok"
    assert len(result["sources"]) == 1
    assert result["sources"][0]["source_type"] == "prompt"
    assert "missing_external_sources" in result["quality_flags"]
    assert "retrieval_errors_present" in result["quality_flags"]
    assert result["retrieval_errors"]


def test_research_agent_detects_cross_source_contradictions():
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
    assert result["contradiction_report"]["contradiction_count"] >= 1
    assert "cross_source_conflicts_detected" in result["quality_flags"]
