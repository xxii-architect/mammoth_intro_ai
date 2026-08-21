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
        "authentication",
        "unauthorized",
        "access denied",
    )
    return any(indicator in message for indicator in indicators)


def _is_transient_provider_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    indicators = (
        "timeout",
        "timed out",
        "connection",
        "connect",
        "unreachable",
        "refused",
        "network",
        "dns",
        "temporary",
        "service unavailable",
        "502",
        "503",
        "504",
    )
    return any(indicator in message for indicator in indicators)


def _is_fallback_eligible_error(exc: BaseException) -> bool:
    return _is_billing_or_auth_error(exc) or _is_transient_provider_error(exc)


def _classify_provider_error(exc: BaseException) -> str:
    lowered = str(exc).lower()
    if any(token in lowered for token in ("insufficient_quota", "billing", "quota", "credit", "payment", "429", "insufficient balance")):
        return "quota_or_billing"
    if any(token in lowered for token in ("401", "403", "api key", "invalid api key", "authentication", "unauthorized", "access denied")):
        return "auth_or_access"
    if _is_transient_provider_error(exc):
        return "network_or_transient"
    return "provider_error"


def _client_label(client: LLMClient) -> str:
    name = type(client).__name__.lower()
    if "openai" in name:
        return "openai"
    if "ollama" in name:
        return "ollama"
    if "local" in name:
        return "local"
    if "fallback" in name:
        used = str(getattr(client, "last_used_provider", "")).strip().lower()
        if used:
            return used
        primary = str(getattr(client, "primary_name", "")).strip().lower()
        return primary or "fallback"
    return str(getattr(client, "adapter", "provider") or "provider").strip().lower()


class FallbackAdapter(LLMClient):
    """Adapter that tries a preferred client and falls back gracefully."""

    contract_version = "v2"

    def __init__(
        self,
        primary: LLMClient,
        fallback: LLMClient,
        primary_name: str | None = None,
        fallback_name: str | None = None,
    ):
        self.primary = primary
        self.fallback = fallback
        self.primary_name = (primary_name or _client_label(primary)).strip().lower() or "primary"
        self.fallback_name = (fallback_name or _client_label(fallback)).strip().lower() or "fallback"
        self.model = str(getattr(primary, "model", getattr(fallback, "model", "unknown")))
        self.last_used_provider = self.primary_name
        self.last_fallback_used = False
        self.last_fallback_reason = ""
        self.last_error_type = ""
        self.last_error_detail = ""

    def _reset_last(self):
        self.last_fallback_used = False
        self.last_fallback_reason = ""
        self.last_error_type = ""
        self.last_error_detail = ""

    def describe_runtime_state(self) -> Dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "primary_provider": self.primary_name,
            "fallback_provider": self.fallback_name,
            "last_used_provider": self.last_used_provider,
            "last_fallback_used": self.last_fallback_used,
            "last_fallback_reason": self.last_fallback_reason,
            "last_error_type": self.last_error_type,
            "last_error_detail": self.last_error_detail,
            "model": self.model,
        }

    async def generate(self, prompt: str, **kwargs) -> str:
        self._reset_last()
        try:
            result = await self.primary.generate(prompt, **kwargs)
            self.last_used_provider = self.primary_name
            self.model = str(getattr(self.primary, "model", self.model))
            return result
        except Exception as exc:
            if not _is_fallback_eligible_error(exc):
                raise
            self.last_fallback_used = True
            self.last_fallback_reason = _classify_provider_error(exc)
            self.last_error_type = type(exc).__name__
            self.last_error_detail = str(exc)
            result = await self.fallback.generate(prompt, **kwargs)
            self.last_used_provider = self.fallback_name
            self.model = str(getattr(self.fallback, "model", self.model))
            return result

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        self._reset_last()
        try:
            result = await self.primary.embed(texts, **kwargs)
            self.last_used_provider = self.primary_name
            self.model = str(getattr(self.primary, "model", self.model))
            return result
        except Exception as exc:
            if not _is_fallback_eligible_error(exc):
                raise
            self.last_fallback_used = True
            self.last_fallback_reason = _classify_provider_error(exc)
            self.last_error_type = type(exc).__name__
            self.last_error_detail = str(exc)
            result = await self.fallback.embed(texts, **kwargs)
            self.last_used_provider = self.fallback_name
            self.model = str(getattr(self.fallback, "model", self.model))
            return result


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
        return OpenAIAdapter(
            config={
                **cfg,
                "api_key": openai_key,
                "model": _cfg_or_env(cfg, "OPENAI_MODEL", str(cfg.get("model") or "gpt-4o-mini")),
                "base_url": _cfg_or_env(cfg, "OPENAI_BASE_URL") or None,
            }
        )
    except Exception:
        return None


