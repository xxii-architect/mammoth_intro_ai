import asyncio
import os
from typing import Any, Dict, List

from .llm_completion import Completion


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
        return (await self.generate_completion(prompt, **kwargs)).text

    async def generate_completion(self, prompt: str, **kwargs) -> Completion:
        client = self._ensure_client()
        timeout = kwargs.pop("timeout", int(os.getenv("OPENAI_TIMEOUT", "60")))
        decision_json = kwargs.pop("decision_json", False)
        decision_schema = kwargs.pop("decision_schema", None)
        decision_protocol = "text"
        official_openai = not self.base_url or self.base_url.rstrip("/") == "https://api.openai.com/v1"
        official_deepseek = bool(self.base_url and self.base_url.rstrip("/") in {
            "https://api.deepseek.com", "https://api.deepseek.com/v1",
        })
        known_openai = (
            official_openai
            and self.model in {
                "gpt-4o", "gpt-4o-2024-08-06", "gpt-4o-2024-11-20",
                "gpt-4o-mini", "gpt-4o-mini-2024-07-18",
                "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
                "gpt-4.1-2025-04-14", "gpt-4.1-mini-2025-04-14", "gpt-4.1-nano-2025-04-14",
            }
        )
        if decision_schema is not None and known_openai and self._config.get("structured_decisions", True):
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "mammoth_decision", "strict": True, "schema": decision_schema},
            }
            decision_protocol = "json_schema"
        elif decision_json and (
            (official_openai and self.model.startswith(("gpt-4o", "gpt-4.1")))
            or (official_deepseek and self.model in {"deepseek-chat", "deepseek-flash"})
        ):
            kwargs["response_format"] = {"type": "json_object"}
            decision_protocol = "json_object"

        system_prompt = kwargs.pop("system_prompt", None)
        _messages = []
        if system_prompt:
            _messages.append({"role": "system", "content": system_prompt})
        _messages.append({"role": "user", "content": prompt})
        if decision_protocol == "json_schema":
            _messages.append({
                "role": "system",
                "content": (
                    "For this decision use the supplied mammoth_decision schema instead of the text JSON shape. "
                    "action is tool, answer, or finalize. args_json is a JSON object encoded as a string, using "
                    "the tool catalog's argument schema. tool action requires an available tool and final=null; "
                    "answer requires tool=null, args_json='{}', and a complete final answer; finalize requires "
                    "tool=null, args_json='{}', final=null and requests separate prose finalization. "
                    "reasoning is a short public rationale, never private chain-of-thought. "
                    "Use [] when the plan is unchanged. Keep plans to at most 12 short steps."
                ),
            })

        def _sync_call():
            params: Dict[str, Any] = {
                "model": self.model,
                "messages": _messages,
            }
            for k in ("temperature", "max_tokens", "response_format"):
                if k in kwargs:
                    params[k] = kwargs[k]
            return client.chat.completions.create(**params)

        try:
            resp = await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=timeout)
        except asyncio.TimeoutError:
            raise RuntimeError(f"OpenAI generate timed out after {timeout}s")

        msg = resp.choices[0].message
        usage = getattr(resp, "usage", None)
        return Completion(
            text=msg.content or "",
            finish_reason="refusal" if getattr(msg, "refusal", None) else str(getattr(resp.choices[0], "finish_reason", "") or ""),
            usage={
                key: int(getattr(usage, key, 0) or 0)
                for key in ("prompt_tokens", "completion_tokens", "total_tokens")
            } if usage is not None else {},
            model=str(getattr(resp, "model", "") or self.model),
            decision_protocol=decision_protocol,
        )

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
