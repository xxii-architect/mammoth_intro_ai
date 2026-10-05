# Route fragment loaded by api_server._load_route_fragments().
# Not importable on its own: handlers execute in api_server globals, so keep helpers there.

@app.post("/api/mammoth/chat/stream")
async def mammoth_chat_stream(body: Dict[str, Any]):
    result = await mammoth_chat(body)

    # Persist to thread file if thread_id provided
    _thread_id = str(body.get("thread_id") or "").strip()
    if _thread_id and isinstance(result.get("chat_history"), list) and result["chat_history"]:
        try:
            _uid = _current_request_user_id()
            _msgs = result["chat_history"]
            _save_thread_messages(_uid, _thread_id, _msgs[-120:])
            _first_user = next((m.get("message", "") for m in _msgs if m.get("role") == "user"), "")
            _auto_title = (_first_user.strip()[:60] + "…") if len(_first_user.strip()) > 60 else _first_user.strip()
            _upsert_thread_index_entry(_uid, _thread_id, title=_auto_title or "Conversation", agent_id=str(body.get("agent_id") or "assistant"), message_count=len(_msgs))
        except Exception:
            pass

    async def event_stream():
        meta_payload = {k: result.get(k) for k in ("agent_id", "adapter", "model", "mode", "task_id", "trace_id", "dispatched", "runtime_status", "runtime_notice")}
        yield f"event: meta\ndata: {json.dumps(meta_payload, default=str)}\n\n"
        for step in result.get("thought_steps") or []:
            yield f"event: thought\ndata: {json.dumps(step, default=str)}\n\n"
            await asyncio.sleep(0.03)
        reply_text = str(result.get("reply") or "") or "No response produced."
        chunks = [reply_text[i:i + 48] for i in range(0, len(reply_text), 48)] or [reply_text]
        for chunk in chunks:
            yield f"event: chunk\ndata: {json.dumps({'text': chunk}, default=str)}\n\n"
            await asyncio.sleep(0.02)
        yield f"event: done\ndata: {json.dumps(result, default=str)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@app.get("/api/mammoth/chat/history")
async def get_mammoth_chat_history():
    state = _load_atlas_state()
    user_id = _current_request_user_id()
    account_id = _active_account_id(state)
    history = state.get("mammoth_chat_history") or []
    if not isinstance(history, list):
        history = []
    history = [
        item
        for item in history
        if str(item.get("user_id") or "") == user_id
        and _normalize_account_id(item.get("account_id") or "default") == account_id
    ]
    return {"status": "ok", "chat_history": history[-80:]}

@app.delete("/api/mammoth/chat/history")
async def delete_mammoth_chat_history():

    state = _load_atlas_state()
    user_id = _current_request_user_id()
    account_id = _active_account_id(state)
    history = state.get("mammoth_chat_history") or []
    if not isinstance(history, list):
        history = []
    scoped_history = [
        item
        for item in history
        if str(item.get("user_id") or "") == user_id
        and _normalize_account_id(item.get("account_id") or "default") == account_id
    ]
    deleted_messages = len(scoped_history)

    state["mammoth_chat_history"] = [
        item for item in history
        if (
            str(item.get("user_id") or "") != user_id
            or _normalize_account_id(item.get("account_id") or "default") != account_id
        )
    ]

    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)

    _append_execution_event(
        kind="mammoth_chat_history_cleared",
        summary=f"Cleared MammothOS chat history ({deleted_messages} messages)",
        detail={"deleted_messages": deleted_messages},
        user_id=user_id,
    )

    return {"status": "ok", "deleted_messages": deleted_messages}

@app.get("/api/mammoth/chat/threads")
async def list_chat_threads():
    user_id = _current_request_user_id()
    index = _load_thread_index(user_id)
    return {"status": "ok", "threads": index}

@app.post("/api/mammoth/chat/threads")
async def create_chat_thread(body: Dict[str, Any] = {}):
    user_id = _current_request_user_id()
    thread_id = f"thread-{uuid.uuid4().hex[:12]}"
    title = str(body.get("title") or "New conversation").strip()[:120]
    agent_id = str(body.get("agent_id") or "assistant").strip()
    _upsert_thread_index_entry(user_id, thread_id, title=title, agent_id=agent_id, message_count=0)
    return {"status": "ok", "thread_id": thread_id, "title": title}

@app.get("/api/mammoth/chat/threads/{thread_id}/history")
async def get_thread_history(thread_id: str):
    user_id = _current_request_user_id()
    messages = _load_thread_messages(user_id, thread_id)
    return {"status": "ok", "thread_id": thread_id, "chat_history": messages}

@app.delete("/api/mammoth/chat/threads/{thread_id}")
async def delete_chat_thread(thread_id: str):
    user_id = _current_request_user_id()
    index = _load_thread_index(user_id)
    index = [t for t in index if t.get("id") != thread_id]
    _save_thread_index(user_id, index)
    msg_path = _thread_msg_path(user_id, thread_id)
    if msg_path.exists():
        msg_path.unlink()
    return {"status": "ok", "deleted": thread_id}

