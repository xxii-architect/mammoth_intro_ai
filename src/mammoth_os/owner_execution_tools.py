"""Owner execution tools share the normal run-loop approval and repo policy."""
import asyncio
from collections.abc import Awaitable, Callable

from mammoth_os.agent_loop.tools import (
    TIER_EXEC,
    TIER_READ,
    TIER_WRITE,
    ToolContext,
    ToolRegistry,
    ToolSpec,
)
from mammoth_os.owner_execution import (
    PROFILES,
    ExecutionError,
    OwnerExecution,
    head_sha,
)


def register_owner_execution_tools(
    registry: ToolRegistry, service: OwnerExecution, *,
    record_execution: Callable[[dict, str], Awaitable[None]] | None = None,
    record_started: Callable[[dict, str], None] | None = None,
) -> None:
    def tool_job(job: dict) -> dict:
        # Preserve the approval identity within the run-loop's bounded result envelope.
        return {**{key: value for key, value in job.items() if key not in {"patch", "baseline", "candidate"}},
                "patch_preview": job.get("patch", "")[:4000], "patch_truncated": len(job.get("patch", "")) > 4000,
                "checks": {phase: {key: value for key, value in job[phase].items() if key not in {"log", "test_results"}}
                           for phase in ("baseline", "candidate") if phase in job},
                "evidence_endpoint": f"/api/owner-executions/{job['id']}"}

    async def status(args: dict, ctx: ToolContext) -> dict:
        if ctx.repo_root is None:
            raise ExecutionError("Select an accessible repository explicitly.", "repo_required", 403)
        return {"status": "ok", **await asyncio.to_thread(service.capabilities),
                "base_sha": await asyncio.to_thread(head_sha, ctx.repo_root)}

    async def prepare(args: dict, ctx: ToolContext) -> dict:
        try:
            if ctx.repo_root is None:
                raise ExecutionError("Select an accessible repository explicitly.", "repo_required", 403)
            job = await asyncio.to_thread(
                service.prepare, ctx.repo_root, ctx.repo_slug or ctx.repo_source_id or "selected-owner-repo",
                ctx.user_id, args["changes"], base_sha=args["base_sha"], profile=args["profile"],
            )
            return {"status": "ok", "execution": tool_job(job)}
        except ExecutionError as exc:
            return {"status": "error", "code": exc.code, "error": str(exc)}

    async def execute(args: dict, ctx: ToolContext) -> dict:
        try:
            if ctx.repo_root is None:
                raise ExecutionError("Select an accessible repository explicitly.", "repo_required", 403)
            worker = asyncio.create_task(asyncio.to_thread(
                service.execute, args["execution_id"], ctx.user_id, ctx.repo_root, args["approval_digest"],
                on_started=(lambda job: record_started(job, ctx.extras.get("run_id", ""))) if record_started else None,
            ))
            try:
                while not worker.done():
                    if callable(ctx.extras.get("cancel_requested")) and ctx.extras["cancel_requested"]():
                        service.cancel(args["execution_id"], ctx.user_id)
                    await asyncio.sleep(.1)
                job = worker.result()
            except asyncio.CancelledError:
                service.cancel(args["execution_id"], ctx.user_id)
                job = await asyncio.shield(worker)
                if record_execution:
                    await record_execution(job, ctx.extras.get("run_id", ""))
                raise
            if record_execution:
                await record_execution(job, ctx.extras.get("run_id", ""))
            return {"status": "ok" if job["status"] == "validated" else "error", "execution": tool_job(job),
                    "notice": "Checks ran in isolation. Patch is unapplied; model-written tests are not independent acceptance evidence."}
        except ExecutionError as exc:
            return {"status": "error", "code": exc.code, "error": str(exc)}

    async def apply(args: dict, ctx: ToolContext) -> dict:
        try:
            if ctx.repo_root is None:
                raise ExecutionError("Select the original repository explicitly.", "repo_required", 403)
            job = await asyncio.to_thread(service.apply, args["execution_id"], ctx.user_id,
                                          ctx.repo_root, args["approval_digest"])
            if record_execution:
                await record_execution(job, ctx.extras.get("run_id", ""))
            return {"status": "ok", "execution": tool_job(job),
                    "notice": "Changes committed on the recorded new local owner branch only. Selected checkout, remote and deployment are unchanged."}
        except ExecutionError as exc:
            return {"status": "error", "code": exc.code, "error": str(exc)}

    registry.register(ToolSpec(
        name="owner_execution_status", description="Owner-only isolated execution readiness and observed selected-repo HEAD.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        tier=TIER_READ, handler=status, admin_only=True, needs_repo=True,
    ))
    registry.register(ToolSpec(
        name="owner_execution_prepare",
        description="Prepare an owner-only isolated patch validation; never writes to the selected checkout. Requires explicit base SHA from owner_execution_status. Frozen proposal expires after 15 minutes.",
        input_schema={"type": "object", "required": ["base_sha", "profile", "changes"], "additionalProperties": False,
                      "properties": {"base_sha": {"type": "string", "minLength": 40, "maxLength": 64},
                                     "profile": {"type": "string", "enum": list(PROFILES)},
                                     "changes": {"type": "array", "minItems": 1, "maxItems": 20, "items": {
                                         "type": "object", "required": ["path", "content"], "additionalProperties": False,
                                         "properties": {"path": {"type": "string", "maxLength": 240},
                                                        "content": {"type": "string", "maxLength": 500000}}}}}},
        tier=TIER_WRITE, handler=prepare, trace_kind="proposed", admin_only=True, needs_repo=True,
    ))
    registry.register(ToolSpec(
        name="owner_execution_apply",
        description="After successful isolated validation, apply the exact tested changes to a NEW LOCAL owner branch as a commit. Requires a separate explicit user approval using execution.application.approval_digest (not the validation digest). Never switches or changes the selected checkout, merges, pushes or deploys. Application approval expires after 15 minutes. Show the user the patch and branch before requesting approval.",
        input_schema={"type": "object", "required": ["execution_id", "approval_digest"], "additionalProperties": False,
                      "properties": {"execution_id": {"type": "string", "maxLength": 32},
                                     "approval_digest": {"type": "string", "minLength": 64, "maxLength": 64}}},
        tier=TIER_EXEC, handler=apply, trace_kind="applied", admin_only=True, needs_repo=True, timeout_s=120,
    ))
    registry.register(ToolSpec(
        name="owner_execution_run",
        description="Run frozen owner proposal baseline and candidate tests in disposable Docker isolation. Explicit approval is mandatory. No host fallback, merge or push. Allow up to 150 seconds.",
        input_schema={"type": "object", "required": ["execution_id", "approval_digest"], "additionalProperties": False,
                      "properties": {"execution_id": {"type": "string", "maxLength": 32},
                                     "approval_digest": {"type": "string", "minLength": 64, "maxLength": 64}}},
        tier=TIER_EXEC, handler=execute, trace_kind="ran", admin_only=True, needs_repo=True, timeout_s=240,
    ))
