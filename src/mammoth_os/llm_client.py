import asyncio
import os
from typing import Any, List, Dict
from .openai_adapter import OpenAIAdapter
from .ollama_adapter import OllamaAdapter, MODEL_ALIASES, check_ollama_running


class LLMClient:
    async def generate(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError()

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        raise NotImplementedError()


from .llm_parsing import extract_code_and_files


def extract_code_from_text(text: str) -> str:
    parsed = extract_code_and_files(text)
    if "code" in parsed and parsed.get("code"):
        return parsed.get("code")
    if "files" in parsed and isinstance(parsed.get("files"), dict):
        return "\n\n".join([f"# FILE: {n}\n{c}" for n, c in parsed["files"].items()])
    return ""


class LocalAdapter(LLMClient):
    """Deterministic in-memory adapter used for CI / offline testing.

    generate() echoes the prompt. embed() returns a trivial numeric vector.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    async def generate(self, prompt: str, **kwargs) -> str:
        return f"[LOCAL_ADAPTER] {prompt}"

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        out = []
        for t in texts:
            s = sum(ord(c) for c in (t or ""))
            out.append([float((s % 100) / 100.0)])
        return out


# Models that route to Ollama even when named as the adapter
_OLLAMA_ADAPTER_NAMES = {
    "ollama", "local-ollama",
    *MODEL_ALIASES.keys(),         # e.g. "hermes", "deepseek", "codellama" …
}

_DEEPSEEK_ADAPTER_NAMES = {
    "deepseek",
    "deepseek-api",
    "deepseek-cloud",
    "deepseek-chat",
    "deepseek-reasoner",
    "deepseek-flash",
}


def _is_ollama_model_hint(model_name: str) -> bool:
    """Return True when a model string clearly refers to a local Ollama model."""
    name = (model_name or "").strip().lower()
    if not name:
        return False
    if name in MODEL_ALIASES or name in MODEL_ALIASES.values():
        return True
    # Most Ollama tags include a ":" version suffix (e.g., hermes3:8b).
    return ":" in name


def _is_billing_or_auth_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    indicators = (
        "insufficient_quota",
        "insufficient balance",
        "billing",
        "credit",
        "quota",
        "payment",
        "429",
        "401",
        "403",
        "invalid api key",
        "api key",
        "not enough",
        "no funds",
        "account",
    )
    return any(indicator in message for indicator in indicators)


class FallbackAdapter(LLMClient):
    """Adapter that tries a preferred client and falls back gracefully."""

    def __init__(self, primary: LLMClient, fallback: LLMClient):
        self.primary = primary
        self.fallback = fallback

    async def generate(self, prompt: str, **kwargs) -> str:
        try:
            return await self.primary.generate(prompt, **kwargs)
        except Exception as exc:
            if not _is_billing_or_auth_error(exc):
                raise
            return await self.fallback.generate(prompt, **kwargs)

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        try:
            return await self.primary.embed(texts, **kwargs)
        except Exception as exc:
            if not _is_billing_or_auth_error(exc):
                raise
            return await self.fallback.embed(texts, **kwargs)


def _build_deepseek_adapter(cfg: Dict[str, Any]) -> LLMClient | None:
    deepseek_key = (cfg.get("api_key") or os.environ.get("DEEPSEEK_API_KEY", "")).strip()
    deepseek_url = (cfg.get("base_url") or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")).strip()
    deepseek_model = cfg.get("model") or os.environ.get("DEEPSEEK_MODEL") or "deepseek-chat"
    if not deepseek_key:
        return None
    try:
        return OpenAIAdapter(config={**cfg, "api_key": deepseek_key, "base_url": deepseek_url, "model": deepseek_model})
    except Exception:
        return None


def _build_openai_adapter(cfg: Dict[str, Any]) -> LLMClient | None:
    openai_key = (cfg.get("api_key") or os.environ.get("OPENAI_API_KEY", "")).strip()
    if not openai_key:
        return None
    try:
        return OpenAIAdapter(config={**cfg, "api_key": openai_key, "model": cfg.get("model") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")})
    except Exception:
        return None


def _make_fallback_client(cfg: Dict[str, Any]) -> LLMClient:
    openai_client = _build_openai_adapter(cfg)
    if openai_client is not None:
        return openai_client
    ollama_url = cfg.get("base_url") or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    if check_ollama_running(ollama_url):
        return OllamaAdapter(config=cfg)
    return LocalAdapter(config=cfg)


def get_llm_client(config: Dict[str, Any] | None = None):
    """Return the best available LLM client.

    Selection priority (first match wins):
      1. MAMMOTH_LLM_ADAPTER=local             → LocalAdapter (testing)
      2. MAMMOTH_LLM_ADAPTER=ollama|hermes|    → OllamaAdapter (local models)
         deepseek|codellama|llama|…
      3. MAMMOTH_LLM_ADAPTER=deepseek|deepseek-api|... → DeepSeek cloud API
      4. MAMMOTH_LLM_ADAPTER=openai            → OpenAIAdapter
      5. OPENAI_API_KEY is set                 → OpenAIAdapter
      6. DEEPSEEK_API_KEY is set               → DeepSeek cloud API
      7. Ollama is running locally             → OllamaAdapter (auto-detect)
      8. fallback                              → LocalAdapter

    If a cloud provider rejects a request due to no balance / quota / auth errors,
    MammothOS gracefully falls back to the next viable provider instead of crashing.
    """
    cfg = config or {}
    adapter_name = (cfg.get("adapter") or os.environ.get("MAMMOTH_LLM_ADAPTER", "")).lower().strip()

    # 1. Explicit local/test adapter
    if adapter_name == "local":
        return LocalAdapter(config=cfg)

    # 2. Explicit Ollama / named-model adapter
    if adapter_name in _OLLAMA_ADAPTER_NAMES:
        if adapter_name in MODEL_ALIASES or adapter_name not in {"ollama", "local-ollama"}:
            cfg = {**cfg, "model": adapter_name}
        return OllamaAdapter(config=cfg)

    # 3. Explicit DeepSeek cloud adapter
    if adapter_name in _DEEPSEEK_ADAPTER_NAMES:
        deepseek_client = _build_deepseek_adapter(cfg)
        if deepseek_client is not None:
            fallback_client = _make_fallback_client(cfg)
            return FallbackAdapter(primary=deepseek_client, fallback=fallback_client)

    # 4. Model hint implies Ollama (even when cloud API keys are present).
    requested_model = str(cfg.get("model", "")).strip()
    if _is_ollama_model_hint(requested_model):
        return OllamaAdapter(config=cfg)

    # 5. Explicit OpenAI
    if adapter_name == "openai":
        openai_client = _build_openai_adapter(cfg)
        if openai_client is not None:
            return openai_client

    # 6. Preferred OpenAI path if configured
    if os.environ.get("OPENAI_API_KEY", "").strip():
        openai_client = _build_openai_adapter(cfg)
        if openai_client is not None:
            return openai_client

    # 7. DeepSeek cloud API as a provider fallback when configured.
    deepseek_client = _build_deepseek_adapter(cfg)
    if deepseek_client is not None:
        fallback_client = _make_fallback_client(cfg)
        return FallbackAdapter(primary=deepseek_client, fallback=fallback_client)

    # 8. Auto-detect Ollama
    ollama_url = cfg.get("base_url") or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    if check_ollama_running(ollama_url):
        return OllamaAdapter(config=cfg)

    # 9. Nothing available — use deterministic local adapter
    return LocalAdapter(config=cfg)
