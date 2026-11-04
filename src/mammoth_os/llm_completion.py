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
    from .runtime_ledger import current_ledger
    from .token_admission import input_allowance

    ledger = current_ledger() if not getattr(client, "delegates_admission", False) else None
    admission = kwargs.pop("_admission", None)
    admitted = None
    if admission is not None:
        if getattr(client, "delegates_admission", False):
            kwargs["_admission"] = admission
        else:
            allowance = input_allowance(client, prompt, kwargs)
            kwargs["max_tokens"] = admission(allowance, kwargs.get("max_tokens", 4096))
            admitted = {**asdict(allowance), "output_limit": kwargs["max_tokens"]}
    identity = None
    if ledger is not None:
        from .llm_client import _client_label

        allowance = input_allowance(client, prompt, kwargs)
        output_limit = kwargs.get("max_tokens", 4096)
        if type(output_limit) is not int or output_limit < 1:
            raise ValueError("A positive output token limit is required for metered calls.")
        kwargs["max_tokens"] = output_limit
        identity = ledger.reserve(_client_label(client), str(getattr(client, "model", "unknown")),
                                  allowance.tokens + allowance.overhead + output_limit)
    try:
        method = getattr(client, "generate_completion", None)
        if callable(method):
            result = await method(prompt, **kwargs)
            if not isinstance(result, Completion):
                raise TypeError("generate_completion must return Completion")
        else:
            result = Completion(text=str(await client.generate(prompt, **kwargs) or ""))
    except BaseException:
        if identity:
            ledger.finish(identity, failed=True)
        raise
    if identity:
        ledger.finish(identity, usage=result.usage)
    return replace(result, admission=admitted) if admitted is not None else result
