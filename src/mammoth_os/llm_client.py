import asyncio
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


def get_llm_client(config: Dict[str, Any] | None = None):
    """Factory returning an LLM client. Defaults to OpenAIAdapter."""
    return OpenAIAdapter(config=config or {})
