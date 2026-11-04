"""Local input admission estimates, distinct from provider-reported usage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InputAllowance:
    tokens: int
    method: str
    model: str
    overhead: int = 1024


def input_allowance(client: Any, prompt: str, options: dict) -> InputAllowance:
    prepare = getattr(client, "completion_payload", None)
    if callable(prepare):
        payload, _ = prepare(prompt, options)
        messages = payload["messages"]
        # Tokenize only documented model text; reserve byte bounds for the envelope/schema.
        official = not client.base_url or client.base_url.rstrip("/") == "https://api.openai.com/v1"
        supported = client.model in {
            "gpt-4o", "gpt-4o-2024-08-06", "gpt-4o-2024-11-20",
            "gpt-4o-mini", "gpt-4o-mini-2024-07-18",
            "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
            "gpt-4.1-2025-04-14", "gpt-4.1-mini-2025-04-14", "gpt-4.1-nano-2025-04-14",
        }
        try:
            if official and supported:
                import tiktoken

                encoding = tiktoken.encoding_for_model(client.model)
                texts = sum(len(encoding.encode(message["content"], disallowed_special=())) for message in messages)
                envelope = {**payload, "messages": [{**message, "content": ""} for message in messages]}
                return InputAllowance(
                    texts + len(json.dumps(envelope, ensure_ascii=False).encode("utf-8")),
                    "model_tokenizer_with_byte_envelope", client.model,
                )
        except (ImportError, KeyError, OSError, ValueError):
            # Missing local tokenizer assets do not justify an unlabelled chars/token guess.
            pass
        return InputAllowance(len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
                              "utf8_byte_upper_bound", client.model)
    return InputAllowance(
        len(prompt.encode("utf-8")) + len(json.dumps(options, default=str, ensure_ascii=False).encode("utf-8")),
        "utf8_byte_upper_bound", str(getattr(client, "model", "unknown")),
    )


def reported_tokens(usage: dict) -> int:
    total = usage.get("total_tokens")
    if total is None and all(type(usage.get(key)) is int and usage[key] >= 0
                             for key in ("prompt_tokens", "completion_tokens")):
        total = usage["prompt_tokens"] + usage["completion_tokens"]
    if type(total) is not int or total < 1:
        raise ValueError("provider_usage_unavailable")
    return total
