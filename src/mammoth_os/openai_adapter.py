import os
import asyncio
from typing import Any, Dict, List


class OpenAIAdapter:
    """Lightweight OpenAI adapter using the v1+ SDK (openai>=1.0).

    Performs synchronous SDK calls inside asyncio.to_thread to avoid blocking
    the event loop.  Import is lazy so tests without openai installed still work.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        self._config = config or {}
        # Default: gpt-4o-mini (cheap, fast, sufficient for MammothOS workloads)
        # Override with OPENAI_MODEL env var or config["model"]
        self.model = self._config.get("model") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.api_key = self._config.get("api_key") or os.getenv("OPENAI_API_KEY")
        self.base_url = self._config.get("base_url") or os.getenv("OPENAI_BASE_URL")
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "openai package is required. Run: pip install 'openai>=1.0'"
                ) from exc
            api_key = self.api_key
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY environment variable is not set. "
                    "Add it to your .env file or set it in your terminal."
                )
            client_kwargs = {"api_key": api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            self._client = OpenAI(**client_kwargs)
        return self._client

    async def generate(self, prompt: str, **kwargs) -> str:
        client = self._ensure_client()
        timeout = kwargs.pop("timeout", int(os.getenv("OPENAI_TIMEOUT", "60")))

        def _sync_call():
            params: Dict[str, Any] = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
            }
            for k in ("temperature", "max_tokens"):
                if k in kwargs:
                    params[k] = kwargs[k]
            return client.chat.completions.create(**params)

        try:
            resp = await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"OpenAI generate timed out after {timeout}s")

        return resp.choices[0].message.content

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        client = self._ensure_client()
        timeout = kwargs.pop("timeout", int(os.getenv("OPENAI_TIMEOUT", "60")))
        embedding_model = self._config.get("embedding_model", "text-embedding-3-small")

        def _sync_call():
            return client.embeddings.create(input=texts, model=embedding_model)

        try:
            resp = await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"OpenAI embed timed out after {timeout}s")

        return [d.embedding for d in resp.data]
