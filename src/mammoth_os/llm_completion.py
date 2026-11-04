"""Additive completion metadata; text-only adapters remain supported."""

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict


@dataclass(frozen=True)
class Completion:
    text: str
    finish_reason: str = ""
    usage: Dict[str, int] = field(default_factory=dict)
    model: str = ""
    provider: str = ""
    decision_protocol: str = ""
    admission: Dict[str, Any] = field(default_factory=dict)


async def complete(client: Any, prompt: str, **kwargs: Any) -> Completion:
    admission = kwargs.pop("_admission", None)
    admitted = None
    if admission is not None:
        if getattr(client, "delegates_admission", False):
            kwargs["_admission"] = admission
        else:
            from .token_admission import input_allowance

            allowance = input_allowance(client, prompt, kwargs)
            kwargs["max_tokens"] = admission(allowance, kwargs.get("max_tokens", 4096))
            admitted = {**asdict(allowance), "output_limit": kwargs["max_tokens"]}
    method = getattr(client, "generate_completion", None)
    if callable(method):
        result = await method(prompt, **kwargs)
        if not isinstance(result, Completion):
            raise TypeError("generate_completion must return Completion")
        return replace(result, admission=admitted) if admitted is not None else result
    result = Completion(text=str(await client.generate(prompt, **kwargs) or ""))
    return replace(result, admission=admitted) if admitted is not None else result
