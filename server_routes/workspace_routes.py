# Route fragment loaded by api_server._load_route_fragments().
# Not importable on its own: handlers execute in api_server globals, so keep helpers there.

@app.get("/api/workspace/artifacts")
async def list_workspace_artifacts():
    from mammoth_os.workspace_artifacts import ARTIFACT_CATEGORIES

    state = _load_atlas_state()
    artifacts = _normalize_workspace_artifact_collection(state.get("workspace_artifacts"))
    if artifacts != state.get("workspace_artifacts"):
        state["workspace_artifacts"] = artifacts
        _save_atlas_state(state)
    return {"status": "ok", "artifacts": artifacts, "categories": ARTIFACT_CATEGORIES}

@app.post("/api/workspace/artifacts")
async def create_workspace_artifact(body: Dict[str, Any]):
    artifact = _normalize_workspace_artifact_record(body)
    if not artifact:
        return JSONResponse(
            {"status": "error", "error": "artifact body is required and must include non-empty text content."},
            status_code=400,
        )
    state = _load_atlas_state()
    artifacts = _normalize_workspace_artifact_collection(state.get("workspace_artifacts"))
    artifacts = [item for item in artifacts if item.get("id") != artifact["id"]]
    artifacts.insert(0, artifact)
    state["workspace_artifacts"] = artifacts[:120]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    return {"status": "ok", "artifact": artifact}

@app.delete("/api/workspace/artifacts/{artifact_id}")
async def delete_workspace_artifact(artifact_id: str):
    state = _load_atlas_state()
    artifacts = _normalize_workspace_artifact_collection(state.get("workspace_artifacts"))
    remaining = [item for item in artifacts if str(item.get("id") or "") != str(artifact_id or "")]
    deleted = len(remaining) != len(artifacts)
    state["workspace_artifacts"] = remaining
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    return {"status": "ok", "deleted": artifact_id, "removed": deleted}

@app.delete("/api/workspace/artifacts")
async def clear_workspace_artifacts():
    state = _load_atlas_state()
    count = len(_normalize_workspace_artifact_collection(state.get("workspace_artifacts")))
    state["workspace_artifacts"] = []
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    return {"status": "ok", "cleared": count}

@app.get("/api/workspace/run-history")
async def list_workspace_run_history():
    state = _load_atlas_state()
    entries = _normalize_agent_run_history_collection(state.get("agent_run_history"))
    if entries != state.get("agent_run_history"):
        state["agent_run_history"] = entries
        _save_atlas_state(state)
    return {"status": "ok", "entries": entries}

@app.post("/api/workspace/run-history")
async def upsert_workspace_run_history_entry(body: Dict[str, Any]):
    entry = _normalize_agent_run_history_entry(body)
    if not entry:
        return JSONResponse(
            {"status": "error", "error": "run history entry requires a non-empty prompt."},
            status_code=400,
        )
    state = _load_atlas_state()
    entries = _normalize_agent_run_history_collection(state.get("agent_run_history"))
    entries = [item for item in entries if item.get("id") != entry["id"]]
    entries.insert(0, entry)
    state["agent_run_history"] = entries[:160]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    return {"status": "ok", "entry": entry}

@app.delete("/api/workspace/run-history/{entry_id}")
async def delete_workspace_run_history_entry(entry_id: str):
    state = _load_atlas_state()
    entries = _normalize_agent_run_history_collection(state.get("agent_run_history"))
    remaining = [item for item in entries if str(item.get("id") or "") != str(entry_id or "")]
    deleted = len(remaining) != len(entries)
    state["agent_run_history"] = remaining
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    return {"status": "ok", "deleted": entry_id, "removed": deleted}

@app.delete("/api/workspace/run-history")
async def clear_workspace_run_history():
    state = _load_atlas_state()
    count = len(_normalize_agent_run_history_collection(state.get("agent_run_history")))
    state["agent_run_history"] = []
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    return {"status": "ok", "cleared": count}

@app.get("/api/notes")
async def get_notes():
    blocked = _require_workspace_tier_api("pro")
    if blocked is not None:
        return blocked
    scope_user_id = _current_request_user_id()
    state = _load_atlas_state()
    scope_account_id = _active_account_id(state)
    notes = _read_json(NOTES_FILE, default=[])
    if not isinstance(notes, list):
        return []

    normalized: List[Dict[str, Any]] = []
    for raw in reversed(notes):
        note = _normalize_note_record(raw)
        if note and note.get("user_id") == scope_user_id and note.get("account_id") == scope_account_id:
            normalized.append(note)
    return normalized

