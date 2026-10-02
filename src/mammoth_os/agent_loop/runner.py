"""Mammoth Mind agent loop.

A provider-agnostic plan → act → observe loop. Each step asks the model for one
JSON decision (reasoning summary, optional plan, then either a tool call or a
final answer). Tool calls run through :class:`ToolRegistry`, so permissions and
schema validation are enforced server-side regardless of what the model asks.

Tools that require approval pause the run (``run.awaiting_approval``). The run
is persisted, and :meth:`AgentRunner.resume` continues it after the user
decides. Context is rebuilt on resume, so access is re-checked at that point.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from . import events as ev
from .tools import ToolContext, ToolRegistry

DEFAULT_MAX_STEPS = 8
MAX_OBSERVATION_CHARS = 6_000
RUN_ID_RE = re.compile(r"^run-[a-f0-9]{16}$")

LLMFactory = Callable[[], Any]
OFFLINE_MESSAGE = (
    "No language model provider is reachable right now, so I can't reason about this request. "
    "Configure DEEPSEEK_API_KEY or OPENAI_API_KEY, or start Ollama, then try again."
)


@dataclass
class AgentRun:
    id: str
    user_id: str
    message: str
    agent_id: str = "assistant"
    status: str = "running"
    created_at: str = field(default_factory=ev.utc_now)
    updated_at: str = field(default_factory=ev.utc_now)
    plan: List[Dict[str, Any]] = field(default_factory=list)
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    events: List[Dict[str, Any]] = field(default_factory=list)
    pending_approval: Optional[Dict[str, Any]] = None
    reply: str = ""
    provider: str = ""
    model: str = ""
    steps: int = 0
    request: Dict[str, Any] = field(default_factory=dict)
    cancel_requested: bool = False

    @staticmethod
    def new_id() -> str:
        return f"run-{secrets.token_hex(8)}"

    def to_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentRun":
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def public(self) -> Dict[str, Any]:
        data = self.to_dict()
        data.pop("request", None)
        data.pop("cancel_requested", None)
        return data


class RunStore:
    """Per-user run persistence (JSON files). Run ids are unguessable and owner-checked."""

    def __init__(self, base_dir: Path, *, keep_per_user: int = 50):
        self.base_dir = base_dir
        self.keep_per_user = keep_per_user
        self._lock = threading.Lock()
        self._live: Dict[str, AgentRun] = {}

    def _user_dir(self, user_id: str) -> Path:
        from mammoth_os.repo_access import user_storage_key

        return self.base_dir / user_storage_key(user_id)

    def save(self, run: AgentRun) -> None:
        run.updated_at = ev.utc_now()
        with self._lock:
            self._live[run.id] = run
            folder = self._user_dir(run.user_id)
            folder.mkdir(parents=True, exist_ok=True)
            tmp = folder / f"{run.id}.json.tmp"
            tmp.write_text(json.dumps(run.to_dict(), default=str), encoding="utf-8")
            tmp.replace(folder / f"{run.id}.json")
            files = sorted(folder.glob("run-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            for stale in files[self.keep_per_user:]:
                stale.unlink(missing_ok=True)
                self._live.pop(stale.stem, None)

    def get(self, run_id: str, user_id: str) -> Optional[AgentRun]:
        if not RUN_ID_RE.match(str(run_id or "")):
            return None
        live = self._live.get(run_id)
        if live is not None:
            return live if live.user_id == user_id else None
        path = self._user_dir(user_id) / f"{run_id}.json"
        try:
            run = AgentRun.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return None
        return run if run.user_id == user_id else None

    def list(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        folder = self._user_dir(user_id)
        if not folder.exists():
            return []
        out = []
        for path in sorted(folder.glob("run-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if data.get("user_id") != user_id:
                continue
            out.append({k: data.get(k) for k in ("id", "message", "agent_id", "status", "created_at", "updated_at", "steps")})
        return out


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.I)


def parse_decision(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object with a ``tool`` or ``final`` key."""
    if not text:
        return None
    cleaned = _FENCE_RE.sub("", text.strip())
    decoder = json.JSONDecoder()
    idx = cleaned.find("{")
    while idx != -1:
        try:
            obj, _ = decoder.raw_decode(cleaned[idx:])
        except ValueError:
            idx = cleaned.find("{", idx + 1)
            continue
        if isinstance(obj, dict) and ("tool" in obj or "final" in obj):
            return obj
        idx = cleaned.find("{", idx + 1)
    return None


