"""Tool registry with JSON-schema inputs and permission tiers.

Tiers describe blast radius, not trust:

* ``read``    – inspects data the caller already has access to.
* ``network`` – reaches the public internet.
* ``write``   – produces a change (in MammothOS this is always a proposal).
* ``exec``    – runs a process. Always requires explicit approval.

Visibility is decided per call from :class:`ToolContext`, so the same registry
can serve the owner, tenants, and anonymous visitors without leaking tools.
"""

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

TIER_READ = "read"
TIER_NETWORK = "network"
TIER_WRITE = "write"
TIER_EXEC = "exec"
TIERS = (TIER_READ, TIER_NETWORK, TIER_WRITE, TIER_EXEC)

MAX_RESULT_CHARS = 24_000

ToolHandler = Callable[[Dict[str, Any], "ToolContext"], Union[Dict[str, Any], Awaitable[Dict[str, Any]]]]


@dataclass
class ToolContext:
    user_id: str
    is_admin: bool = False
    repo_root: Optional[Path] = None
    repo_scope: str = "none"
    repo_slug: str = ""
    repo_source_id: str = ""
    policy: Any = None
    extras: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_repo(self) -> bool:
        return self.repo_root is not None


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    tier: str
    handler: ToolHandler
    trace_kind: str = "tool"
    admin_only: bool = False
    needs_repo: bool = False
    requires_approval: Optional[bool] = None
    source: str = "builtin"
    available: Optional[Callable[["ToolContext"], bool]] = None

    def __post_init__(self) -> None:
        if self.tier not in TIERS:
            raise ValueError(f"Unknown tool tier: {self.tier}")
        if self.requires_approval is None:
            self.requires_approval = self.tier == TIER_EXEC

    def visible_to(self, ctx: ToolContext) -> bool:
        if self.admin_only and not ctx.is_admin:
            return False
        if self.needs_repo and not ctx.has_repo:
            return False
        if self.available is not None and not self.available(ctx):
            return False
        return True

    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tier": self.tier,
            "trace_kind": self.trace_kind,
            "requires_approval": bool(self.requires_approval),
            "source": self.source,
            "input_schema": self.input_schema,
        }


_JSON_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def validate_args(schema: Dict[str, Any], value: Any, path: str = "args") -> List[str]:
    """Validate against the JSON Schema subset tools use. Returns error strings."""
    errors: List[str] = []
    if not isinstance(schema, dict) or not schema:
        return errors
    expected = schema.get("type")
    if expected:
        py_type = _JSON_TYPES.get(expected)
        if py_type is not None:
            is_bool = isinstance(value, bool)
            if expected in {"integer", "number"} and is_bool:
                return [f"{path}: expected {expected}"]
            if not isinstance(value, py_type):
                return [f"{path}: expected {expected}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: must be one of {schema['enum']}")
    if isinstance(value, str):
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            errors.append(f"{path}: longer than {schema['maxLength']} characters")
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            errors.append(f"{path}: shorter than {schema['minLength']} characters")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")
    if isinstance(value, list):
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            errors.append(f"{path}: more than {schema['maxItems']} items")
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                errors.extend(validate_args(item_schema, item, f"{path}[{idx}]"))
    if isinstance(value, dict):
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        for key in schema.get("required") or []:
            if key not in value:
                errors.append(f"{path}.{key}: required")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}.{key}: not allowed")
        for key, sub in props.items():
            if key in value:
                errors.extend(validate_args(sub, value[key], f"{path}.{key}"))
    return errors


def _clip_result(result: Dict[str, Any]) -> Dict[str, Any]:
    encoded = json.dumps(result, default=str)
    if len(encoded) <= MAX_RESULT_CHARS:
        return result
    return {
        "status": result.get("status", "ok"),
        "truncated": True,
        "preview": encoded[:MAX_RESULT_CHARS],
    }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> ToolSpec:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = spec
        return spec

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return sorted(self._tools)

    def available(self, ctx: ToolContext) -> List[ToolSpec]:
        return [spec for name, spec in sorted(self._tools.items()) if spec.visible_to(ctx)]

    def catalog(self, ctx: ToolContext) -> List[Dict[str, Any]]:
        return [spec.describe() for spec in self.available(ctx)]

    def resolve(self, name: str, ctx: ToolContext) -> Optional[ToolSpec]:
        spec = self._tools.get(str(name or ""))
        if spec is None or not spec.visible_to(ctx):
            return None
        return spec

    async def invoke(self, name: str, args: Any, ctx: ToolContext, *, timeout_s: float = 60.0) -> Dict[str, Any]:
        spec = self.resolve(name, ctx)
        if spec is None:
            return {"status": "error", "code": "unknown_tool", "error": f"Tool not available: {name}"}
        if args is None:
            args = {}
        errors = validate_args(spec.input_schema, args)
        if errors:
            return {"status": "error", "code": "invalid_args", "error": "; ".join(errors[:6])}
        try:
            outcome = spec.handler(args, ctx)
            if inspect.isawaitable(outcome):
                outcome = await asyncio.wait_for(outcome, timeout=timeout_s)
        except asyncio.TimeoutError:
            return {"status": "error", "code": "timeout", "error": f"{name} timed out after {int(timeout_s)}s"}
        except Exception as exc:  # tool failures must never crash the run
            return {"status": "error", "code": "tool_error", "error": f"{type(exc).__name__}: {exc}"[:500]}
        if not isinstance(outcome, dict):
            outcome = {"status": "ok", "result": outcome}
        outcome.setdefault("status", "ok")
        return _clip_result(outcome)
