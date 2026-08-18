import asyncio
import os
from pathlib import Path
from typing import Any, Dict, List

from .openai_adapter import OpenAIAdapter
from .ollama_adapter import OllamaAdapter, MODEL_ALIASES, check_ollama_running
from .llm_parsing import extract_code_and_files


class LLMClient:
    async def generate(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError()

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        raise NotImplementedError()


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


_OLLAMA_ADAPTER_NAMES = {
    "ollama", "local-ollama",
    *MODEL_ALIASES.keys(),
}

_DEEPSEEK_ADAPTER_NAMES = {
    "deepseek",
    "deepseek-api",
    "deepseek-cloud",
    "deepseek-chat",
    "deepseek-reasoner",
    "deepseek-flash",
}

_LOCAL_ENV_CACHE: Dict[str, str] | None = None


def _env_file_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _read_local_env() -> Dict[str, str]:
    global _LOCAL_ENV_CACHE
    if _LOCAL_ENV_CACHE is not None:
        return dict(_LOCAL_ENV_CACHE)
    path = _env_file_path()
    env_vars: Dict[str, str] = {}
    if path.exists():
        try:
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip().strip('"').strip("'")
        except Exception:
            env_vars = {}
    _LOCAL_ENV_CACHE = dict(env_vars)
    return env_vars


def _cfg_or_env(cfg: Dict[str, Any], key: str, default: str = "") -> str:
    value = cfg.get(key)
    if value not in (None, ""):
        return str(value).strip()
    env_value = os.environ.get(key)
    if env_value not in (None, ""):
        return str(env_value).strip()
    local_env_value = _read_local_env().get(key)
    if local_env_value not in (None, ""):
        return str(local_env_value).strip()
    return default


def extract_code_from_text(text: str) -> str:
    parsed = extract_code_and_files(text)
    if "code" in parsed and parsed.get("code"):
        return parsed.get("code")
    if "files" in parsed and isinstance(parsed.get("files"), dict):
        return "\n\n".join([f"# FILE: {name}\n{content}" for name, content in parsed["files"].items()])
    return ""


def _is_ollama_model_hint(model_name: str) -> bool:
    name = (model_name or "").strip().lower()
    if not name:
        return False
    if name in MODEL_ALIASES or name in MODEL_ALIASES.values():
        return True
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
    deepseek_key = _cfg_or_env(cfg, "DEEPSEEK_API_KEY")
    deepseek_url = _cfg_or_env(cfg, "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    deepseek_model = _cfg_or_env(cfg, "DEEPSEEK_MODEL", str(cfg.get("model") or "deepseek-chat"))
    if not deepseek_key:
        return None
    try:
        return OpenAIAdapter(config={**cfg, "api_key": deepseek_key, "base_url": deepseek_url, "model": deepseek_model})
    except Exception:
        return None


def _build_openai_adapter(cfg: Dict[str, Any]) -> LLMClient | None:
    openai_key = _cfg_or_env(cfg, "OPENAI_API_KEY")
    if not openai_key:
        return None
    try:
        return OpenAIAdapter(config={**cfg, "api_key": openai_key, "model": _cfg_or_env(cfg, "OPENAI_MODEL", str(cfg.get("model") or "gpt-4o-mini")), "base_url": _cfg_or_env(cfg, "OPENAI_BASE_URL") or None})
    except Exception:
        return None


def _make_fallback_client(cfg: Dict[str, Any]) -> LLMClient:
    openai_client = _build_openai_adapter(cfg)
    if openai_client is not None:
        return openai_client
    ollama_url = _cfg_or_env(cfg, "OLLAMA_BASE_URL", "http://localhost:11434")
    if check_ollama_running(ollama_url):
        return OllamaAdapter(config={**cfg, "base_url": ollama_url})
    return LocalAdapter(config=cfg)


def get_llm_client(config: Dict[str, Any] | None = None):
    """Return the best available LLM client.

    Reads explicit config first, then process env, then the repository .env file so
    the runtime and UI use the same provider source of truth.
    """
    cfg = config or {}
    adapter_name = _cfg_or_env(cfg, "MAMMOTH_LLM_ADAPTER").lower().strip()

    if adapter_name == "local":
        return LocalAdapter(config=cfg)

    if adapter_name in _OLLAMA_ADAPTER_NAMES:
        if adapter_name in MODEL_ALIASES or adapter_name not in {"ollama", "local-ollama"}:
            cfg = {**cfg, "model": adapter_name}
        return OllamaAdapter(config={**cfg, "base_url": _cfg_or_env(cfg, "OLLAMA_BASE_URL", "http://localhost:11434")})

    if adapter_name in _DEEPSEEK_ADAPTER_NAMES:
        deepseek_client = _build_deepseek_adapter(cfg)
        if deepseek_client is not None:
            return FallbackAdapter(primary=deepseek_client, fallback=_make_fallback_client(cfg))

    requested_model = str(cfg.get("model", "")).strip()
    if not requested_model:
        requested_model = _cfg_or_env(cfg, "OPENAI_MODEL")
    if _is_ollama_model_hint(requested_model):
        return OllamaAdapter(config={**cfg, "model": requested_model, "base_url": _cfg_or_env(cfg, "OLLAMA_BASE_URL", "http://localhost:11434")})

    if adapter_name == "openai":
        openai_client = _build_openai_adapter(cfg)
        if openai_client is not None:
            return openai_client

    openai_client = _build_openai_adapter(cfg)
    if openai_client is not None:
        return openai_client

    deepseek_client = _build_deepseek_adapter(cfg)
    if deepseek_client is not None:
        return FallbackAdapter(primary=deepseek_client, fallback=_make_fallback_client(cfg))

    ollama_url = _cfg_or_env(cfg, "OLLAMA_BASE_URL", "http://localhost:11434")
    if check_ollama_running(ollama_url):
        return OllamaAdapter(config={**cfg, "base_url": ollama_url})

    return LocalAdapter(config=cfg)
