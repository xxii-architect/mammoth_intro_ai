"""mammoth_os/ollama_adapter.py - Ollama local model adapter.

Implements the same async generate/embed interface as OpenAIAdapter so
get_llm_client() can swap between cloud and local models transparently.

Supported models (all installed locally):
    hermes3:8b          - best for agent/instruction tasks (ATLAS tutor, hints)
    deepseek-coder      - best for code generation (CodingAgent)
    qwen2.5-coder       - alternative code model
    codellama           - code generation fallback
    llama3.1:8b         - general purpose
    mistral             - general purpose fallback
    qwen2.5             - general purpose
    phi3                - fast/lightweight tasks
    nous-hermes:7b      - instruction following

Configured via .env:
    OLLAMA_MODEL=hermes3:8b
    OLLAMA_BASE_URL=http://localhost:11434
    OLLAMA_EMBED_MODEL=llama3.1:8b
"""

import asyncio
import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List

from .llm_completion import Completion

MODEL_ALIASES: Dict[str, str] = {
    "hermes": "hermes3:8b",
    "hermes3": "hermes3:8b",
    "deepseek": "deepseek-coder:latest",
    "deepseek-coder": "deepseek-coder:latest",
    "codellama": "codellama:latest",
    "llama": "llama3.1:8b",
    "llama3": "llama3.1:8b",
    "mistral": "mistral:latest",
    "qwen": "qwen2.5:latest",
    "qwen-coder": "qwen2.5-coder:latest",
    "phi": "phi3:latest",
    "phi3": "phi3:latest",
    "nous-hermes": "nous-hermes:7b",
}

ROLE_DEFAULTS: Dict[str, str] = {
    "code": "deepseek-coder:latest",
    "tutor": "hermes3:8b",
    "general": "hermes3:8b",
}


def _resolve_model(name: str) -> str:
    return MODEL_ALIASES.get(name, name)


def check_ollama_running(base_url: str = "http://localhost:11434") -> bool:
    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


class OllamaAdapter:
    """Async LLM adapter for locally running Ollama models."""

    def __init__(self, config: Dict[str, Any] | None = None):
        cfg = config or {}
        raw_model = cfg.get("model") or os.getenv("OLLAMA_MODEL") or "hermes3:8b"
        self.model = _resolve_model(raw_model)
        self.base_url = (cfg.get("base_url") or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        raw_embed = cfg.get("embedding_model") or os.getenv("OLLAMA_EMBED_MODEL") or "llama3.1:8b"
        self.embed_model = _resolve_model(raw_embed)

    async def generate(self, prompt: str, **kwargs) -> str:
        return (await self.generate_completion(prompt, **kwargs)).text

    async def generate_completion(self, prompt: str, **kwargs) -> Completion:
        timeout = kwargs.pop("timeout", int(os.getenv("OLLAMA_TIMEOUT", "120")))

        def _result(body, text):
            return Completion(
                text=str(text or "").strip(),
                finish_reason=str(body.get("done_reason") or ""),
                usage={
                    "prompt_tokens": int(body.get("prompt_eval_count") or 0),
                    "completion_tokens": int(body.get("eval_count") or 0),
                    "total_tokens": int(body.get("prompt_eval_count") or 0) + int(body.get("eval_count") or 0),
                } if "prompt_eval_count" in body or "eval_count" in body else {},
                model=str(body.get("model") or self.model),
                decision_protocol="json_object" if kwargs.get("decision_json") else "text",
            )

        options = {}
        if "temperature" in kwargs:
            options["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            options["num_predict"] = kwargs["max_tokens"]

        def _sync_call():
            chat_payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
            if options:
                chat_payload["options"] = options
            if kwargs.get("decision_json"):
                chat_payload["format"] = "json"

            chat_data = json.dumps(chat_payload).encode("utf-8")
            chat_req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=chat_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(chat_req, timeout=timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                return _result(body, body.get("message", {}).get("content"))
            except urllib.error.HTTPError as exc:
                if exc.code != 404:
                    raise

            generate_payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            }
            if options:
                generate_payload["options"] = options
            if kwargs.get("decision_json"):
                generate_payload["format"] = "json"
            generate_data = json.dumps(generate_payload).encode("utf-8")
            generate_req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=generate_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(generate_req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return _result(body, body.get("response"))

        try:
            return await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=timeout + 5)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Ollama generate timed out after {timeout}s (model: {self.model})")
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama not reachable at {self.base_url}. "
                f"Make sure Ollama is running: ollama serve\n  ({exc})"
            ) from exc

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        timeout = kwargs.pop("timeout", int(os.getenv("OLLAMA_TIMEOUT", "60")))

        def _embed_one(text: str) -> List[float]:
            for endpoint in ("/api/embed", "/api/embeddings"):
                try:
                    if endpoint == "/api/embed":
                        payload = {"model": self.embed_model, "input": text}
                    else:
                        payload = {"model": self.embed_model, "prompt": text}
                    data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(
                        f"{self.base_url}{endpoint}",
                        data=data,
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        body = json.loads(resp.read().decode("utf-8"))
                    if "embeddings" in body:
                        return body["embeddings"][0]
                    if "embedding" in body:
                        return body["embedding"]
                except urllib.error.HTTPError:
                    continue
            return [0.0]

        def _sync_all():
            return [_embed_one(t) for t in texts]

        try:
            return await asyncio.wait_for(asyncio.to_thread(_sync_all), timeout=timeout + 5)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Ollama embed timed out after {timeout}s")
