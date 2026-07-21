import os
import asyncio
from typing import Any, Dict


class OpenAIAdapter:
    """Lightweight OpenAI adapter with lazy import.

    This adapter performs synchronous SDK calls inside asyncio.to_thread to
    avoid blocking the event loop and to keep imports lazy so tests/workflows
    without OpenAI installed still import the module.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        self._config = config or {}
        self.model = self._config.get("model") or os.getenv("OPENAI_MODEL", "gpt-4o")
        self._openai = None

    def _ensure_openai(self):
        if self._openai is None:
            try:
                import openai
            except Exception as exc:
                raise RuntimeError("OpenAI SDK is required for OpenAIAdapter but not available") from exc
            openai.api_key = os.getenv("OPENAI_API_KEY")
            self._openai = openai
        return self._openai

    async def generate(self, prompt: str, **kwargs) -> str:
        openai = self._ensure_openai()

        timeout = kwargs.pop("timeout", int(os.getenv("OPENAI_TIMEOUT", "30")))

        def _sync_call():
            messages = [{"role": "user", "content": prompt}]
            params = {"model": self.model, "messages": messages}
            # allow temperature/max_tokens overrides
            for k in ("temperature", "max_tokens"):
                if k in kwargs:
                    params[k] = kwargs[k]
            resp = openai.ChatCompletion.create(**params)
            return resp

        # Run the blocking SDK call in a thread with a timeout
        try:
            resp = await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"OpenAI generate timed out after {timeout}s")

        # extract text
        try:
            if hasattr(resp, "choices"):
                return resp.choices[0].message.content
            if isinstance(resp, dict) and "choices" in resp:
                return resp["choices"][0]["message"]["content"]
        except Exception:
            pass
        return str(resp)

    async def embed(self, texts: list[str], **kwargs) -> list[list[float]]:
        openai = self._ensure_openai()
        timeout = kwargs.pop("timeout", int(os.getenv("OPENAI_TIMEOUT", "30")))

        def _sync_call():
            model = self._config.get("embedding_model", "text-embedding-3-small")
            return openai.Embeddings.create(input=texts, model=model)

        try:
            resp = await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"OpenAI embed timed out after {timeout}s")

        if isinstance(resp, dict) and "data" in resp:
            return [d["embedding"] for d in resp["data"]]
        try:
            return [d.embedding for d in resp.data]
        except Exception:
            raise RuntimeError("Unexpected embeddings response format from OpenAI")
