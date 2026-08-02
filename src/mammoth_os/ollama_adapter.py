"""mammoth_os/ollama_adapter.py — Ollama local model adapter.

Implements the same async generate/embed interface as OpenAIAdapter so
get_llm_client() can swap between cloud and local models transparently.

Supported models (all installed locally):
    hermes3:8b          — best for agent/instruction tasks (ATLAS tutor, hints)
    deepseek-coder      — best for code generation (CodingAgent)
    qwen2.5-coder       — alternative code model
    codellama           — code generation fallback
    llama3.1:8b         — general purpose
    mistral             — general purpose fallback
    qwen2.5             — general purpose
    phi3                — fast/lightweight tasks
    nous-hermes:7b      — instruction following

Configured via .env:
    OLLAMA_MODEL=hermes3:8b          # which model to use (default: hermes3:8b)
    OLLAMA_BASE_URL=http://localhost:11434   # where Ollama is running (default)
    OLLAMA_EMBED_MODEL=llama3.1:8b   # model used for embeddings (default)
"""

import asyncio
import json
import os
import urllib.request
import urllib.error
from typing import Any, Dict, List

# Convenient short aliases → actual Ollama model names
MODEL_ALIASES: Dict[str, str] = {
    "hermes":       "hermes3:8b",
    "hermes3":      "hermes3:8b",
    "deepseek":     "deepseek-coder:latest",
    "deepseek-coder": "deepseek-coder:latest",
    "codellama":    "codellama:latest",
    "llama":        "llama3.1:8b",
    "llama3":       "llama3.1:8b",
    "mistral":      "mistral:latest",
    "qwen":         "qwen2.5:latest",
    "qwen-coder":   "qwen2.5-coder:latest",
    "phi":          "phi3:latest",
    "phi3":         "phi3:latest",
    "nous-hermes":  "nous-hermes:7b",
}

# Default model for each use-case role (used when no explicit model is set)
ROLE_DEFAULTS: Dict[str, str] = {
    "code":    "deepseek-coder:latest",   # CodingAgent generate/refactor
    "tutor":   "hermes3:8b",              # TutorAgent hints + ATLAS loop
    "general": "hermes3:8b",              # everything else
}


def _resolve_model(name: str) -> str:
    """Resolve alias or role name to actual Ollama model tag."""
    return MODEL_ALIASES.get(name, name)


def check_ollama_running(base_url: str = "http://localhost:11434") -> bool:
    """Return True if Ollama is reachable."""
    try:
        req = urllib.request.Request(f"{base_url}/api/tags")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


class OllamaAdapter:
    """Async LLM adapter for locally running Ollama models.

    Uses Ollama's /api/chat endpoint for generation and /api/embed
    (or /api/embeddings for older Ollama) for vector embeddings.
    """

    def __init__(self, config: Dict[str, Any] | None = None):
        cfg = config or {}
        raw_model = (
            cfg.get("model")
            or os.getenv("OLLAMA_MODEL")
            or "hermes3:8b"
        )
        self.model = _resolve_model(raw_model)
        self.base_url = (
            cfg.get("base_url")
            or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        raw_embed = (
            cfg.get("embedding_model")
            or os.getenv("OLLAMA_EMBED_MODEL")
            or "llama3.1:8b"
        )
        self.embed_model = _resolve_model(raw_embed)

    # ─────────────────────────────────────────────────────────────────────
    # generate
    # ─────────────────────────────────────────────────────────────────────

    async def generate(self, prompt: str, **kwargs) -> str:
        timeout = kwargs.pop("timeout", int(os.getenv("OLLAMA_TIMEOUT", "120")))

        def _sync_call() -> str:
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
            # Pass temperature if provided
            if "temperature" in kwargs:
                payload["options"] = {"temperature": kwargs["temperature"]}

            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            # /api/chat response: {"message": {"role": "assistant", "content": "..."}}
            return body.get("message", {}).get("content", "").strip()

        try:
            return await asyncio.wait_for(asyncio.to_thread(_sync_call), timeout=timeout + 5)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Ollama generate timed out after {timeout}s (model: {self.model})")
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama not reachable at {self.base_url}. "
                f"Make sure Ollama is running: ollama serve\n  ({exc})"
            ) from exc

    # ─────────────────────────────────────────────────────────────────────
    # embed
    # ─────────────────────────────────────────────────────────────────────

    async def embed(self, texts: List[str], **kwargs) -> List[List[float]]:
        """Return embeddings for a list of texts using the embed model."""
        timeout = kwargs.pop("timeout", int(os.getenv("OLLAMA_TIMEOUT", "60")))

        def _embed_one(text: str) -> List[float]:
            # Try /api/embed (Ollama >= 0.1.26) first, fall back to /api/embeddings
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
                    # /api/embed → {"embeddings": [[...]]}  or  /api/embeddings → {"embedding": [...]}
                    if "embeddings" in body:
                        return body["embeddings"][0]
                    if "embedding" in body:
                        return body["embedding"]
                except urllib.error.HTTPError:
                    continue
            # Final fallback: zero vector
            return [0.0]

        def _sync_all():
            return [_embed_one(t) for t in texts]

        try:
            return await asyncio.wait_for(asyncio.to_thread(_sync_all), timeout=timeout + 5)
        except asyncio.TimeoutError:
            raise RuntimeError(f"Ollama embed timed out after {timeout}s")