@app.patch("/api/mammoth/chat/threads/{thread_id}")
async def rename_chat_thread(thread_id: str, body: Dict[str, Any] = {}):
    user_id = _current_request_user_id()
    index = _load_thread_index(user_id)
    entry = next((t for t in index if t.get("id") == thread_id), None)
    if not entry:
        return JSONResponse({"status": "error", "error": "Thread not found"}, status_code=404)
    new_title = str(body.get("title") or "").strip()[:120]
    if new_title:
        entry["title"] = new_title
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_thread_index(user_id, index)
    return {"status": "ok", "thread_id": thread_id, "title": new_title}

@app.post("/api/mammoth/files/upload")
async def upload_chat_file(file: UploadFile = File(...)):
    user_id = _current_request_user_id()
    filename = str(file.filename or "upload.txt").strip()
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
        return JSONResponse({"status": "error", "error": f"File type {ext!r} not allowed. Allowed: {sorted(_ALLOWED_UPLOAD_EXTENSIONS)}"}, status_code=400)
    content_bytes = await file.read()
    if len(content_bytes) > _MAX_UPLOAD_BYTES:
        return JSONResponse({"status": "error", "error": "File too large. Max 4MB."}, status_code=400)
    file_id = f"file-{uuid.uuid4().hex[:12]}"
    user_dir = _user_uploads_dir(user_id)
    file_path = user_dir / f"{file_id}{ext}"
    file_path.write_bytes(content_bytes)
    text_preview = _extract_text_preview(content_bytes, filename)
    now_iso = datetime.now(timezone.utc).isoformat()
    entry = {
        "file_id": file_id,
        "name": filename,
        "ext": ext,
        "size": len(content_bytes),
        "text_preview": text_preview[:8000],
        "created_at": now_iso,
        "path": str(file_path),
        "scope": "chat",
    }
    index = _load_uploads_index(user_id)
    index.insert(0, entry)
    _save_uploads_index(user_id, index[:100])
    return {
        "status": "ok",
        "file_id": file_id,
        "name": filename,
        "size": len(content_bytes),
        "text_preview": text_preview[:1200],
    }

@app.get("/api/mammoth/files")
async def list_chat_files():
    user_id = _current_request_user_id()
    index = _load_uploads_index(user_id)
    return {"status": "ok", "files": [{k: v for k, v in f.items() if k != "text_preview"} for f in index]}

@app.delete("/api/mammoth/files/{file_id}")
async def delete_chat_file(file_id: str):
    user_id = _current_request_user_id()
    index = _load_uploads_index(user_id)
    entry = next((f for f in index if f.get("file_id") == file_id), None)
    if entry:
        try:
            Path(entry["path"]).unlink(missing_ok=True)
        except Exception:
            pass
    index = [f for f in index if f.get("file_id") != file_id]
    _save_uploads_index(user_id, index)
    return {"status": "ok", "deleted": file_id}

@app.post("/api/mammoth/repo-context")
async def mammoth_repo_context(body: Dict[str, Any]):
    raw = body.get("repo_context") if isinstance(body.get("repo_context"), dict) else body
    repo_request = _normalize_repo_context_request(raw)
    if not repo_request:
        notice = _repo_context_denied_notice(raw)
        if notice:
            return JSONResponse({"status": "error", "code": "repo_access_denied", "error": notice.get("root_warning"), "repo_context": {}}, status_code=403)
        return {"status": "ok", "repo_context": {}, "notice": "No repository selected. Connect a repository to use repo context."}
    snapshot = _collect_repo_context_snapshot(repo_request)
    return {"status": "ok", "repo_context": snapshot}

@app.get("/api/mammoth/repo-sources")
async def list_repo_sources():
    return _repo_sources_payload(_current_request_user_id())

@app.post("/api/mammoth/repo-sources")
async def connect_repo_source(body: Dict[str, Any]):
    user_id = _current_request_user_id()
    if _AUTH_REQUIRED and user_id in {"", "anonymous"}:
        return JSONResponse({"status": "error", "error": "Sign in to connect repositories."}, status_code=401)
    result = await asyncio.to_thread(_REPO_POLICY.connect, user_id, body.get("repo") or body.get("slug"), is_admin=_request_is_admin())
    _append_audit_event(
        kind="repo_source_connect",
        message=f"Repository connect: {result.get('status')}",
        details={"repo": str(body.get("repo") or body.get("slug") or "")[:200], "code": result.get("code", "")},
        source="repo_access",
        actor=user_id,
    )
    return result

@app.post("/api/mammoth/repo-sources/{source_id}/sync")
async def sync_repo_source(source_id: str):
    return await asyncio.to_thread(_REPO_POLICY.sync, _current_request_user_id(), source_id)

@app.delete("/api/mammoth/repo-sources/{source_id}")
async def remove_repo_source(source_id: str):
    return await asyncio.to_thread(_REPO_POLICY.remove, _current_request_user_id(), source_id)

