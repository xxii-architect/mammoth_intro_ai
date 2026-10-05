import asyncio
import io
import json
import urllib.error

import pytest

from mammoth_os import web_search as ws
from mammoth_os.agents.research_agent import ResearchAgent
from mammoth_os.agents.search_agent import SearchAgent

BRAVE_PAYLOAD = {
    "web": {
        "results": [
            {"title": "<strong>Harvest</strong> Moon", "url": "https://example.org/harvest", "description": "The <strong>full moon</strong> nearest the equinox &amp; more.", "profile": {"name": "Example"}},
            {"title": "Bad scheme", "url": "javascript:alert(1)", "description": "should be dropped"},
            {"title": "No snippet", "url": "https://example.org/empty", "description": ""},
        ]
    }
}


class FakeTransport:
    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else BRAVE_PAYLOAD
        self.error = error
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.payload


def _client(env, transport, clock=None, sleeps=None):
    times = clock or [0.0]
    return ws.WebSearch(env=env, transport=transport, clock=lambda: times[0], sleep=(sleeps.append if sleeps is not None else (lambda s: None)))


def test_resolve_provider_prefers_explicit_then_brave():
    assert ws.resolve_provider({}) is None
    assert ws.resolve_provider({"TAVILY_API_KEY": "t"})["name"] == "tavily"
    assert ws.resolve_provider({"TAVILY_API_KEY": "t", "BRAVE_SEARCH_API_KEY": "b"})["name"] == "brave"
    both = {"TAVILY_API_KEY": "t", "BRAVE_SEARCH_API_KEY": "b", "MAMMOTH_WEB_SEARCH_PROVIDER": "tavily"}
    assert ws.resolve_provider(both)["name"] == "tavily"
    assert ws.resolve_provider({"BRAVE_SEARCH_API_KEY": "b", "MAMMOTH_WEB_SEARCH_PROVIDER": "tavily"}) is None


def test_not_configured_never_calls_upstream():
    transport = FakeTransport()
    result = _client({}, transport).search("harvest moon")
    assert result["status"] == "not_configured" and result["results"] == []
    assert transport.requests == []


def test_brave_results_are_cleaned_and_key_stays_in_header():
    transport = FakeTransport()
    result = _client({"BRAVE_SEARCH_API_KEY": "secret-key"}, transport).search("harvest moon", 5)
    assert result["status"] == "ok" and result["provider"] == "brave" and result["contract"] == ws.CONTRACT
    assert result["results"] == [{
        "title": "Harvest Moon",
        "url": "https://example.org/harvest",
        "snippet": "The full moon nearest the equinox & more.",
        "publisher": "Example",
    }]
    request = transport.requests[0]
    assert request.get_header("X-subscription-token") == "secret-key"
    assert "secret-key" not in request.full_url
    assert "secret-key" not in json.dumps(result)


def test_tavily_uses_bearer_post():
    transport = FakeTransport(payload={"results": [{"title": "T", "url": "https://t.example/a", "content": "Tavily snippet"}]})
    result = _client({"TAVILY_API_KEY": "tv-key"}, transport).search("q")
    request = transport.requests[0]
    assert request.get_method() == "POST" and request.get_header("Authorization") == "Bearer tv-key"
    assert json.loads(request.data)["query"] == "q"
    assert result["results"][0]["publisher"] == "t.example"


def test_cache_and_throttle():
    clock, sleeps = [100.0], []
    transport = FakeTransport()
    client = _client({"BRAVE_SEARCH_API_KEY": "k"}, transport, clock, sleeps)
    first = client.search("Harvest  Moon")
    second = client.search("harvest moon")
    assert first["cached"] is False and second["cached"] is True
    assert len(transport.requests) == 1
    client.search("another query")
    assert len(transport.requests) == 2 and sleeps and sleeps[0] == pytest.approx(1.0)
    clock[0] += ws.CACHE_TTL_SECONDS + 1
    client.search("harvest moon")
    assert len(transport.requests) == 3


def test_daily_limit():
    transport = FakeTransport()
    client = _client({"BRAVE_SEARCH_API_KEY": "k", "MAMMOTH_WEB_SEARCH_DAILY_LIMIT": "1"}, transport)
    assert client.search("one")["status"] == "ok"
    limited = client.search("two")
    assert limited["status"] == "error" and limited["code"] == "daily_limit"
    assert len(transport.requests) == 1


@pytest.mark.parametrize("status,code", [(429, "rate_limited"), (401, "auth_failed"), (500, "provider_error")])
def test_http_errors_are_classified_without_leaking_key(status, code):
    error = urllib.error.HTTPError("https://api.search.brave.com", status, "err", {}, io.BytesIO(b"key=secret-key"))
    result = _client({"BRAVE_SEARCH_API_KEY": "secret-key"}, FakeTransport(error=error)).search("q")
    assert result["status"] == "error" and result["code"] == code
    assert "secret-key" not in json.dumps(result)


