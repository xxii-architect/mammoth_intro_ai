"""Additive completion metadata; text-only adapters remain supported."""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(frozen=True)
class Completion:
    text: str
    finish_reason: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = ""
    provider: str = ""
    decision_protocol: str = ""


async def complete(client: Any, prompt: str, **kwargs: Any) -> Completion:
    method = getattr(client, "generate_completion", None)
    if callable(method):
        result = await method(prompt, **kwargs)
        if not isinstance(result, Completion):
            raise TypeError("generate_completion must return Completion")
        return result
    return Completion(text=str(await client.generate(prompt, **kwargs) or ""))
