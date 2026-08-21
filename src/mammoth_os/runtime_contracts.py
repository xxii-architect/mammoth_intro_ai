from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


CONTRACT_VERSION = "v2"


def new_trace_id(prefix: str = "run") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _coerce_iso(value: Any) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    return str(value or "")


def _text_preview(value: Any, max_len: int = 220) -> str:
    text = str(value or "").strip()
    return text[:max_len]


def build_runtime_notice(
    runtime_status: Dict[str, Any],
    *,
    trace_id: str = "",
    agent_id: str = "",
    context: str = "",
    provider: str = "",
) -> Dict[str, Any]:
    runtime_status = dict(runtime_status or {})
    providers = runtime_status.get("providers") if isinstance(runtime_status.get("providers"), list) else []
    fallback_chain = runtime_status.get("fallback_chain") if isinstance(runtime_status.get("fallback_chain"), list) else []
    state = str(runtime_status.get("state") or "ready").strip().lower() or "ready"
    degraded = bool(runtime_status.get("degraded_mode")) or state != "ready"
    issue = str(runtime_status.get("issue") or "").strip()
    if not issue:
        issue = "The runtime is operating normally." if not degraded else "The runtime is in degraded fallback mode."
    recommendation = str(runtime_status.get("recommendation") or "").strip()
    return {
        "contract_version": CONTRACT_VERSION,
        "trace_id": trace_id,
        "agent_id": agent_id,
        "context": context,
        "provider": provider,
        "state": state,
        "degraded_mode": degraded,
        "active_adapter": str(runtime_status.get("active_adapter") or "local").strip() or "local",
        "active_model": str(runtime_status.get("active_model") or "local-adapter").strip() or "local-adapter",
        "available_providers": runtime_status.get("available_providers") or [],
        "fallback_chain": fallback_chain,
        "providers": providers,
        "issue": issue,
        "next_action": str(runtime_status.get("next_action") or "").strip(),
        "recommendation": recommendation,
        "summary": runtime_status.get("summary") or {},
    }


def build_run_envelope(
    *,
    status: str,
    agent_id: str,
    trace_id: str,
    result: Any,
    runtime_notice: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = result if isinstance(result, dict) else {"value": result}
    payload.setdefault("status", status)
    return {
        "status": status,
        "contract_version": CONTRACT_VERSION,
        "trace_id": trace_id,
        "agent_id": agent_id,
        "runtime_notice": runtime_notice or {},
        "result": payload,
    }


def build_observability_run(
    *,
    run_id: str,
    source: str,
    title: str,
    status: str,
    created_at: Any,
    updated_at: Any = "",
    objective: str = "",
    plan_profile: str = "",
    trace_id: str = "",
    summary: str = "",
    replay: Optional[Dict[str, Any]] = None,
    progress: Optional[Dict[str, Any]] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "source": source,
        "title": title,
        "status": status,
        "created_at": _coerce_iso(created_at),
        "updated_at": _coerce_iso(updated_at),
        "objective": objective,
        "plan_profile": plan_profile,
        "trace_id": trace_id,
        "summary": summary,
        "replay": replay or {},
        "progress": progress or {},
        "details": details or {},
    }

