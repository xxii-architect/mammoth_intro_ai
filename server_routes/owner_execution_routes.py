# Route fragment: owner authorization is rechecked on every request.

@app.exception_handler(ExecutionError)
async def owner_execution_error(request: Request, exc: ExecutionError):
    logger.warning("Owner execution request rejected at %s: %s", request.url.path, exc)
    return JSONResponse({"status": "error", "code": exc.code, "error": str(exc)}, status_code=exc.status)


@app.get("/api/owner-executions/capabilities")
async def owner_execution_capabilities(repo: str = ""):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    ctx, notice = _agent_tool_context({"root": repo})
    result = await asyncio.to_thread(_OWNER_EXECUTION.capabilities)
    if notice:
        return JSONResponse({"status": "error", "error": notice["message"]}, status_code=403)
    if ctx.has_repo:
        from mammoth_os.owner_execution import head_sha
        result["base_sha"] = await asyncio.to_thread(head_sha, ctx.repo_root)
    return {"status": "ok", **result}


@app.post("/api/owner-executions")
async def prepare_owner_execution(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    ctx, notice = _agent_tool_context(body.get("repo_context"))
    if notice or not ctx.has_repo:
        raise ExecutionError("Select an accessible repository explicitly.", "repo_required", 403)
    job = await asyncio.to_thread(
        _OWNER_EXECUTION.prepare, ctx.repo_root, ctx.repo_slug or ctx.repo_source_id or "selected-owner-repo",
        ctx.user_id, body.get("changes"), base_sha=body.get("base_sha"), profile=body.get("profile"),
    )
    _append_activity("Owner isolated proposal prepared", agent_id="coding_agent", task_id=job["id"], kind="approval_requested",
                     details={"repo": job["repo"], "base_sha": job["base_sha"], "approval_digest": job["approval_digest"]})
    return {"status": "ok", "execution": job}


@app.get("/api/owner-executions/{execution_id}")
async def get_owner_execution(execution_id: str):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return {"status": "ok", "execution": _OWNER_EXECUTION.get(execution_id, _current_request_user_id())}


@app.post("/api/owner-executions/{execution_id}/approve")
async def approve_owner_execution(execution_id: str, body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    ctx, notice = _agent_tool_context(body.get("repo_context"))
    if notice or not ctx.has_repo:
        raise ExecutionError("Select the original accessible repository explicitly.", "repo_required", 403)
    job = await asyncio.to_thread(_OWNER_EXECUTION.execute, execution_id, ctx.user_id, ctx.repo_root,
                                 str(body.get("approval_digest") or ""), on_started=_record_owner_execution_started)
    await _record_owner_execution(job)
    return {"status": "ok", "execution": job}


@app.post("/api/owner-executions/{execution_id}/cancel")
async def cancel_owner_execution(execution_id: str):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    job = _OWNER_EXECUTION.cancel(execution_id, _current_request_user_id())
    if job["status"] == "cancelled":
        _append_activity("Owner isolated validation cancellation requested", agent_id="coding_agent", task_id=job["id"], kind="task_cancelled")
    return {"status": "ok", "execution": job}


@app.post("/api/owner-executions/{execution_id}/apply")
async def apply_owner_execution(execution_id: str, body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    ctx, notice = _agent_tool_context(body.get("repo_context"))
    if notice or not ctx.has_repo:
        raise ExecutionError("Select the original accessible repository explicitly.", "repo_required", 403)
    job = await asyncio.to_thread(_OWNER_EXECUTION.apply, execution_id, ctx.user_id, ctx.repo_root,
                                 str(body.get("approval_digest") or ""))
    await _record_owner_execution(job)
    return {"status": "ok", "execution": job}
