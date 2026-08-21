import asyncio
import json
import urllib.error

from mammoth_os.llm_client import FallbackAdapter, LocalAdapter, get_llm_client
import mammoth_os.llm_client as llm_client
from mammoth_os.ollama_adapter import OllamaAdapter
import mammoth_os.ollama_adapter as ollama_adapter


class BrokenProvider(LocalAdapter):
    async def generate(self, prompt: str, **kwargs) -> str:
        raise RuntimeError("insufficient_quota: billing blocked")


class HealthyFallback(LocalAdapter):
    async def generate(self, prompt: str, **kwargs) -> str:
        return "fallback-response"


class DummyResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_fallback_adapter_uses_next_provider_for_billing_failure():
    adapter = FallbackAdapter(BrokenProvider(), HealthyFallback())
    result = asyncio.run(adapter.generate("hello"))
    assert result == "fallback-response"


def test_get_llm_client_returns_local_when_all_cloud_providers_are_missing(monkeypatch):
    monkeypatch.delenv("MAMMOTH_LLM_ADAPTER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(llm_client, "_read_local_env", lambda: {})
    monkeypatch.setattr(llm_client, "check_ollama_running", lambda *_args, **_kwargs: False)
    client = llm_client.get_llm_client()
    assert isinstance(client, LocalAdapter)


def test_get_llm_client_uses_repo_env_for_openai(monkeypatch):
    monkeypatch.delenv("MAMMOTH_LLM_ADAPTER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(
        llm_client,
        "_read_local_env",
        lambda: {
            "MAMMOTH_LLM_ADAPTER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "gpt-4o-mini",
        },
    )
    monkeypatch.setattr(llm_client, "check_ollama_running", lambda *_args, **_kwargs: False)
    client = llm_client.get_llm_client()
    assert isinstance(client, FallbackAdapter)
    assert client.primary.__class__.__name__ == "OpenAIAdapter"
    assert getattr(client.primary, "model", "") == "gpt-4o-mini"


def test_ollama_adapter_falls_back_to_generate_when_chat_404(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        if req.full_url.endswith("/api/chat"):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)
        if req.full_url.endswith("/api/generate"):
            return DummyResponse({"response": "fallback generate response"})
        raise AssertionError(req.full_url)

    monkeypatch.setattr(ollama_adapter.urllib.request, "urlopen", fake_urlopen)
    adapter = OllamaAdapter(config={"base_url": "http://localhost:11434", "model": "hermes3:8b"})
    result = asyncio.run(adapter.generate("hello"))
    assert result == "fallback generate response"
    assert calls == [
        "http://localhost:11434/api/chat",
        "http://localhost:11434/api/generate",
    ]


class TransientBrokenProvider(LocalAdapter):
    async def generate(self, prompt: str, **kwargs) -> str:
        raise RuntimeError("network timeout while contacting provider")


def test_fallback_adapter_uses_next_provider_for_network_failure():
    adapter = FallbackAdapter(TransientBrokenProvider(), HealthyFallback(), primary_name="deepseek", fallback_name="local")
    result = asyncio.run(adapter.generate("hello"))
    assert result == "fallback-response"
    assert adapter.last_fallback_used is True
    assert adapter.last_fallback_reason == "network_or_transient"
    assert adapter.last_used_provider == "local"


def test_fallback_adapter_describe_runtime_state_reports_contract_version():
    adapter = FallbackAdapter(BrokenProvider(), HealthyFallback(), primary_name="deepseek", fallback_name="local")
    state = adapter.describe_runtime_state()
    assert state["contract_version"] == "v2"
    assert state["primary_provider"] == "deepseek"
    assert state["fallback_provider"] == "local"
