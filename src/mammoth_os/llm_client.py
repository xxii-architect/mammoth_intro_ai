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


def _is_ollama_model_hint(model_name: str) -> bool:
    """Return True when a model string clearly refers to a local Ollama model."""
    name = (model_name or "").strip().lower()
    if not name:
        return False
    if name in MODEL_ALIASES or name in MODEL_ALIASES.values():
        return True
    # Most Ollama tags include a ":" version suffix (e.g., hermes3:8b).
    return ":" in name


def get_llm_client(config: Dict[str, Any] | None = None):
    """Return the best available LLM client.

    Selection priority (first match wins):
      1. MAMMOTH_LLM_ADAPTER=local             → LocalAdapter (testing)
      2. MAMMOTH_LLM_ADAPTER=ollama|hermes|    → OllamaAdapter (local models)
         deepseek|codellama|llama|…
      3. MAMMOTH_LLM_ADAPTER=openai            → OpenAIAdapter
      4. OPENAI_API_KEY is set                 → OpenAIAdapter
      5. Ollama is running locally             → OllamaAdapter (auto-detect)
      6. fallback                              → LocalAdapter

    Override the Ollama model via OLLAMA_MODEL env var or config["model"].
    """
    cfg = config or {}
    adapter_name = (cfg.get("adapter") or os.environ.get("MAMMOTH_LLM_ADAPTER", "")).lower().strip()

    # 1. Explicit local/test adapter
    if adapter_name == "local":
        return LocalAdapter(config=cfg)

    # 2. Explicit Ollama / named-model adapter
    if adapter_name in _OLLAMA_ADAPTER_NAMES:
        # If a known model alias was used as adapter name, pass it as the model
        if adapter_name in MODEL_ALIASES or adapter_name not in {"ollama", "local-ollama"}:
            cfg = {**cfg, "model": adapter_name}
        return OllamaAdapter(config=cfg)

    # 2b. Model hint implies Ollama (even when OPENAI_API_KEY is present).
    requested_model = str(cfg.get("model", "")).strip()
    if _is_ollama_model_hint(requested_model):
        return OllamaAdapter(config=cfg)

    # 3. Explicit OpenAI
    if adapter_name == "openai":
        try:
            return OpenAIAdapter(config=cfg)
        except Exception:
            pass

    # 4. OpenAI key present → use OpenAI
    if os.environ.get("OPENAI_API_KEY", "").strip():
        try:
            return OpenAIAdapter(config=cfg)
        except Exception:
            pass

    # 5. Auto-detect Ollama
    ollama_url = cfg.get("base_url") or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    if check_ollama_running(ollama_url):
        return OllamaAdapter(config=cfg)

    # 6. Nothing available — use deterministic local adapter
    return LocalAdapter(config=cfg)
