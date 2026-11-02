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


def _strict_arguments(schema: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(schema)
    if schema.get("type") == "object":
        properties = {}
        required = schema.get("required", [])
        for key, value in schema.get("properties", {}).items():
            converted = _strict_arguments(value)
            properties[key] = converted if key in required else {"anyOf": [converted, {"type": "null"}]}
        result.update(properties=properties, required=list(properties), additionalProperties=False)
    elif schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        result["items"] = _strict_arguments(schema["items"])
    return result


def _closed_arguments(schema: Dict[str, Any]) -> bool:
    if "$ref" in schema:
        return False
    if schema.get("type") == "object" and schema.get("additionalProperties") is not False:
        return False
    children = list(schema.get("properties", {}).values())
    if isinstance(schema.get("items"), dict):
        children.append(schema["items"])
    for key in ("anyOf", "allOf", "oneOf"):
        children.extend(schema.get(key, []))
    return all(_closed_arguments(child) for child in children)


def decision_schema(tool_names: Iterable[str], tool_schemas: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    # Open-ended MCP schemas retain encoded arguments; never silently close them.
    # Both formats are validated against the original schema before approval.
    result: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["tool", "answer", "finalize"]},
            "goal": {"type": "string", "enum": ["answer", "proposal", "validated", "applied"]},
            "reasoning": {"type": "string"},
            "plan": {"type": "array", "items": {"type": "string"}},
            "tool": {"type": ["string", "null"], "enum": [None, *sorted(set(tool_names))]},
            "args_json": {"type": "string"},
            "final": {"type": ["string", "null"]},
        },
        "required": ["action", "goal", "reasoning", "plan", "tool", "args_json", "final"],
        "additionalProperties": False,
    }
    if tool_schemas is not None and all(_closed_arguments(schema) for schema in tool_schemas.values()):
        variants = [{"type": "object", "properties": {}, "required": [], "additionalProperties": False}]
        for schema in tool_schemas.values():
            converted = _strict_arguments(schema)
            if converted not in variants:
                variants.append(converted)
        result["properties"].pop("args_json")
        result["properties"]["args"] = {"anyOf": variants}
        result["required"] = [key for key in result["properties"]]
    return result


def parse_structured_decision(text: str, tool_names: Iterable[str]) -> Optional[Dict[str, Any]]:
    try:
        raw = _json(text)
    except (ValueError, TypeError):
        return None
    required = {"action", "goal", "reasoning", "plan", "tool", "final"}
    if not isinstance(raw, dict) or set(raw) not in (required | {"args"}, required | {"args_json"}):
        return None
    if not isinstance(raw["goal"], str) or raw["goal"] not in {"answer", "proposal", "validated", "applied"}:
        return None
    if not isinstance(raw["reasoning"], str) or not isinstance(raw["plan"], list):
        return None
    if len(raw["reasoning"]) > 1200 or len(raw["plan"]) > 12:
        return None
    if any(not isinstance(item, str) or not item.strip() or len(item) > 160 for item in raw["plan"]):
        return None
    if "args" in raw:
        args = raw["args"]
    else:
        if not isinstance(raw["args_json"], str):
            return None
        try:
            # Legacy schema compatibility. Required arguments are still validated.
            args = _json(raw["args_json"] if raw["args_json"].strip() else "{}")
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
    return {"goal": raw["goal"], "reasoning": raw["reasoning"], "plan": raw["plan"], "tool": tool, "args": args, "final": final}


def omit_optional_nulls(args: Any, schema: Dict[str, Any]) -> Any:
    if isinstance(args, dict):
        properties = schema.get("properties") or {}
        required = schema.get("required") or []
        return {key: omit_optional_nulls(value, properties.get(key, {})) for key, value in args.items()
                if value is not None or key in required or key not in properties}
    if isinstance(args, list):
        return [omit_optional_nulls(value, schema.get("items") or {}) for value in args]
    return args