@app.post("/api/mammoth/repo-sources/{source_id}/propose")
async def propose_repo_source_patch(source_id: str, body: Dict[str, Any]):
    """Proposal-only write: local branch + patch in the user's sandbox clone. Never pushes."""
    user_id = _current_request_user_id()
    result = await asyncio.to_thread(
        _REPO_POLICY.propose_patch,
        user_id,
        source_id,
        body.get("changes") if isinstance(body.get("changes"), list) else [],
        title=str(body.get("title") or ""),
    )
    _append_audit_event(
        kind="repo_source_proposal",
        message=f"Repository proposal: {result.get('status')}",
        details={"source_id": source_id, "branch": result.get("branch", ""), "code": result.get("code", "")},
        source="repo_access",
        actor=user_id,
    )
    return result

@app.post("/api/mammoth/gitops/propose")
async def mammoth_gitops_propose(body: Dict[str, Any]):
    return {
        "status": "error",
        "error": "Git mutation commands are disabled in Mammoth Mind chat. Use Copilot CLI or repository workflow for commits/push/deploy.",
        "code": "mammoth_chat_read_only",
    }

@app.get("/api/mammoth/tools")
async def mammoth_agent_tools(repo: str = ""):
    """Tools and MCP servers the caller can use. Platform-rooted MCP servers are admin-only."""
    ctx, notice = _agent_tool_context({"root": repo} if repo else None)
    return {
        "status": "ok",
        "contract": EVENT_CONTRACT_VERSION,
        "tools": _AGENT_TOOLS.catalog(ctx),
        "mcp_servers": _AGENT_MCP.describe(ctx),
        "repo": {"scope": ctx.repo_scope, "slug": ctx.repo_slug} if ctx.has_repo else None,
        "repo_access_notice": notice or None,
    }

@app.post("/api/mammoth/runs")
async def mammoth_agent_run_start(body: Dict[str, Any]):
    message = str(body.get("message") or "").strip()
    if not message:
        return JSONResponse({"status": "error", "error": "message is required"}, status_code=400)
    if len(message) > 20_000:
        return JSONResponse({"status": "error", "error": "message is too long"}, status_code=413)
    ctx, notice = _agent_tool_context(body.get("repo_context"))
    if notice:
        return JSONResponse({"status": "error", **notice}, status_code=403)
    user_id = ctx.user_id
    account_id = _active_account_id(_load_atlas_state())
    approval_mode = str(body.get("approval_mode") or "tools").lower()
    surface = str(body.get("surface") or "mind").strip().lower()
    surface = surface if surface in AGENT_RUN_SURFACES else "mind"
    history_text = (
        _client_history_text(body.get("history"))
        if surface == "agent_workspace"
        else _agent_history_text(user_id, account_id)
    )
    run = AgentRun(
        id=AgentRun.new_id(),
        user_id=user_id,
        message=message,
        agent_id=str(body.get("agent_id") or "assistant").strip()[:64] or "assistant",
        request={
            "repo_context": {"root": (body.get("repo_context") or {}).get("root")} if isinstance(body.get("repo_context"), dict) else None,
            "approval_mode": approval_mode if approval_mode in {"tools", "always"} else "tools",
            "history_text": history_text,
            "thread_id": str(body.get("thread_id") or "")[:80] if surface == "mind" else "",
            "surface": surface,
            "extra_context": _agent_task_brief(body.get("task")),
        },
    )
    return _agent_run_stream(run, _AGENT_RUNNER.start(run, ctx), thread_id=run.request["thread_id"])

@app.get("/api/mammoth/runs")
async def mammoth_agent_run_list():
    return {"status": "ok", "runs": _AGENT_RUNS.list(_current_request_user_id())}

@app.get("/api/mammoth/runs/{run_id}")
async def mammoth_agent_run_get(run_id: str, after: int = 0):
    run = _AGENT_RUNS.get(run_id, _current_request_user_id())
    if run is None:
        return JSONResponse({"status": "error", "error": "Run not found."}, status_code=404)
    data = run.public()
    data["events"] = [e for e in run.events if int(e.get("seq") or 0) > max(0, int(after or 0))]
    return {"status": "ok", "run": data}

@app.post("/api/mammoth/runs/{run_id}/approval")
async def mammoth_agent_run_approval(run_id: str, body: Dict[str, Any]):
    run = _AGENT_RUNS.get(run_id, _current_request_user_id())
    if run is None:
        return JSONResponse({"status": "error", "error": "Run not found."}, status_code=404)
    decision = str(body.get("decision") or "").lower()
    if decision not in {"approve", "reject"}:
        return JSONResponse({"status": "error", "error": "decision must be approve or reject"}, status_code=400)
    ctx, notice = _agent_tool_context(run.request.get("repo_context"))
    if notice:
        return JSONResponse({"status": "error", **notice}, status_code=403)
    _append_audit_event(
        kind="agent_run_approval",
        message=f"Agent run tool {decision}d",
        details={"run_id": run.id, "approval_id": str(body.get("approval_id") or ""), "tool": (run.pending_approval or {}).get("tool")},
        source="mammoth_mind",
        actor=ctx.user_id,
    )
    events_iter = _AGENT_RUNNER.resume(
        run, ctx,
        approval_id=str(body.get("approval_id") or ""),
        approved=decision == "approve",
        note=str(body.get("note") or ""),
    )
    return _agent_run_stream(run, events_iter, thread_id=str(run.request.get("thread_id") or ""))

