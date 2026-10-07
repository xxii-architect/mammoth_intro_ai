"""Provider-constrained decision envelope, independent of tool execution."""

import json
from typing import Any, Dict, Iterable, Optional


def _json(text: str) -> Any:
    def reject_constant(value: str) -> Any:
        raise ValueError(f"Invalid JSON constant: {value}")

    def unique_object(items: list[tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(text, parse_constant=reject_constant, object_pairs_hook=unique_object)


def decision_schema(tool_names: Iterable[str]) -> Dict[str, Any]:
    # Tool argument schemas can be open-ended; keep them in a JSON string and
    # validate against the original registry schema before requesting approval.
    return {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["tool", "answer", "finalize"]},
            "reasoning": {"type": "string"},
            "plan": {"type": "array", "items": {"type": "string"}},
            "tool": {"type": ["string", "null"], "enum": [None, *sorted(set(tool_names))]},
            "args_json": {"type": "string"},
            "final": {"type": ["string", "null"]},
        },
        "required": ["action", "reasoning", "plan", "tool", "args_json", "final"],
        "additionalProperties": False,
    }


def parse_structured_decision(text: str, tool_names: Iterable[str]) -> Optional[Dict[str, Any]]:
    try:
        raw = _json(text)
    except (ValueError, TypeError):
        return None
    required = {"action", "reasoning", "plan", "tool", "args_json", "final"}
    if not isinstance(raw, dict) or set(raw) != required:
        return None
    if not isinstance(raw["reasoning"], str) or not isinstance(raw["plan"], list):
        return None
    if len(raw["reasoning"]) > 1200 or len(raw["plan"]) > 12:
        return None
    if any(not isinstance(item, str) or not item.strip() or len(item) > 160 for item in raw["plan"]):
        return None
    if not isinstance(raw["args_json"], str):
        return None
    try:
        args = _json(raw["args_json"])
    except ValueError:
        return None
    if not isinstance(args, dict):
        return None
    action, tool, final = raw["action"], raw["tool"], raw["final"]
    if action == "tool":
        if not isinstance(tool, str) or tool not in set(tool_names) or final is not None:
            return None
    elif action == "answer":
        if tool is not None or args or not isinstance(final, str) or not final.strip():
            return None
    elif action == "finalize":
        if tool is not None or args or final is not None:
            return None
    else:
        return None
    return {"reasoning": raw["reasoning"], "plan": raw["plan"], "tool": tool, "args": args, "final": final}
