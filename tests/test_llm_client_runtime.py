import asyncio

from mammoth_os.llm_client import FallbackAdapter, LocalAdapter, get_llm_client


class BrokenProvider(LocalAdapter):
    async def generate(self, prompt: str, **kwargs) -> str:
        raise RuntimeError("insufficient_quota: billing blocked")


class HealthyFallback(LocalAdapter):
    async def generate(self, prompt: str, **kwargs) -> str:
        return "fallback-response"


def test_fallback_adapter_uses_next_provider_for_billing_failure():
    adapter = FallbackAdapter(BrokenProvider(), HealthyFallback())
    result = asyncio.run(adapter.generate("hello"))
    assert result == "fallback-response"


def test_get_llm_client_returns_local_when_all_cloud_providers_are_missing(monkeypatch):
    monkeypatch.delenv("MAMMOTH_LLM_ADAPTER", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    import mammoth_os.llm_client as llm_client

    monkeypatch.setattr(llm_client, "check_ollama_running", lambda *_args, **_kwargs: False)
    client = llm_client.get_llm_client()
    assert isinstance(client, LocalAdapter)