@app.post("/api/notes")
async def upsert_note(body: Dict[str, Any]):
    blocked = _require_workspace_tier_api("pro")
    if blocked is not None:
        return blocked
    scope_user_id = _current_request_user_id()
    state = _load_atlas_state()
    scope_account_id = _active_account_id(state)
    notes = _read_json(NOTES_FILE, default=[])
    if not isinstance(notes, list):
        notes = []
    note_id = str(body.get("id") or "").strip()
    now = datetime.now(timezone.utc).isoformat()
    if note_id:
        for i, n in enumerate(notes):
            if n.get("id") == note_id:
                if str(n.get("user_id") or "") != scope_user_id or _normalize_account_id(n.get("account_id") or "default") != scope_account_id:
                    continue
                created_at = str(n.get("created_at") or n.get("updated_at") or now)
                normalized = _normalize_note_record(
                    {
                        **n,
                        **body,
                        "id": note_id,
                        "created_at": created_at,
                        "updated_at": now,
                        "user_id": scope_user_id,
                        "account_id": scope_account_id,
                    },
                    now=now,
                )
                if normalized is None:
                    return {"status": "error", "error": "note payload is invalid"}
                notes[i] = normalized
                _write_json(NOTES_FILE, notes)
                return normalized
    # create new
    new_note = _normalize_note_record({
        "id": str(uuid.uuid4()),
        "title": body.get("title"),
        "body": body.get("body"),
        "content": body.get("content"),
        "created_at": now,
        "updated_at": now,
        "agent_id": body.get("agent_id"),
        "source": body.get("source"),
        "type": body.get("type"),
        "priority": body.get("priority"),
        "subsystem": body.get("subsystem"),
        "metadata": body.get("metadata"),
        "user_id": scope_user_id,
        "account_id": scope_account_id,
    }, now=now)
    if new_note is None:
        return {"status": "error", "error": "note payload is invalid"}
    notes.append(new_note)
    _write_json(NOTES_FILE, notes)
    return new_note

@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: str):
    blocked = _require_workspace_tier_api("pro")
    if blocked is not None:
        return blocked
    scope_user_id = _current_request_user_id()
    state = _load_atlas_state()
    scope_account_id = _active_account_id(state)
    notes = _read_json(NOTES_FILE)
    notes = [
        n for n in notes
        if str(n.get("id") or "") != note_id
        or str(n.get("user_id") or "") != scope_user_id
        or _normalize_account_id(n.get("account_id") or "default") != scope_account_id
    ]
    _write_json(NOTES_FILE, notes)
    return {"status": "ok"}

@app.get("/api/beta-feedback")
async def get_beta_feedback():
    entries = _read_json(BETA_FEEDBACK_FILE, default=[])
    if not isinstance(entries, list):
        entries = []
    normalized: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()
    for raw in entries:
        record = _normalize_beta_feedback_record(raw, now=now)
        if record:
            normalized.append(record)

    is_admin = _request_is_admin()
    if _AUTH_REQUIRED and not is_admin:
        requester_id = str(_REQUEST_USER_ID.get() or "").strip()
        requester_email = str(_REQUEST_USER_EMAIL.get() or "").strip().lower()
        normalized = [
            item for item in normalized
            if item.get("reporter_user_id") == requester_id
            or (requester_email and item.get("reporter_email") == requester_email)
        ]

    normalized.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    return {"entries": normalized, "can_manage": bool(is_admin)}

