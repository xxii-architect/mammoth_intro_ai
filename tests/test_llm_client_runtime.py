import asyncio
import json
import urllib.error

import pytest

import mammoth_os.llm_client as llm_client
import mammoth_os.ollama_adapter as ollama_adapter
from mammoth_os.llm_client import FallbackAdapter, LocalAdapter, get_llm_client
from mammoth_os.ollama_adapter import OllamaAdapter


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

def test_ollama_completion_reports_usage_and_honors_output_budget(monkeypatch):
    payloads = []

    def fake_urlopen(req, timeout=0):
        payloads.append(json.loads(req.data))
        return DummyResponse({
            "model": "hermes3:8b", "message": {"content": '{"final":"ok"}'},
            "done_reason": "length", "prompt_eval_count": 20, "eval_count": 30,
        })

    monkeypatch.setattr(ollama_adapter.urllib.request, "urlopen", fake_urlopen)
    adapter = OllamaAdapter(config={"base_url": "http://localhost:11434", "model": "hermes3:8b"})
    result = asyncio.run(adapter.generate_completion("JSON", max_tokens=4096, decision_json=True))
    assert result.finish_reason == "length"
    assert result.usage["total_tokens"] == 50
    assert payloads[0]["options"]["num_predict"] == 4096
    assert payloads[0]["format"] == "json"


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


@pytest.fixture
def cloud_settings(monkeypatch):
    monkeypatch.setattr(llm_client, "_read_local_env", lambda: {})
    monkeypatch.setattr(llm_client, "check_ollama_running", lambda *_a, **_kw: False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("MAMMOTH_CODING_LLM_ADAPTER", raising=False)
    monkeypatch.setenv("MAMMOTH_LLM_ADAPTER", "deepseek-cloud")


def test_coding_route_prefers_openai_without_changing_general_route(cloud_settings):
    coding = get_llm_client({"workload": "coding"})
    assert coding.primary_name == "openai"
    assert coding.primary.model == "gpt-4o-mini"
    assert coding.fallback.primary_name == "deepseek"
    assert coding.fallback.primary.model == "deepseek-flash"
    assert isinstance(coding.fallback.fallback, LocalAdapter)
    general = get_llm_client()
    assert general.primary_name == "deepseek"
    assert general.fallback.primary_name == "openai"


def test_deepseek_cloud_key_disambiguates_legacy_ollama_alias(cloud_settings, monkeypatch):
    monkeypatch.setenv("MAMMOTH_LLM_ADAPTER", "deepseek")
    assert get_llm_client().primary_name == "deepseek"
    monkeypatch.delenv("DEEPSEEK_API_KEY")
    assert get_llm_client().primary_name == "ollama"
    assert get_llm_client({"workload": "coding"}).primary_name == "openai"


def test_coding_preference_is_explicit_and_never_changes_general_routing(cloud_settings, monkeypatch):
    monkeypatch.setenv("MAMMOTH_CODING_LLM_ADAPTER", "deepseek")
    client = get_llm_client({"workload": "coding"})
    assert client.primary_name == "deepseek" and client.fallback.primary_name == "openai"
    monkeypatch.setenv("MAMMOTH_CODING_LLM_ADAPTER", "invalid")
    with pytest.raises(ValueError, match="must be openai or deepseek"):
        get_llm_client({"workload": "coding"})
    assert get_llm_client().primary_name == "deepseek"


@pytest.mark.parametrize("missing", ["OPENAI_API_KEY", "DEEPSEEK_API_KEY", "both"])
def test_coding_route_keeps_available_fallbacks(cloud_settings, monkeypatch, missing):
    if missing == "both":
        monkeypatch.delenv("OPENAI_API_KEY")
        monkeypatch.delenv("DEEPSEEK_API_KEY")
    else:
        monkeypatch.delenv(missing)
    client = get_llm_client({"workload": "coding"})
    if missing == "both":
        assert isinstance(client, LocalAdapter)
    else:
        assert client.primary_name == ("deepseek" if missing == "OPENAI_API_KEY" else "openai")


def test_explicit_and_offline_adapter_choices_are_not_overridden(cloud_settings, monkeypatch):
    explicit = get_llm_client({"workload": "coding", "MAMMOTH_LLM_ADAPTER": "deepseek"})
    assert explicit.primary_name == "deepseek"
    monkeypatch.setenv("MAMMOTH_LLM_ADAPTER", "local")
    assert isinstance(get_llm_client({"workload": "coding"}), LocalAdapter)


@pytest.mark.parametrize("error", ["insufficient_quota", "429", "401", "403", "network timeout"])
def test_coding_route_provider_failure_uses_deepseek_with_honest_metadata(cloud_settings, monkeypatch, error):
    class Broken(LocalAdapter):
        async def generate(self, prompt, **kwargs):
            raise RuntimeError(error)
    monkeypatch.setattr(llm_client, "_build_openai_adapter", lambda cfg: Broken())
    monkeypatch.setattr(llm_client, "_build_deepseek_adapter", lambda cfg: HealthyFallback())
    client = get_llm_client({"workload": "coding"})
    assert asyncio.run(client.generate("fixture only")) == "fallback-response"
    assert client.last_used_provider == "deepseek"
    assert client.last_fallback_used is True
    assert client.last_fallback_reason in {"quota_or_billing", "auth_or_access", "network_or_transient"}


def test_coding_route_both_cloud_failures_reach_local_without_cycles(cloud_settings, monkeypatch):
    monkeypatch.setattr(llm_client, "_build_openai_adapter", lambda cfg: BrokenProvider())
    monkeypatch.setattr(llm_client, "_build_deepseek_adapter", lambda cfg: BrokenProvider())
    client = get_llm_client({"workload": "coding"})
    assert asyncio.run(client.generate("fixture only")).startswith("[LOCAL_ADAPTER]")
    assert client.last_used_provider == "local"
    assert client.last_fallback_used is True