def _normalize_plan(raw: Any) -> List[Dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    plan: List[Dict[str, Any]] = []
    for item in raw[:12]:
        if isinstance(item, str) and item.strip():
            plan.append({"title": item.strip()[:160], "status": "pending"})
        elif isinstance(item, dict) and str(item.get("title") or "").strip():
            status = str(item.get("status") or "pending").lower()
            if status not in {"pending", "in_progress", "done", "skipped"}:
                status = "pending"
            plan.append({"title": str(item["title"]).strip()[:160], "status": status})
    return plan


def _client_meta(client: Any) -> Dict[str, str]:
    describe = getattr(client, "describe_runtime_state", None)
    state = describe() if callable(describe) else {}
    provider = str(state.get("last_used_provider") or type(client).__name__.replace("Adapter", "").lower())
    return {
        "provider": provider,
        "model": str(getattr(client, "model", "") or state.get("model") or "unknown"),
        "fallback_used": bool(state.get("last_fallback_used")),
        "fallback_reason": str(state.get("last_fallback_reason") or ""),
    }


SYSTEM_PROMPT = """You are Mammoth Mind, the MammothOS agent. Work like a careful senior engineer:
gather facts with tools before answering, keep the plan short, and never invent file contents.

Conversation style:
- Sound like a thoughtful, approachable collaborator: warm, clear, direct, and natural. Do not sound like a scripted helpdesk or a report generator.
- Match answer depth to the request. A simple question or confirmation deserves a brief, conversational reply. A multi-part, technical, consequential, or explicitly thorough request deserves a complete, well-structured answer.
- Structure only when it helps. Use useful headings, steps, bullets, or code for complex answers; don't force a template or headings onto a simple one.
- For complex work, lead with the direct answer, then explain the reasoning that can be shared, important caveats, and actionable next steps. Never expose private chain-of-thought; provide concise rationale, evidence, and decision summaries instead.
- Avoid filler, repetitive summaries, canned openings, and branded quips. Ask a focused follow-up only when a real ambiguity blocks a good answer.

Rules:
- Respond with exactly ONE JSON object and nothing else.
- Shape: {"reasoning": "<1-2 sentence summary of why you are taking this step>",
          "plan": ["short step", ...],            (optional; send it when the plan changes)
          "tool": "<tool name>" or null,
          "args": {...},                           (required when tool is set)
          "final": "<markdown answer>" or null}
- Set exactly one of "tool" or "final".
- Only call tools from the catalog. Arguments must match the tool's input_schema.
- Changes are proposals: use repo_propose_patch with full new file contents. Never claim you applied or pushed anything.
- If no repository is connected, do not pretend to know its code.
- If a repository IS connected, never say you lack repo access or context. When the request is about the code,
  inspect it with the repo tools before answering.
"""


def describe_repo(ctx: Optional[ToolContext]) -> str:
    """One-line, model-facing description of the run's repository context."""
    if ctx is None or not ctx.has_repo:
        return "Repository context: none. No repository is connected for this run."
    if ctx.repo_scope == "platform":
        label = "MammothOS platform repository (owner only)"
    else:
        label = ctx.repo_slug or "user-connected repository"
    return (
        f"Repository context: connected to {label} (scope={ctx.repo_scope}). "
        "You can list, read, and search its files with the repo tools, and propose changes as patches "
        "(proposal-only; nothing is applied or pushed)."
    )


class AgentRunner:
    def __init__(
        self,
        registry: ToolRegistry,
        llm_factory: LLMFactory,
        store: RunStore,
        *,
        max_steps: int = DEFAULT_MAX_STEPS,
        approval_mode: str = "tools",
    ):
        self.registry = registry
        self.llm_factory = llm_factory
        self.store = store
        self.max_steps = max_steps
        self.approval_mode = approval_mode

    # ── event plumbing ──────────────────────────────────────────────────────
    def _emit(self, run: AgentRun, kind: str, data: Dict[str, Any]) -> ev.RunEvent:
        event = ev.RunEvent(run_id=run.id, seq=len(run.events) + 1, type=kind, data=data)
        run.events.append(event.to_dict())
        return event

    def _needs_approval(self, spec: Any, run: AgentRun) -> bool:
        if spec.requires_approval:
            return True
        mode = str(run.request.get("approval_mode") or self.approval_mode)
        return mode == "always" and spec.tier != "read"

    def _build_prompt(self, run: AgentRun, ctx: ToolContext) -> str:
        catalog = [
            {"name": t["name"], "description": t["description"], "tier": t["tier"], "input_schema": t["input_schema"]}
            for t in self.registry.catalog(ctx)
        ]
        repo_line = describe_repo(ctx)
        history = str(run.request.get("history_text") or "").strip()
        parts = [
            SYSTEM_PROMPT,
            repo_line,
            f"Agent lane: {run.agent_id}.",
            "Tool catalog:\n" + json.dumps(catalog, default=str),
        ]
        if run.request.get("extra_context"):
            parts.append("Additional context:\n" + str(run.request["extra_context"])[:6000])
        if history:
            parts.append("Recent conversation:\n" + history[:4000])
        parts.append(f"User request:\n{run.message}")
        if run.plan:
            parts.append("Current plan:\n" + json.dumps(run.plan))
        parts.append(self._observations_text(run))
        parts.append(
            "Decide the next step. If the observations already answer the request, respond with \"final\" now. "
            "Never repeat a tool call you already made with the same arguments."
        )
        return "\n\n".join(p for p in parts if p)

    @staticmethod
    def _observations_text(run: AgentRun) -> str:
        if not run.transcript:
            return ""
        lines = ["Observations so far (oldest first):"]
        for idx, step in enumerate(run.transcript[-10:], start=1):
            call = f"{step.get('tool')}({json.dumps(step.get('args') or {}, default=str)[:400]})"
            result = json.dumps(step.get("result") or {}, default=str)[:MAX_OBSERVATION_CHARS]
            lines.append(f"[{idx}] {call}\n    → {result}")
        return "\n".join(lines)

    def _final_prompt(self, run: AgentRun, ctx: Optional[ToolContext] = None) -> str:
        return "\n\n".join(p for p in [
            "You are Mammoth Mind, replying as a thoughtful and approachable collaborator. Use only the observations below "
            "for claims about tools or repository contents; if something could not be determined, say so plainly. "
            "Match the answer to the request instead of defaulting to one sentence or a report: simple requests get a brief, "
            "natural reply; multi-part, technical, consequential, or explicitly thorough requests get a complete answer with "
            "helpful structure (headings, steps, bullets, or code only where useful). Lead with the answer, then include "
            "necessary explanation, caveats, and next steps. Avoid filler, canned openings, and repetitive conclusions. "
            "Do not reveal private chain-of-thought; share concise rationale and evidence instead. Do not output JSON.",
            describe_repo(ctx) if ctx is not None else "",
            f"User request:\n{run.message}",
            ("Recent conversation:\n" + str(run.request.get("history_text") or "").strip()[:4000])
            if str(run.request.get("history_text") or "").strip() else "",
            self._observations_text(run),
        ] if p)

    async def _final_answer(self, run: AgentRun, ctx: Optional[ToolContext] = None) -> Dict[str, Any]:
        client = self.llm_factory()
        text = str(await client.generate(self._final_prompt(run, ctx), temperature=0.2) or "").strip()
        meta = _client_meta(client)
        run.provider, run.model = meta["provider"], meta["model"]
        if text.startswith("[LOCAL_ADAPTER]"):
            return {"final": OFFLINE_MESSAGE, "_meta": {**meta, "offline": True}}
        decision = parse_decision(text)
        if decision is not None:
            text = str(decision.get("final") or "").strip()
        return {"final": text or "I could not produce an answer from the information gathered.", "_meta": meta}

    async def _decide(self, run: AgentRun, ctx: ToolContext) -> Dict[str, Any]:
        client = self.llm_factory()
        text = await client.generate(self._build_prompt(run, ctx), temperature=0.2)
        meta = _client_meta(client)
        run.provider, run.model = meta["provider"], meta["model"]
        text = str(text or "")
        if text.startswith("[LOCAL_ADAPTER]"):
            return {"final": OFFLINE_MESSAGE, "_meta": {**meta, "offline": True}}
        decision = parse_decision(text)
        if decision is None:
            decision = {"final": text.strip() or "I could not produce an answer."}
        decision["_meta"] = meta
        return decision

    # ── main loop ───────────────────────────────────────────────────────────
    async def start(self, run: AgentRun, ctx: ToolContext) -> AsyncIterator[ev.RunEvent]:
        yield self._emit(run, ev.RUN_STARTED, {
            "agent_id": run.agent_id,
            "message": run.message[:2000],
            "repo": {"scope": ctx.repo_scope, "slug": ctx.repo_slug} if ctx.has_repo else None,
            "tools": [t.name for t in self.registry.available(ctx)],
        })
        self.store.save(run)
        async for event in self._loop(run, ctx):
            yield event

    async def resume(self, run: AgentRun, ctx: ToolContext, *, approval_id: str, approved: bool, note: str = "") -> AsyncIterator[ev.RunEvent]:
        pending = run.pending_approval or {}
        if run.status != "awaiting_approval" or pending.get("id") != approval_id:
            yield self._emit(run, ev.RUN_FAILED, {"error": "No matching approval is pending for this run."})
            return
        run.pending_approval = None
        run.status = "running"
        yield self._emit(run, ev.APPROVAL_RESOLVED, {"approval_id": approval_id, "approved": approved, "tool": pending.get("tool"), "note": note[:500]})
        if approved:
            async for event in self._execute_tool(run, ctx, pending["tool"], pending.get("args") or {}, call_id=pending.get("call_id")):
                yield event
        else:
            run.transcript.append({"tool": pending.get("tool"), "args": pending.get("args"), "result": {"status": "rejected", "note": note[:500] or "User rejected this action."}})
        self.store.save(run)
        async for event in self._loop(run, ctx):
            yield event

    def cancel(self, run: AgentRun) -> None:
        run.cancel_requested = True

    @staticmethod
    def _is_repeat(run: AgentRun, tool: str, args: Dict[str, Any]) -> bool:
        key = json.dumps(args, sort_keys=True, default=str)
        return any(
            step.get("tool") == tool and json.dumps(step.get("args") or {}, sort_keys=True, default=str) == key
            for step in run.transcript
        )

    async def _execute_tool(self, run: AgentRun, ctx: ToolContext, name: str, args: Dict[str, Any], *, call_id: Optional[str] = None) -> AsyncIterator[ev.RunEvent]:
        spec = self.registry.resolve(name, ctx)
        call_id = call_id or f"call-{secrets.token_hex(4)}"
        trace_kind = spec.trace_kind if spec else "tool"
        yield self._emit(run, ev.TOOL_CALL, {"call_id": call_id, "tool": name, "args": args, "trace_kind": trace_kind, "tier": spec.tier if spec else None})
        result = await self.registry.invoke(name, args, ctx)
        yield self._emit(run, ev.TOOL_RESULT, {"call_id": call_id, "tool": name, "status": result.get("status"), "trace_kind": trace_kind, "result": result})
        if result.get("status") == "ok" and result.get("diff"):
            yield self._emit(run, ev.DIFF_PROPOSED, {
                "call_id": call_id,
                "title": result.get("title"),
                "files": result.get("files") or [],
                "diff": result.get("diff"),
                "patch": result.get("patch"),
                "branch": result.get("branch"),
                "next_step": result.get("next_step"),
            })
        run.transcript.append({"tool": name, "args": args, "result": result})

    async def _loop(self, run: AgentRun, ctx: ToolContext) -> AsyncIterator[ev.RunEvent]:
        try:
            while True:
                if run.cancel_requested:
                    run.status = "cancelled"
                    yield self._emit(run, ev.RUN_CANCELLED, {"steps": run.steps})
                    return
                run.steps += 1
                if run.steps > self.max_steps:
                    decision = await self._final_answer(run, ctx)
                else:
                    decision = await self._decide(run, ctx)
                meta = decision.pop("_meta", {})
                reasoning = str(decision.get("reasoning") or "").strip()
                if reasoning:
                    yield self._emit(run, ev.REASONING_SUMMARY, {"text": reasoning[:1200], "step": run.steps, "provider": meta.get("provider")})
                plan = _normalize_plan(decision.get("plan"))
                if plan and plan != run.plan:
                    run.plan = plan
                    yield self._emit(run, ev.PLAN_UPDATED, {"plan": plan})

                tool_name = decision.get("tool")
                args = decision.get("args") if isinstance(decision.get("args"), dict) else {}
                if tool_name and self._is_repeat(run, str(tool_name), args):
                    # Models sometimes loop on an identical call; answer from what we have.
                    decision = await self._final_answer(run, ctx)
                    meta = decision.pop("_meta", meta)
                    tool_name = None
                if tool_name and not decision.get("final"):
                    spec = self.registry.resolve(str(tool_name), ctx)
                    if spec is not None and self._needs_approval(spec, run):
                        approval = {
                            "id": f"apr-{secrets.token_hex(6)}",
                            "call_id": f"call-{secrets.token_hex(4)}",
                            "tool": spec.name,
                            "args": args,
                            "tier": spec.tier,
                            "reason": reasoning[:500],
                        }
                        run.pending_approval = approval
                        run.status = "awaiting_approval"
                        yield self._emit(run, ev.APPROVAL_REQUESTED, approval)
                        yield self._emit(run, ev.RUN_AWAITING_APPROVAL, {"approval_id": approval["id"]})
                        return
                    async for event in self._execute_tool(run, ctx, str(tool_name), args):
                        yield event
                    self.store.save(run)
                    continue

                final = str(decision.get("final") or "").strip()
                if not final:
                    decision = await self._final_answer(run, ctx)
                    meta = decision.pop("_meta", meta)
                    final = str(decision.get("final") or "").strip()
                run.reply = final
                yield self._emit(run, ev.MESSAGE_DELTA, {"text": final})
                yield self._emit(run, ev.MESSAGE_COMPLETED, {"text": final})
                run.status = "completed"
                yield self._emit(run, ev.RUN_COMPLETED, {
                    "reply": final,
                    "steps": run.steps,
                    "tool_calls": sum(1 for e in run.events if e["type"] == ev.TOOL_CALL),
                    "provider": run.provider,
                    "model": run.model,
                    "fallback_used": bool(meta.get("fallback_used")),
                    "offline": bool(meta.get("offline")),
                })
                return
        except Exception as exc:  # the run must end with a terminal event
            run.status = "failed"
            yield self._emit(run, ev.RUN_FAILED, {"error": f"{type(exc).__name__}: {exc}"[:500]})
        finally:
            self.store.save(run)
