import asyncio
import sys
from types import SimpleNamespace

import pytest

from mammoth_os.llm_client import ContextualClient, FallbackAdapter
from mammoth_os.llm_completion import Completion, complete
from mammoth_os.openai_adapter import OpenAIAdapter
from mammoth_os.token_admission import input_allowance


def test_known_openai_counts_text_but_bounds_schema_and_protocol_envelope(monkeypatch):
    seen = []

    class Encoding:
        def encode(self, text, **kwargs):
            seen.append(text)
            return list(range(5))

    monkeypatch.setitem(sys.modules, "tiktoken", SimpleNamespace(encoding_for_model=lambda model: Encoding()))
    client = OpenAIAdapter({"model": "gpt-4o-mini"})
    schema = {"type": "object", "properties": {"SENTINEL_SCHEMA": {"type": "string"}}}
    allowance = input_allowance(client, "Unicode \u4e2d\u6587 <|endoftext|>", {
        "decision_schema": schema, "decision_json": True, "system_prompt": "SYSTEM_SENTINEL"})
    assert allowance.method == "model_tokenizer_with_byte_envelope"
    assert allowance.tokens > len("SENTINEL_SCHEMA") + 15
    assert "SYSTEM_SENTINEL" in seen
    assert any("mammoth_decision schema" in text for text in seen)
    assert allowance.overhead == 1024


@pytest.mark.parametrize("config", [
    {"model": "unrecognized"},
    {"model": "gpt-4o-mini", "base_url": "https://proxy.invalid/v1"},
    {"model": "deepseek-chat", "base_url": "https://api.deepseek.com/v1"},
])
def test_unknown_or_compatible_endpoint_uses_byte_bound_not_wrong_tokenizer(monkeypatch, config):
    def forbidden(*args):
        raise AssertionError("Wrong provider tokenizer")

    monkeypatch.setitem(sys.modules, "tiktoken", SimpleNamespace(encoding_for_model=forbidden))
    client = OpenAIAdapter(config)
    text = "Unicode \u4e2d\u6587"
    allowance = input_allowance(client, text, {"decision_json": True})
    assert allowance.method == "utf8_byte_upper_bound"
    assert allowance.tokens >= len(text.encode("utf-8"))


def test_missing_tokenizer_uses_explicit_conservative_fallback(monkeypatch):
    monkeypatch.setitem(sys.modules, "tiktoken", None)
    assert input_allowance(OpenAIAdapter({"model": "gpt-4o-mini"}), "text", {}).method == "utf8_byte_upper_bound"


@pytest.mark.parametrize("failure", [KeyError("model"), OSError("cache unavailable"), ValueError("invalid vocabulary")])
def test_unavailable_tokenizer_assets_use_the_labeled_byte_bound(monkeypatch, failure):
    def unavailable(model):
        raise failure

    monkeypatch.setitem(sys.modules, "tiktoken", SimpleNamespace(encoding_for_model=unavailable))
    allowance = input_allowance(OpenAIAdapter({"model": "gpt-4o-mini"}), "Source text.", {})
    assert allowance.method == "utf8_byte_upper_bound"
    assert allowance.tokens >= len("Source text.".encode("utf-8"))


def test_real_model_tokenizer_reduces_the_byte_reservation_without_claiming_exact_chat_usage():
    pytest.importorskip("tiktoken")
    client = OpenAIAdapter({"model": "gpt-4o-mini"})
    prompt = ("Repeated source explanation. \u4e2d\u6587\n" * 1000)
    allowance = input_allowance(client, prompt, {"max_tokens": 2048})
    assert allowance.method == "model_tokenizer_with_byte_envelope"
    assert allowance.tokens < len(prompt.encode("utf-8")) // 2
    assert allowance.overhead == 1024


def test_fallback_re_admits_every_actual_provider_attempt():
    seen = []
    calls = []

    class Provider:
        def __init__(self, model, fail=False):
            self.model, self.fail = model, fail

        async def generate_completion(self, prompt, **kwargs):
            calls.append((self.model, kwargs))
            if self.fail:
                raise RuntimeError("429")
            return Completion("Done.", finish_reason="stop", usage={"total_tokens": 15})

    chain = FallbackAdapter(Provider("primary", True), Provider("fallback"))

    def admit(allowance, requested):
        seen.append(allowance)
        return 200 if allowance.model == "primary" else 128

    result = asyncio.run(complete(chain, "Source", max_tokens=1024, _admission=admit))
    assert [item.model for item in seen] == ["primary", "fallback"]
    assert [kwargs["max_tokens"] for _, kwargs in calls] == [200, 128]
    assert all("_admission" not in kwargs for _, kwargs in calls)
    assert result.admission["model"] == "fallback"
    assert result.admission["output_limit"] == 128
    assert result.usage["total_tokens"] == 15


def test_refused_fallback_does_not_make_another_provider_call():
    calls = []

    class Provider:
        model = "first"

        async def generate_completion(self, *args, **kwargs):
            calls.append(self.model)
            raise RuntimeError("429")

    second = Provider()
    second.model = "second"
    chain = FallbackAdapter(Provider(), second)

    def admit(allowance, requested):
        if allowance.model == "second":
            raise ValueError("insufficient_call_allowance")
        return 128

    with pytest.raises(ValueError, match="insufficient_call_allowance"):
        asyncio.run(complete(chain, "source", _admission=admit))
    assert calls == ["first"]


def test_contextual_wrapper_admits_the_actual_background_expanded_prompt():
    seen = []

    class Client:
        model = "fixture"

        async def generate_completion(self, prompt, **kwargs):
            assert "LONG_BACKGROUND" in prompt
            return Completion("Done.")

    result = asyncio.run(complete(ContextualClient(Client(), "LONG_BACKGROUND" * 100), "Small prompt",
                                  max_tokens=1024, _admission=lambda allowance, requested: seen.append(allowance) or 128))
    assert len(seen) == 1
    assert seen[0].tokens > len("LONG_BACKGROUND" * 100)
    assert result.admission["output_limit"] == 128