@app.post("/api/beta-feedback")
async def submit_beta_feedback(body: Dict[str, Any]):
    if not isinstance(body, dict):
        return {"status": "error", "error": "Invalid payload"}
    if not bool(body.get("safety_acknowledged")):
        return {"status": "error", "error": "Safety acknowledgment is required."}

    now = datetime.now(timezone.utc).isoformat()
    reporter_user_id = str(_REQUEST_USER_ID.get() or "").strip()
    reporter_email = str(_REQUEST_USER_EMAIL.get() or "").strip().lower()
    if not _AUTH_REQUIRED:
        reporter_user_id = str(body.get("reporter_user_id") or reporter_user_id).strip()
        reporter_email = str(body.get("reporter_email") or reporter_email).strip().lower()

    candidate = {
        "id": str(uuid.uuid4()),
        "title": body.get("title"),
        "summary": body.get("summary"),
        "area": body.get("area"),
        "severity": body.get("severity"),
        "status": "new",
        "expected_behavior": body.get("expected_behavior"),
        "actual_behavior": body.get("actual_behavior"),
        "reproduction_steps": body.get("reproduction_steps"),
        "device": body.get("device"),
        "browser": body.get("browser"),
        "reproducible": body.get("reproducible", True),
        "safety_acknowledged": body.get("safety_acknowledged"),
        "reporter_user_id": reporter_user_id,
        "reporter_email": reporter_email,
        "created_at": now,
        "updated_at": now,
        "metadata": body.get("metadata"),
    }
    normalized = _normalize_beta_feedback_record(candidate, now=now)
    if normalized is None:
        return {"status": "error", "error": "summary and reproduction_steps are required."}

    entries = _read_json(BETA_FEEDBACK_FILE, default=[])
    if not isinstance(entries, list):
        entries = []
    entries.append(normalized)
    _write_json(BETA_FEEDBACK_FILE, entries)
    return {"status": "ok", "entry": normalized}

@app.post("/api/beta-feedback/{feedback_id}/status")
async def update_beta_feedback_status(feedback_id: str, body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    status = str((body or {}).get("status") or "").strip().lower()
    if status not in {"new", "triaged", "in_progress", "fixed", "closed"}:
        return {"status": "error", "error": "Invalid status."}

    entries = _read_json(BETA_FEEDBACK_FILE, default=[])
    if not isinstance(entries, list):
        entries = []
    now = datetime.now(timezone.utc).isoformat()
    for index, raw in enumerate(entries):
        if str((raw or {}).get("id") or "").strip() != feedback_id:
            continue
        updated = _normalize_beta_feedback_record({**raw, "status": status, "updated_at": now}, now=now)
        if updated is None:
            return {"status": "error", "error": "Record payload is invalid."}
        entries[index] = updated
        _write_json(BETA_FEEDBACK_FILE, entries)
        return {"status": "ok", "entry": updated}

    return {"status": "error", "error": "Feedback record not found."}

@app.get("/api/message-feedback")
async def list_message_feedback():
    blocked = _require_signed_in_api()
    if blocked is not None:
        return blocked
    user_id = _current_request_user_id()
    account_id = _active_account_id(_load_atlas_state())
    ratings = message_feedback.for_user(_load_message_feedback(), user_id=user_id, account_id=account_id)
    return {
        "status": "ok",
        "contract_version": message_feedback.CONTRACT_VERSION,
        "reasons": list(message_feedback.REASONS),
        "ratings": [message_feedback.public_view(item) for item in ratings],
    }

@app.post("/api/message-feedback")
async def rate_chat_message(body: Dict[str, Any]):
    blocked = _require_signed_in_api()
    if blocked is not None:
        return blocked
    body = body if isinstance(body, dict) else {}
    try:
        direction = message_feedback.normalize_direction(body.get("direction"))
        key = message_feedback.message_key(run_id=body.get("run_id"), created_at=body.get("created_at"))
        reason = message_feedback.normalize_reason(body.get("reason"))
    except message_feedback.FeedbackError as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=400)

    user_id = _current_request_user_id()
    account_id = _active_account_id(_load_atlas_state())
    thread_id = str(body.get("thread_id") or "").strip()
    found = _find_rated_chat_exchange(
        user_id, account_id, run_id=body.get("run_id"), created_at=body.get("created_at"), thread_id=thread_id,
    )
    if found is None:
        return JSONResponse({"status": "error", "error": "Message not found in your conversations."}, status_code=404)
    assistant_entry, prompt = found

    records = _load_message_feedback()
    if direction == "none":
        records, removed = message_feedback.remove(records, user_id=user_id, account_id=account_id, key=key)
        if removed:
            _write_json(MESSAGE_FEEDBACK_FILE, records)
        return {"status": "ok", "rating": {"message_key": key, "direction": "none"}}

    existing = message_feedback.find_rating(records, user_id=user_id, account_id=account_id, key=key)
    record = message_feedback.build_record(
        user_id=user_id,
        account_id=account_id,
        key=key,
        direction=direction,
        assistant_entry=assistant_entry,
        prompt=prompt,
        thread_id=thread_id,
        reason=reason,
        comment=body.get("comment"),
        existing=existing,
    )
    _write_json(MESSAGE_FEEDBACK_FILE, message_feedback.upsert(records, record))
    return {"status": "ok", "rating": message_feedback.public_view(record)}

