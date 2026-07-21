import asyncio
from typing import Any, List, Dict
from .openai_adapter import OpenAIAdapter


class LLMClient:
    async def generate(self, prompt: str, **kwargs) -> str:
        raise NotImplementedError()

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        raise NotImplementedError()


def extract_code_from_text(text: str) -> str:
    import re
    if not text:
        return ""
    m = re.search(r"```(?:[\w+-]*)\n([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    # fallback: look for '```' with no language or the entire response
    return text.strip()


def get_llm_client(config: Dict[str, Any] | None = None):
    """Factory returning an LLM client. Defaults to OpenAIAdapter."""
    return OpenAIAdapter(config=config or {})