def _build_ollama_or_local_client(cfg: Dict[str, Any]) -> LLMClient:
    ollama_url = _cfg_or_env(cfg, "OLLAMA_BASE_URL", "http://localhost:11434")
    if check_ollama_running(ollama_url):
        try:
            return OllamaAdapter(config={**cfg, "base_url": ollama_url})
        except Exception:
            return LocalAdapter(config=cfg)
    return LocalAdapter(config=cfg)


def _build_openai_chain(cfg: Dict[str, Any]) -> LLMClient | None:
    openai_client = _build_openai_adapter(cfg)
    if openai_client is None:
        return None
    fallback_client = _build_ollama_or_local_client(cfg)
    return FallbackAdapter(
        primary=openai_client,
        fallback=fallback_client,
        primary_name="openai",
        fallback_name=_client_label(fallback_client),
    )


def _build_deepseek_chain(cfg: Dict[str, Any]) -> LLMClient | None:
    deepseek_client = _build_deepseek_adapter(cfg)
    if deepseek_client is None:
        return None
    openai_chain = _build_openai_chain(cfg)
    fallback_client: LLMClient = openai_chain if openai_chain is not None else _build_ollama_or_local_client(cfg)
    return FallbackAdapter(
        primary=deepseek_client,
        fallback=fallback_client,
        primary_name="deepseek",
        fallback_name=_client_label(fallback_client),
    )


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
        local_cfg = dict(cfg)
        if adapter_name in MODEL_ALIASES or adapter_name not in {"ollama", "local-ollama"}:
            local_cfg["model"] = adapter_name
        primary = OllamaAdapter(config={**local_cfg, "base_url": _cfg_or_env(local_cfg, "OLLAMA_BASE_URL", "http://localhost:11434")})
        return FallbackAdapter(primary=primary, fallback=LocalAdapter(config=local_cfg), primary_name="ollama", fallback_name="local")

    if adapter_name in _DEEPSEEK_ADAPTER_NAMES:
        deepseek_chain = _build_deepseek_chain(cfg)
        if deepseek_chain is not None:
            return deepseek_chain

    requested_model = str(cfg.get("model", "")).strip()
    if not requested_model:
        requested_model = _cfg_or_env(cfg, "OPENAI_MODEL")
    if _is_ollama_model_hint(requested_model):
        ollama_cfg = {**cfg, "model": requested_model, "base_url": _cfg_or_env(cfg, "OLLAMA_BASE_URL", "http://localhost:11434")}
        primary = OllamaAdapter(config=ollama_cfg)
        return FallbackAdapter(primary=primary, fallback=LocalAdapter(config=ollama_cfg), primary_name="ollama", fallback_name="local")

    if adapter_name == "openai":
        openai_chain = _build_openai_chain(cfg)
        if openai_chain is not None:
            return openai_chain

    deepseek_chain = _build_deepseek_chain(cfg)
    if deepseek_chain is not None:
        return deepseek_chain

    openai_chain = _build_openai_chain(cfg)
    if openai_chain is not None:
        return openai_chain

    return _build_ollama_or_local_client(cfg)