@app.get("/api/message-feedback/summary")
async def message_feedback_summary(agent_id: str = "", date_from: str = "", date_to: str = ""):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    records = _load_message_feedback()
    try:
        filtered = message_feedback.filter_records(records, agent_id=agent_id, date_from=date_from, date_to=date_to)
    except message_feedback.FeedbackError as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=400)
    available_agents = sorted({
        str(item.get("agent_id") or "assistant") for item in records
        if isinstance(item, dict) and item.get("direction") in message_feedback.DIRECTIONS
    })
    return {"status": "ok", **message_feedback.summarize(filtered), "available_agents": available_agents}

@app.get("/api/message-feedback/regression-cases")
async def message_feedback_regression_cases(limit: int = 200, agent_id: str = "", date_from: str = "", date_to: str = ""):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        records = message_feedback.filter_records(
            _load_message_feedback(), agent_id=agent_id, date_from=date_from, date_to=date_to,
        )
    except message_feedback.FeedbackError as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=400)
    cases = message_feedback.build_regression_cases(records, limit=max(1, min(int(limit), 1000)))
    return {"status": "ok", "contract_version": message_feedback.REGRESSION_CONTRACT_VERSION, "cases": cases}

@app.get("/api/buildlog")
async def get_buildlog():
    blocked = _require_workspace_tier_api("pro")
    if blocked is not None:
        return blocked
    entries = _read_json(BUILDLOG_FILE, default=[])
    if not isinstance(entries, list):
        return []
    user_id = _current_request_user_id()
    is_admin = _request_is_admin()
    return [entry for entry in entries if _buildlog_entry_visible(entry, user_id, is_admin)]

@app.post("/api/buildlog")
async def append_buildlog(body: Dict[str, Any]):
    blocked = _require_workspace_tier_api("pro")
    if blocked is not None:
        return blocked
    entries = _read_json(BUILDLOG_FILE, default=[])
    if not isinstance(entries, list):
        entries = []
    fields = body.get("fields", {})
    if not isinstance(fields, dict):
        fields = {}
    entry = {
        "id":          str(uuid.uuid4()),
        "title":       body.get("title", "") or str(fields.get("primary_task") or ""),
        "description": body.get("description", "") or str(fields.get("session_goal") or ""),
        "tags":        body.get("tags", []),
        "command":     body.get("command", ""),
        "project":     body.get("project", "") or str(fields.get("project") or ""),
        "phase":       body.get("phase", "") or str(fields.get("phase") or ""),
        "month":       body.get("month", "") or str(fields.get("month") or ""),
        "status":      body.get("status", "") or str(fields.get("goal_outcome") or ""),
        "fields":      fields,
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "user_id":     _current_request_user_id(),
    }
    entries.append(entry)
    _write_json(BUILDLOG_FILE, entries)
    return entry

@app.get("/api/logsale")
async def get_sales():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _load_normalized_sales()