@app.post("/api/mammoth/runs/{run_id}/cancel")
async def mammoth_agent_run_cancel(run_id: str):
    run = _AGENT_RUNS.get(run_id, _current_request_user_id())
    if run is None:
        return JSONResponse({"status": "error", "error": "Run not found."}, status_code=404)
    if run.status == "awaiting_approval":
        run.pending_approval = None
        run.status = "cancelled"
        _AGENT_RUNS.save(run)
    else:
        _AGENT_RUNNER.cancel(run)
    return {"status": "ok", "run_id": run.id, "run_status": run.status, "cancel_requested": True}

@app.post("/api/mammoth/chat")
async def mammoth_chat(body: Dict[str, Any]):
    message = str(body.get("message", "")).strip()
    if not message:
        return {"status": "error", "error": "message is required"}

    # Inject attached file contents as additional context
    attached_file_ids = body.get("attached_file_ids") or []
    if attached_file_ids and isinstance(attached_file_ids, list):
        _uid_for_files = _current_request_user_id()
        _file_index = _load_uploads_index(_uid_for_files)
        _file_texts = []
        for _fid in attached_file_ids[:4]:
            _entry = next((f for f in _file_index if f.get("file_id") == _fid), None)
            if _entry and _entry.get("text_preview"):
                _file_texts.append(f"--- Attached file: {_entry['name']} ---\n{_entry['text_preview'][:4000]}")
        if _file_texts:
            message = message + "\n\n[ATTACHED FILES]\n" + "\n\n".join(_file_texts)

    trace_id = str(body.get("trace_id") or new_trace_id("chat"))
    initial_repo_request = _normalize_repo_context_request(body.get("repo_context"))
    initial_repo_context = _collect_repo_context_snapshot(initial_repo_request) if initial_repo_request else {}
    repo_access_notice = {} if initial_repo_request else _repo_context_denied_notice(body.get("repo_context"))
    repo_evidence_items = _repo_context_evidence_items(initial_repo_context)
    slash = _parse_mammoth_chat_command(message)
    if slash and slash.get("kind") == "plan":
        plan_result = await plan_execute({
            "objective": slash["objective"],
            "approval_mode": bool(body.get("approval_mode", True)),
            "stop_on_failure": bool(body.get("stop_on_failure", True)),
            "plan_profile": body.get("plan_profile") or "atlas",
            "coding_intent": body.get("coding_intent") or "patch_existing",
        })
        progress = plan_result.get("progress") if isinstance(plan_result.get("progress"), dict) else {}
        summary = (
            f"Plan queued: {plan_result.get('objective') or slash['objective']}\n"
            f"Status: {plan_result.get('plan_status') or 'active'} • "
            f"{progress.get('completed') or 0}/{progress.get('total') or 0} complete"
        )
        return {
            "status": "ok",
            "reply": summary,
            "agent_id": "orchestrator",
            "adapter": "plan-execute",
            "model": "plan-execute",
            "mode": "chat",
            "task_id": plan_result.get("plan_id") or "",
            "dispatched": True,
            "trace_id": trace_id,
            "thought_steps": [{
                "ts": _ts(),
                "label": "Plan command parsed",
                "detail": f"objective={slash['objective']}",
                "status": "info",
            }],
            "runtime_status": _runtime_status_snapshot(),
            "runtime_notice": None if _runtime_status_snapshot().get("state") == "ready" else build_runtime_notice(_runtime_status_snapshot(), trace_id=trace_id, agent_id="mammoth_chat", context="chat", provider="plan-execute"),
        }
    if slash and slash.get("kind") == "agent":
        if not slash.get("message"):
            return {"status": "error", "error": "Usage: /agent <agent_id> <message>"}
        body = {**body, "agent_id": slash["agent_id"], "message": slash["message"]}
        return await mammoth_chat(body)
    if slash and slash.get("kind") == "guide":
        body = {**body, "agent_id": "mammoth_guide", "message": str(slash.get("message") or "").strip()}
        return await mammoth_chat(body)
    if slash and slash.get("kind") in {"web", "research"}:
        command_result = _run_internet_command(slash)
        reply = str(command_result.get("reply") or "No response produced.")
        state = _load_atlas_state()
        user_id = _current_request_user_id()
        account_id = _active_account_id(state)
        all_history = state.get("mammoth_chat_history") or []
        if not isinstance(all_history, list):
            all_history = []
        history = [
            item
            for item in all_history
            if str(item.get("user_id") or "") == user_id
            and _normalize_account_id(item.get("account_id") or "default") == account_id
        ]

        internet_evidence = [item for item in [command_result.get("evidence"), *repo_evidence_items] if isinstance(item, dict)]
        internet_confidence = _derive_chat_confidence(
            runtime_status=_runtime_status_snapshot(),
            evidence_items=internet_evidence,
            reply=reply,
            base=0.78 if command_result.get("status") == "ok" else 0.46,
        )
        internet_trust = _build_chat_trust_metadata(
            provider="internet-tool",
            confidence=internet_confidence,
            evidence_items=internet_evidence,
            content=reply,
            response_type="research" if slash.get("kind") == "research" else "general",
        )
        history.append({
            "role": "user",
            "message": message,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent_id": "assistant",
            "mode": "chat",
            "page": "",
            "user_id": user_id,
            "account_id": account_id,
        })
        history.append({
            "role": "assistant",
            "message": reply,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "agent_id": "assistant",
            "mode": "chat",
            "adapter": "internet-tool",
            "model": "internet-tool",
            "thought_steps": [{
                "ts": _ts(),
                "label": "Internet command completed",
                "detail": f"kind={slash.get('kind')}",
                "status": "success" if command_result.get("status") == "ok" else "warning",
            }],
            "evidence_items": internet_evidence,
            "confidence": internet_confidence,
            "trust_metadata": internet_trust,
            "orchestrated": False,
            "runtime_status": _runtime_status_snapshot(),
            "runtime_notice": None,
            "user_id": user_id,
            "account_id": account_id,
        })

        other_history = [
            item
            for item in all_history
            if (
                str(item.get("user_id") or "") != user_id
                or _normalize_account_id(item.get("account_id") or "default") != account_id
            )
        ]
        scoped_history = history[-80:]
        state["mammoth_chat_history"] = (other_history + scoped_history)[-400:]
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_atlas_state(state)
        return {
            "status": "ok" if command_result.get("status") == "ok" else "error",
            "reply": reply,
            "chat_history": scoped_history,
            "thought_steps": [{
                "ts": _ts(),
                "label": "Internet command completed",
                "detail": f"kind={slash.get('kind')}",
                "status": "success" if command_result.get("status") == "ok" else "warning",

            }],
            "agent_id": "assistant",
            "adapter": "internet-tool",
            "model": "internet-tool",
            "mode": "chat",
            "task_id": "",
            "dispatched": False,
            "evidence_items": internet_evidence,
            "orchestrated": False,
            "runtime_status": _runtime_status_snapshot(),
            "runtime_notice": None,
            "trace_id": trace_id,
            "confidence": internet_confidence,
            "trust_metadata": internet_trust,
        }
    if slash and slash.get("kind") == "gitops":
        return {
            "status": "error",
            "reply": "Git mutation commands are disabled in Mammoth Mind chat. Use Copilot CLI or repository workflow for commits/push/deploy.",
            "agent_id": "assistant",
            "adapter": "policy-guard",
            "model": "policy-guard",
            "mode": "chat",
            "task_id": "",
            "dispatched": False,
            "trace_id": trace_id,
        }
    if slash and slash.get("kind") == "error":
        return {"status": "error", "error": slash["error"]}

    state = _load_atlas_state()
    page_context = _normalize_page_context(body.get("page_context"), body.get("page_snapshot"))
    repo_context = initial_repo_context
    agent_id = str(body.get("agent_id") or "assistant").strip() or "assistant"
    if not repo_context and agent_id == "mammoth_guide":
        repo_context = _collect_public_docs_context(message)
        repo_evidence_items = _repo_context_evidence_items(repo_context)
    mode = str(body.get("mode") or "chat").strip().lower() or "chat"
    adapter = str(body.get("adapter", "")).strip()
    model = str(body.get("model", "")).strip()
    temperature = float(body.get("temperature", 0.3))
    user_id = _current_request_user_id()
    account_id = _active_account_id(state)
    all_history = state.get("mammoth_chat_history") or []
    if not isinstance(all_history, list):
        all_history = []
    history = [
        item
        for item in all_history
        if str(item.get("user_id") or "") == user_id
        and _normalize_account_id(item.get("account_id") or "default") == account_id
    ]
    runtime_status = _runtime_status_snapshot()
    web_context = body.get("web")

    user_entry = {
        "role": "user",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "mode": mode,
        "page": str(page_context.get("current_page") or ""),
        "user_id": user_id,
        "account_id": account_id,
    }
    history.append(user_entry)

    thought_steps: List[Dict[str, Any]] = [
        {"ts": _ts(), "label": "Hearing hoofbeats", "detail": f"agent={agent_id} mode={mode}", "status": "info"},
        {"ts": _ts(), "label": "Priming mammoth cores", "detail": "Spinning up MammothOS reasoning lanes", "status": "info"},
    ]

    reply = ""
    active_model = ""
    active_adapter = ""
    task_id = ""
    dispatched = False
    evidence_items: List[Dict[str, Any]] = []
    guide_steps_result = None
    guide_branch_result = None
    fanout_agents = body.get("fanout_agents") if isinstance(body.get("fanout_agents"), list) else []
    orchestrate = bool(body.get("orchestrate") or body.get("multi_agent") or body.get("fanout")) or len(fanout_agents) > 1 or agent_id in {"herd", "orchestrator", "multi_agent"}

    async def _run_native_assistant() -> Dict[str, Any]:
        from mammoth_os.llm_client import get_llm_client

        convo_window = history[-8:]
        convo_text = "\n".join(
            f"{item.get('role', 'unknown')}: {str(item.get('message', ''))[:500]}"
            for item in convo_window
            if isinstance(item, dict)
        )
        prompt = (
            "You are Mammoth Mind, a thoughtful and approachable collaborator inside MammothOS. "
            "Be warm, clear, practical, and natural—not a scripted helpdesk or a report generator. "
            "Avoid branded quips, canned openings, and filler.\n\n"
            "Match the response to the request: answer simple questions and confirmations briefly and conversationally; "
            "for multi-part, technical, consequential, or explicitly thorough requests, give a complete, well-structured "
            "answer with useful headings, steps, bullets, or code only where they help. Do not force a template onto a simple reply. "
            "Lead with the direct answer, then include necessary explanation, caveats, and actionable next steps. "
            "Share concise rationale and evidence, never private chain-of-thought. If a real ambiguity blocks a good answer, "
            "ask one focused follow-up.\n\n"
            f"Observed page context: {json.dumps(page_context, default=str)[:1400]}\n\n"
            f"Observed repo context: {json.dumps(repo_context, default=str)[:2200]}\n\n"
            f"Observed web context: {json.dumps(web_context, default=str)}\n\n"
            f"Recent conversation:\n{convo_text}\n\n"
            f"User message: {message}"
        )
        cfg: Dict[str, Any] = {}
        if adapter:
            cfg["adapter"] = adapter
        if model:
            cfg["model"] = model
        thought_steps.append({"ts": _ts(), "label": "Consulting the herd", "detail": "Running native MammothOS assistant response", "status": "info"})
        client = get_llm_client(config=cfg)
        assistant_reply = await client.generate(prompt, temperature=temperature)
        requested_adapter = str((cfg.get("adapter") or os.environ.get("MAMMOTH_LLM_ADAPTER") or "").strip() or "auto")
        client_meta = _runtime_metadata_from_client(client, requested_adapter=requested_adapter)
        assistant_adapter = str(client_meta.get("active_adapter") or requested_adapter or "auto")
        assistant_model = str(getattr(client, "model", model or "unknown"))
        thought_steps.append({"ts": _ts(), "label": "Tusks charged", "detail": f"adapter={assistant_adapter} model={assistant_model}", "status": "success"})
        runtime_status = _runtime_status_snapshot()
        runtime_status["effective_adapter"] = assistant_adapter
        if client_meta.get("fallback_used"):
            runtime_status["state"] = "degraded"
            runtime_status["degraded_mode"] = True
            runtime_status["fallback_used"] = True
            runtime_status["primary_provider"] = client_meta.get("primary_provider")
            runtime_status["used_provider"] = client_meta.get("used_provider")
            if client_meta.get("fallback_reason"):
                runtime_status["fallback_reason"] = client_meta.get("fallback_reason")
            if client_meta.get("fallback_error_type"):
                runtime_status["fallback_error_type"] = client_meta.get("fallback_error_type")
        _remember_runtime_status(runtime_status)
        return {
            "agent_id": "assistant",
            "adapter": assistant_adapter,
            "model": assistant_model,
            "reply": assistant_reply,
            "thought_steps": [],
            "evidence": {"agent_id": "assistant", "summary": _render_evidence_summary(assistant_reply), "source": "native-chat"},
            "task_id": "",
            "dispatched": False,
            "runtime_status": runtime_status,
            "runtime_notice": None if runtime_status.get("state") == "ready" else build_runtime_notice(runtime_status, trace_id=trace_id, agent_id="assistant", context="assistant", provider=assistant_adapter),
        }

    async def _run_lane(lane_agent: str) -> Dict[str, Any]:
        if lane_agent in {"assistant", "mammoth_assistant", "atlas_assistant"}:
            return await _run_native_assistant()

        lane_intent = str(body.get("intent") or "").strip()
        lane_coding_intent = _normalize_coding_intent(body.get("coding_intent"))
        if not lane_intent:
            if lane_agent == "coding_agent":
                lane_intent = lane_coding_intent or "generate_code"
            elif lane_agent == "reasoning_agent":
                lane_intent = "reason"
            elif lane_agent == "tutor_agent":
                lane_intent = "lesson_coaching"
            elif lane_agent == "shell_agent":
                lane_intent = "shell"
            elif lane_agent == "mammoth_guide":
                lane_intent = "guide_platform"
            else:
                lane_intent = "summarize"
        lane_payload = {
            "prompt": message,
            "task": message,
            "coding_intent": lane_coding_intent or _normalize_coding_intent(lane_intent),
            "files": body.get("files") if isinstance(body.get("files"), list) else [],
            "target": str(body.get("target") or "").strip(),
            "context": {
                "source": "mammoth.chat",
                "page_context": page_context,
                "repo_context": repo_context,
                "conversation_mode": mode,
                "agent_id": lane_agent,
                "orchestrated": True,
            },
        }
        if lane_agent == "mammoth_guide":
            lane_payload["message"] = message
            lane_payload["repo_context"] = repo_context
        thought_steps.append({"ts": _ts(), "label": "Routing through the herd", "detail": f"intent={lane_intent} agent={lane_agent}", "status": "info"})
        lane_run = await run_agent({
            "agent_id": lane_agent,
            "intent": lane_intent,
            "payload": lane_payload,
            "temperature": temperature,
            "approval_mode": bool(body.get("approval_mode", False)),
        })
        lane_result = lane_run.get("result")
        lane_output = lane_result.get("output") if isinstance(lane_result, dict) and isinstance(lane_result.get("output"), dict) else None
        lane_reply = _render_chat_result(lane_result)
        lane_thoughts = list(lane_run.get("thought_steps") or [])
        lane_thoughts.append({"ts": _ts(), "label": "Lane complete", "detail": f"task_id={lane_run.get('task_id') or 'n/a'}", "status": "success"})
        evidence = {
            "agent_id": lane_agent,
            "intent": lane_intent,
            "summary": _render_evidence_summary(lane_result),
            "task_id": lane_run.get("task_id") or "",
            "status": lane_run.get("status") or "ok",
            "source": "agent-runtime",
        }
        if isinstance(lane_result, dict):
            for key in ("files", "source_files", "references", "evidence", "diff"):
                if lane_result.get(key):
                    evidence[key] = lane_result.get(key)
        if isinstance(lane_output, dict):
            for key in ("files", "source_files", "references", "evidence", "diff"):
                if lane_output.get(key) and key not in evidence:
                    evidence[key] = lane_output.get(key)
        # Preserve structured guide steps if the guide agent returned them
        lane_guide_steps = None
        lane_guide_branch = "main"
        if isinstance(lane_result, dict) and isinstance(lane_result.get("guide_steps"), list) and lane_result.get("guide_steps"):
            lane_guide_steps = lane_result["guide_steps"]
            lane_guide_branch = str(lane_result.get("guide_branch") or lane_result.get("branch") or "main")
        elif isinstance(lane_output, dict) and isinstance(lane_output.get("guide_steps"), list) and lane_output.get("guide_steps"):
            lane_guide_steps = lane_output["guide_steps"]
            lane_guide_branch = str(lane_output.get("guide_branch") or lane_output.get("branch") or "main")
        elif isinstance(lane_run.get("result"), dict) and isinstance(lane_run["result"].get("guide_steps"), list) and lane_run["result"].get("guide_steps"):
            lane_guide_steps = lane_run["result"]["guide_steps"]
            lane_guide_branch = str(lane_run["result"].get("guide_branch") or lane_run["result"].get("branch") or "main")

        lane_return: Dict[str, Any] = {
            "agent_id": lane_agent,
            "adapter": (
                lane_result.get("adapter") if isinstance(lane_result, dict) and lane_result.get("adapter")
                else (lane_output.get("adapter") if isinstance(lane_output, dict) and lane_output.get("adapter") else "agent-runtime")
            ),
            "model": str(lane_run.get("agent_id") or lane_agent),
            "reply": lane_reply,
            "task_id": lane_run.get("task_id") or "",
            "dispatched": True,
            "thought_steps": lane_thoughts,
            "evidence": evidence,
            "raw": lane_run,
        }
        if lane_guide_steps:
            lane_return["guide_steps"] = lane_guide_steps
            lane_return["guide_branch"] = lane_guide_branch
        return lane_return

    try:
        if orchestrate:
            selected_agents = [str(item).strip() for item in fanout_agents if str(item).strip()] if fanout_agents else []
            if not selected_agents:
                selected_agents = ["assistant", "reasoning_agent", "coding_agent"]
            if agent_id not in selected_agents and agent_id not in {"herd", "orchestrator", "multi_agent"}:
                selected_agents.insert(0, agent_id)
            seen_agents: List[str] = []
            for lane in selected_agents:
                if lane not in seen_agents:
                    seen_agents.append(lane)
            thought_steps.append({"ts": _ts(), "label": "Splitting the herd", "detail": f"lanes={', '.join(seen_agents)}", "status": "info"})
            lane_results = await asyncio.gather(*[_run_lane(lane) for lane in seen_agents])
            thought_steps.append({"ts": _ts(), "label": "Merging the herd", "detail": f"lanes_completed={len(lane_results)}", "status": "info"})
            assistant_lane = next((lane for lane in lane_results if lane.get("agent_id") == "assistant"), lane_results[0])
            active_adapter = assistant_lane.get("adapter") or "agent-runtime"
            active_model = assistant_lane.get("model") or seen_agents[0]
            task_id = assistant_lane.get("task_id") or task_id
            reply_parts = [assistant_lane.get("reply") or "No response produced."]
            for lane in lane_results:
                evidence = lane.get("evidence") or {}
                evidence_items.append({
                    "agent_id": lane.get("agent_id"),
                    "intent": evidence.get("intent") or ("chat" if lane.get("agent_id") == "assistant" else "unknown"),
                    "summary": evidence.get("summary") or lane.get("reply") or "No summary.",
                    "task_id": lane.get("task_id") or "",
                    "status": evidence.get("status") or "ok",
                    "source": evidence.get("source") or ("native-chat" if lane.get("agent_id") == "assistant" else "agent-runtime"),
                })
                if lane.get("agent_id") != "assistant" and lane.get("reply"):
                    reply_parts.append(f"\n\n**{lane.get('agent_id').replace('_', ' ').title()}**\n{lane.get('reply')}")
                thought_steps.extend(lane.get("thought_steps") or [])
            reply = "\n\n".join(reply_parts)
            thought_steps.append({"ts": _ts(), "label": "Herd merged", "detail": f"evidence_items={len(evidence_items)}", "status": "success"})
        else:
            lane_result = await _run_lane(agent_id)
            dispatched = bool(lane_result.get("dispatched"))
            active_adapter = lane_result.get("adapter") or active_adapter
            active_model = lane_result.get("model") or active_model
            task_id = lane_result.get("task_id") or task_id
            reply = lane_result.get("reply") or "No response produced."
            thought_steps.extend(lane_result.get("thought_steps") or [])
            if lane_result.get("evidence"):
                evidence_items.append(lane_result["evidence"])
            if lane_result.get("agent_id") != "assistant":
                thought_steps.append({"ts": _ts(), "label": "Packaged response", "detail": f"task_id={task_id or 'n/a'}", "status": "success"})
            # Capture structured guide steps from guide agent
            if lane_result.get("guide_steps"):
                guide_steps_result = lane_result["guide_steps"]
                guide_branch_result = lane_result.get("guide_branch") or "main"
            else:
                guide_steps_result = None
                guide_branch_result = None
    except Exception as exc:
        runtime_status = _runtime_status_snapshot()
        safe_error = _sanitize_runtime_error_message(exc)
        runtime_status["error_type"] = type(exc).__name__
        runtime_status["safe_error"] = safe_error
        _remember_runtime_status(runtime_status)
        reply = (
            "I hit a MammothOS chat routing problem. "
            "The good news is the shell is still up; the routing stack just needs better wiring. "
            "MammothOS switched to a safe fallback path. "
            f"{runtime_status.get('recommendation')}"
        )
        active_adapter = active_adapter or "fallback-local"
        active_model = active_model or "fallback-local"
        thought_steps.append({"ts": _ts(), "label": "Hamster escaped", "detail": safe_error, "status": "error"})

    for item in repo_evidence_items:
        if len(evidence_items) >= 5:
            break
        evidence_items.append(item)

    reply_response_type = "research" if str(agent_id or "").strip() == "research_agent" else "general"
    response_confidence = _derive_chat_confidence(
        runtime_status=runtime_status,
        evidence_items=evidence_items,
        reply=reply,
        base=0.72,
    )
    response_trust_metadata = _build_chat_trust_metadata(
        provider=active_adapter or "unknown",
        confidence=response_confidence,
        evidence_items=evidence_items,
        content=reply,
        response_type=reply_response_type,
    )

    assistant_entry = {
        "role": "assistant",
        "message": reply,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "agent_id": agent_id,
        "mode": mode,
        "adapter": active_adapter,
        "model": active_model,
        "thought_steps": thought_steps[-12:],
        "task_id": task_id,
        "dispatched": dispatched,
        "evidence_items": evidence_items,
        "confidence": response_confidence,
        "trust_metadata": response_trust_metadata,
        "orchestrated": orchestrate,
        "runtime_status": runtime_status,
        "runtime_notice": None if runtime_status.get("state") == "ready" else build_runtime_notice(runtime_status, trace_id=trace_id, agent_id=agent_id, context=mode, provider=active_adapter),
        "user_id": user_id,
        "account_id": account_id,
    }
    if guide_steps_result:
        assistant_entry["guide_steps"] = guide_steps_result
        assistant_entry["guide_branch"] = guide_branch_result or "main"
    history.append(assistant_entry)
    other_history = [
        item
        for item in all_history
        if (
            str(item.get("user_id") or "") != user_id
            or _normalize_account_id(item.get("account_id") or "default") != account_id
        )
    ]
    state["mammoth_chat_history"] = (other_history + history)[-400:]
    scoped_history = history[-80:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    _append_execution_event(
        kind="mammoth_chat",
        summary=f"Chat [{mode}] via {active_adapter or 'unknown'}: {message[:80]}{'…' if len(message)>80 else ''}",
        detail={"agent_id": agent_id, "mode": mode, "adapter": active_adapter, "task_id": task_id},
        user_id=user_id,
    )
    final_response: Dict[str, Any] = {
        "status": "ok",
        "reply": reply,
        "chat_history": scoped_history,
        "thought_steps": thought_steps[-12:],
        "repo_scope": str(repo_context.get("scope") or "none") if isinstance(repo_context, dict) else "none",
        "repo_access_notice": repo_access_notice or None,
        "agent_id": agent_id,
        "adapter": active_adapter,
        "model": active_model,
        "mode": mode,
        "task_id": task_id,
        "dispatched": dispatched,
        "evidence_items": evidence_items,
        "confidence": response_confidence,
        "trust_metadata": response_trust_metadata,
        "orchestrated": orchestrate,
        "runtime_status": runtime_status,
        "runtime_notice": None if runtime_status.get("state") == "ready" else build_runtime_notice(runtime_status, trace_id=trace_id, agent_id=agent_id, context=mode, provider=active_adapter),
        "trace_id": trace_id,
    }
    if guide_steps_result:
        final_response["guide_steps"] = guide_steps_result
        final_response["guide_branch"] = guide_branch_result or "main"
    return final_response