def test_unreachable_provider():
    result = _client({"BRAVE_SEARCH_API_KEY": "k"}, FakeTransport(error=urllib.error.URLError("down"))).search("q")
    assert result["code"] == "unreachable"


class StubSearcher:
    def __init__(self, configured=True, results=None, status="ok"):
        self._configured = configured
        self.results = results if results is not None else [{"title": "API hit", "url": "https://a.example/x", "snippet": "api snippet", "publisher": "a.example"}]
        self.status = status
        self.calls = []

    def configured(self):
        return self._configured

    def search(self, query, limit=5):
        self.calls.append(query)
        if not self._configured:
            return {"status": "not_configured", "code": "not_configured", "results": []}
        return {"status": self.status, "provider": "brave", "results": self.results if self.status == "ok" else [], "code": None if self.status == "ok" else "rate_limited"}


def _patch_research(monkeypatch, searcher):
    monkeypatch.setattr(ws, "default_web_search", lambda: searcher)
    ddg_calls = []
    monkeypatch.setattr(ResearchAgent, "_fetch_wikipedia", lambda self, q: ([], None))
    monkeypatch.setattr(ResearchAgent, "_fetch_duckduckgo", lambda self, q: (ddg_calls.append(q) or [], None))
    return ddg_calls


def test_research_uses_api_once_and_skips_scraping(monkeypatch):
    searcher = StubSearcher()
    ddg_calls = _patch_research(monkeypatch, searcher)
    sources, errors = ResearchAgent.__new__(ResearchAgent)._retrieve_sources(["harvest moon history", "harvest moon", "moon"])
    assert searcher.calls == ["harvest moon history"]
    assert ddg_calls == []
    assert sources[0]["source_type"] == "web" and sources[0]["url"] == "https://a.example/x"
    assert errors == []


def test_research_falls_back_to_duckduckgo_when_api_fails(monkeypatch):
    searcher = StubSearcher(status="error")
    ddg_calls = _patch_research(monkeypatch, searcher)
    _, errors = ResearchAgent.__new__(ResearchAgent)._retrieve_sources(["a", "b"])
    assert ddg_calls == ["a", "b"]
    assert errors == ["web_search: rate_limited"]


def test_research_without_provider_keeps_existing_path(monkeypatch):
    searcher = StubSearcher(configured=False)
    ddg_calls = _patch_research(monkeypatch, searcher)
    ResearchAgent.__new__(ResearchAgent)._retrieve_sources(["a"])
    assert searcher.calls == [] and ddg_calls == ["a"]


def _no_llm(monkeypatch):
    async def summarize(self, results, query):
        return "summary"
    monkeypatch.setattr(SearchAgent, "summarize", summarize)


def test_search_agent_returns_web_results(monkeypatch):
    _no_llm(monkeypatch)
    monkeypatch.setattr(ws, "default_web_search", lambda: StubSearcher())
    result = asyncio.run(SearchAgent().run({"query": "harvest moon"}))
    assert result["status"] == "ok"
    assert result["results"][0]["url"] == "https://a.example/x" and "web" in result["sources"]
    assert "web_search_not_configured" not in result["quality_flags"]


def test_search_agent_flags_missing_provider_instead_of_fake_result(monkeypatch):
    _no_llm(monkeypatch)
    monkeypatch.setattr(ws, "default_web_search", lambda: StubSearcher(configured=False))
    result = asyncio.run(SearchAgent().run({"query": "harvest moon"}))
    assert result["results"] == []
    assert "web_search_not_configured" in result["quality_flags"]


def test_search_agent_can_skip_web(monkeypatch):
    _no_llm(monkeypatch)
    searcher = StubSearcher()
    monkeypatch.setattr(ws, "default_web_search", lambda: searcher)
    asyncio.run(SearchAgent().run({"query": "q", "allow_web": False}))
    assert searcher.calls == []


def test_agent_loop_registers_web_search_only_when_configured(monkeypatch):
    import api_server

    monkeypatch.setattr(ws, "default_web_search", lambda: StubSearcher(configured=False))
    ctx = api_server._agent_tool_context(None)[0]
    registry, _ = api_server._build_agent_tool_registry()
    assert "web_search" not in {t["name"] for t in registry.catalog(ctx)}
    monkeypatch.setattr(ws, "default_web_search", lambda: StubSearcher(configured=True))
    registry, _ = api_server._build_agent_tool_registry()
    assert "web_search" in {t["name"] for t in registry.catalog(ctx)}