@app.post("/api/logsale")
async def log_sale(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    sales = _load_normalized_sales()
    item = str(body.get("item") or "").strip()
    if not item:
        return {"status": "error", "error": "item is required"}
    try:
        amount = _coerce_float(body.get("amount"), field="amount")
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}
    ledger = str(body.get("ledger") or "personal").strip().lower()
    if ledger not in _VALID_LEDGERS:
        return {"status": "error", "error": "ledger must be personal or business"}
    category = str(body.get("category") or "general").strip() or "general"
    entry = {
        "id":         str(uuid.uuid4()),
        "item":       item,
        "amount":     round(amount, 2),
        "ledger":     ledger,
        "category":   category,
        "notes":      str(body.get("notes", "")),
        "date":       body.get("date", datetime.now(timezone.utc).date().isoformat()),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    sales.append(entry)
    _write_json(SALES_FILE, sales)
    return entry

@app.get("/api/logsale/summary")
async def get_sales_summary():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    sales = _load_normalized_sales()
    return {"status": "ok", "summary": _sales_summary(sales)}

@app.get("/api/onboarding/state")
async def get_onboarding_state(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    state = _load_onboarding()
    user_state = state.get(uid, {})
    completed = user_state.get("completed_steps", [])
    steps_out = [
        {**step, "completed": step["id"] in completed}
        for step in _ONBOARDING_STEPS
    ]
    total = len(_ONBOARDING_STEPS)
    done = len(completed)
    return {
        "status": "ok",
        "user_id": uid,
        "steps": steps_out,
        "completed": done,
        "total": total,
        "percent": round(done / total * 100) if total else 0,
        "onboarding_complete": done >= total,
    }

@app.post("/api/onboarding/complete-step")
async def complete_onboarding_step(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    body = await request.json()
    step_id = str(body.get("step_id", "")).strip()
    valid_ids = {s["id"] for s in _ONBOARDING_STEPS}
    if step_id not in valid_ids:
        return JSONResponse({"status": "error", "error": f"Unknown step: {step_id}"}, status_code=400)
    state = _load_onboarding()
    user_state = state.setdefault(uid, {"completed_steps": [], "started_at": datetime.now(timezone.utc).isoformat()})
    if step_id not in user_state.get("completed_steps", []):
        user_state.setdefault("completed_steps", []).append(step_id)
        user_state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state[uid] = user_state
    _save_onboarding(state)
    return {"status": "ok", "step_id": step_id, "completed_steps": user_state["completed_steps"]}

@app.post("/api/onboarding/reset")
async def reset_onboarding(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    state = _load_onboarding()
    state[uid] = {"completed_steps": [], "started_at": datetime.now(timezone.utc).isoformat()}
    _save_onboarding(state)
    return {"status": "ok", "message": "Onboarding reset."}

@app.get("/api/notifications")
async def list_notifications(request: Request, unread_only: bool = False, limit: int = 50):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    is_admin = user.get("is_admin", False)
    items = _load_notifications()
    # Each user sees their own + broadcast (user_id=None) notifications
    visible = [
        n for n in items
        if (not n.get("dismissed"))
        and (n.get("user_id") is None or n.get("user_id") == uid or is_admin)
    ]
    if unread_only:
        visible = [n for n in visible if not n.get("read")]
    visible = list(reversed(visible[-limit:]))
    unread_count = sum(1 for n in visible if not n.get("read"))
    return {"status": "ok", "notifications": visible, "unread_count": unread_count}

@app.get("/api/notifications/unread-count")
async def get_unread_count(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    items = _load_notifications()
    count = sum(
        1 for n in items
        if not n.get("read") and not n.get("dismissed")
        and (n.get("user_id") is None or n.get("user_id") == uid)
    )
    return {"status": "ok", "unread_count": count}

@app.patch("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    items = _load_notifications()
    matched = False
    for n in items:
        if n.get("id") == notification_id and (n.get("user_id") is None or n.get("user_id") == uid):
            n["read"] = True
            matched = True
            break
    if not matched:
        return JSONResponse({"status": "error", "error": "Notification not found."}, status_code=404)
    _save_notifications(items)
    return {"status": "ok", "notification_id": notification_id}

@app.post("/api/notifications/mark-all-read")
async def mark_all_notifications_read(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    items = _load_notifications()
    for n in items:
        if n.get("user_id") is None or n.get("user_id") == uid:
            n["read"] = True
    _save_notifications(items)
    return {"status": "ok"}

@app.delete("/api/notifications/{notification_id}")
async def dismiss_notification(notification_id: str, request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    items = _load_notifications()
    matched = False
    for n in items:
        if n.get("id") == notification_id and (n.get("user_id") is None or n.get("user_id") == uid):
            n["dismissed"] = True
            matched = True
            break
    if not matched:
        return JSONResponse({"status": "error", "error": "Notification not found."}, status_code=404)
    _save_notifications(items)
    return {"status": "ok"}

@app.post("/api/notifications")
async def create_notification(request: Request):
    """Admin-only: create a system notification broadcast or targeted notification."""
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    if not user.get("is_admin"):
        return JSONResponse({"status": "error", "error": "Only administrators can create notifications."}, status_code=403)
    body = await request.json()
    note = _create_notification(
        title=str(body.get("title", "System Notification")),
        body=str(body.get("body", "")),
        kind=str(body.get("type", "info")),
        user_id=body.get("user_id"),
        action_url=body.get("action_url"),
        actor=user.get("email") or user.get("id", "admin"),
    )
    return {"status": "ok", "notification": note}
