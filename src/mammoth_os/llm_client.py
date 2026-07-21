import asyncio
import os
from typing import Any, List, Dict
from .openai_adapter import OpenAIAdapter


class LLMClient:
    async def generate(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError()

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        raise NotImplementedError()


from .llm_parsing import extract_code_and_files


def extract_code_from_text(text: str) -> str:
    parsed = extract_code_and_files(text)
    # Prefer 'code' if available; if structured files present, return concatenated files
    if "code" in parsed and parsed.get("code"):
        return parsed.get("code")
    if "files" in parsed and isinstance(parsed.get("files"), dict):
        # Concatenate files into one string for initial consumption
        return "\n\n".join([f"# FILE: {n}\n{c}" for n, c in parsed["files"].items()])
    return ""


class LocalAdapter(LLMClient):
    """A deterministic, in-memory adapter used for local testing and CI.

    - generate(prompt) returns the prompt echoed with a marker
    - embed(texts) returns a deterministic vector (list of floats)
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        self.config = config or {}

    async def generate(self, prompt: str, **kwargs) -> str:
        # Simple deterministic echo — tests can mock this if they need specific behavior
        return f"[LOCAL_ADAPTER] {prompt}"

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        # Return a simple deterministic embedding: length-normalized character sums
        out = []
        for t in texts:
            s = sum(ord(c) for c in (t or ""))
            out.append([float((s % 100) / 100.0)])
        return out


def get_llm_client(config: Dict[str, Any] | None = None):
    """Factory returning an LLM client. Adapter selection via config or env var.

    config can be: { 'adapter': 'openai' | 'local', ... }
    Defaults to OpenAIAdapter when available, otherwise LocalAdapter.
    """
    cfg = config or {}
    adapter_name = cfg.get("adapter") or os.environ.get("MAMMOTH_LLM_ADAPTER")

    if adapter_name == "local":
        return LocalAdapter(config=cfg)

    # Default to OpenAIAdapter; fall back to LocalAdapter if import fails
    try:
        return OpenAIAdapter(config=cfg)
    except Exception:
        return LocalAdapter(config=cfg)
