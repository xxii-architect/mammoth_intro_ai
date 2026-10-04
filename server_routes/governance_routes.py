# Route fragment loaded by api_server._load_route_fragments().
# Not importable on its own: handlers execute in api_server globals, so keep helpers there.

@app.get("/api/operator/health")
async def get_operator_health():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    data = _read_json(OPERATOR_HEALTH_FILE, default={})
    payload = data if isinstance(data, dict) else {}
    normalized = _normalize_operator_health(payload)
    return {
        "status": "ok",
        "data": normalized,
        "updated_at": payload.get("updated_at"),
    }

@app.post("/api/operator/health")
async def set_operator_health(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    current = _read_json(OPERATOR_HEALTH_FILE, default={})
    if not isinstance(current, dict):
        current = {}
    allowed_keys = _PERCENT_HEALTH_FIELDS | _NUMERIC_HEALTH_FIELDS
    unknown = [k for k in body.keys() if k not in allowed_keys]
    if unknown:
        return {"status": "error", "error": f"Unknown operator health fields: {', '.join(sorted(unknown))}"}
    merged = dict(_normalize_operator_health(current))
    try:
        for key in _PERCENT_HEALTH_FIELDS:
            if key in body:
                value = _coerce_int(body.get(key), field=key)
                merged[key] = max(0, min(100, value))
        if "uptime" in body:
            merged["uptime"] = max(0, _coerce_int(body.get("uptime"), field="uptime"))
    except ValueError as exc:
        return {"status": "error", "error": str(exc)}
    merged["updated_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(OPERATOR_HEALTH_FILE, merged)
    return {"status": "ok", "data": _normalize_operator_health(merged), "updated_at": merged["updated_at"]}

@app.get("/api/modules")
async def get_modules():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    module_map: Dict[str, Dict[str, Any]] = {}
    manifest_map: Dict[str, Any] = {}
    for item in _STATIC_MODULES:
        module = dict(item)
        workflow = _workflow_state_for_agent(module["id"])
        module.update(workflow)
        module_map[module["id"]] = module

    if _agent_registry_ok:
        try:
            manifests = await agent_registry.list_agents()
        except Exception:
            manifests = []
        for manifest in manifests:
            agent_id = str(getattr(manifest, "agent_id", "") or "").strip()
            if not agent_id:
                continue
            workflow = _workflow_state_for_agent(agent_id)
            module = module_map.get(agent_id, {
                "id": agent_id,
                "name": getattr(manifest, "name", agent_id),
                "version": getattr(manifest, "version", "v1.0.0"),
                "status": "ready",
                "description": "Registered agent",
            })
            module.update({
                "id": agent_id,
                "name": getattr(manifest, "name", module.get("name", agent_id)),
                "version": getattr(manifest, "version", module.get("version", "v1.0.0")),
                "status": _normalize_module_status(getattr(manifest, "status", None)),
                "description": module.get("description") or "Registered agent",
                "capabilities": getattr(manifest, "capabilities", []),
                "level": getattr(manifest, "level", 1),
                "endpoint": getattr(manifest, "endpoint", ""),
                "source": "registry",
            })
            manifest_map[agent_id] = manifest
            module.update(_agent_quality_snapshot(agent_id))
            module.update(workflow)
            module_map[agent_id] = module

    agents_dir = ROOT / "src" / "mammoth_os" / "agents"
    if agents_dir.exists():
        for f in sorted(agents_dir.glob("*_agent.py")):
            mid = f.stem
            if mid in module_map:
                continue
            workflow = _workflow_state_for_agent(mid)
            module_map[mid] = {
                "id": mid,
                "name": "".join(w.title() for w in mid.split("_")),
                "version": "v1.0.0",
                "status": "ready",
                "description": f"Agent: {mid}",
                "source": "discovered",
                **workflow,
                **_agent_quality_snapshot(mid),
            }

    activity_index = _build_activity_index()
    for module in module_map.values():
        module_id = str(module.get("id") or "")
        status = str(module.get("status") or "ready")
        module.update(
            _module_observability_snapshot(
                module_id,
                status,
                manifest=manifest_map.get(module_id),
                activity_index=activity_index,
            )
        )

    return list(module_map.values())

@app.get("/api/mcp/servers")
async def get_mcp_servers():
    """Return the MCP server registry with config details and availability status."""
    index = _load_mcp_index()
    servers = []
    for entry in index.get("servers") or []:
        if not isinstance(entry, dict):
            continue
        cfg = _load_mcp_server_config(str(entry.get("config") or ""))
        import shutil
        command = cfg.get("command") or entry.get("command") or "npx"
        available = shutil.which(command) is not None
        servers.append({
            "id": str(entry.get("id") or ""),
            "label": str(entry.get("label") or cfg.get("name") or entry.get("id") or ""),
            "description": str(entry.get("description") or cfg.get("description") or ""),
            "category": str(entry.get("category") or "tool"),
            "enabled": bool(entry.get("enabled", True)) and bool(cfg.get("enabled", True)),
            "available": available,
            "status": "ready" if available else "needs_setup",
            "tools": cfg.get("tools") or [],
            "command": command,
            "transport": cfg.get("transport") or "stdio",
            "notes": cfg.get("notes") or [],
        })
    return {
        "status": "ok",
        "contract_version": "v1",
        "server_count": len(servers),
        "servers": servers,
    }

@app.get("/api/audit")
async def get_audit_log():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    entries = _load_audit_log()
    return {"status": "ok", "entries": entries[-80:]}

@app.get("/api/audit/export")
async def export_audit_log_csv():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    entries = _load_audit_log()
    csv_payload = _audit_entries_to_csv(entries[-250:])
    return PlainTextResponse(
        content=csv_payload,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="mammoth-audit-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}.csv"'},
    )

@app.post("/api/audit")
async def append_audit_log(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    kind = str(body.get("kind") or "generic").strip() or "generic"
    message = str(body.get("message") or f"{kind} event").strip() or f"{kind} event"
    details = body.get("details") if isinstance(body.get("details"), dict) else {}
    source = str(body.get("source") or "system").strip() or "system"
    actor = str(body.get("actor") or "system").strip() or "system"
    tier = str(body.get("tier") or "").strip() or None
    entry = _append_audit_event(kind=kind, message=message, details=details, source=source, actor=actor, tier=tier)
    return {"status": "ok", "entry": entry}

@app.get("/api/entitlements")
async def get_entitlements():
    """Return the current user's tier and feature entitlements."""
    state = _load_atlas_state()
    workspace = _build_workspace_accounts_snapshot(state)
    tier = str(state.get("tier") or "explorer").strip().lower()
    if tier not in {"explorer", "pro", "enterprise"}:
        tier = "explorer"
    developer_access = bool(state.get("developer_access", False))
    effective_tier = "enterprise" if developer_access else tier
    base_features = {
        "atlas_tutor": True,
        "adaptive_pacing": True,
        "lesson_resume": True,
        "flashcards_quiz": True,
        "basic_evals": True,
        "local_storage": True,
    }
    pro_features = {
        "multi_agent_orchestration": effective_tier in {"pro", "enterprise"},
        "plan_execute_all_profiles": effective_tier in {"pro", "enterprise"},
        "supabase_sync": effective_tier in {"pro", "enterprise"},
        "eval_history_dashboard": effective_tier in {"pro", "enterprise"},
        "audit_log_export": effective_tier in {"pro", "enterprise"},
        "coding_agent_approval": effective_tier in {"pro", "enterprise"},
    }
    enterprise_features = {
        "team_dashboards": effective_tier == "enterprise",
        "custom_curriculum": effective_tier == "enterprise",
        "lms_integration": effective_tier == "enterprise",
        "white_label": effective_tier == "enterprise",
    }
    profile = _normalized_account_profile(state)
    completion = _profile_completion(profile)
    return {
        "status": "ok",
        "tier": tier,
        "effective_tier": "developer" if developer_access else effective_tier,
        "developer_access": developer_access,
        "admin_controls_enabled": _request_is_admin(),
        "auth_mode": _auth_mode_from_state(state),
        "session_scope": "workspace_multi_account",
        "tier_updated_at": state.get("tier_updated_at"),
        "developer_access_updated_at": state.get("developer_access_updated_at"),
        "active_account_id": workspace.get("active_account_id"),
        "account_count": len(workspace.get("accounts") or []),
        "user_id": _atlas_user_id(state),
        "account_profile": profile,
        "account_profile_complete": all(completion.values()),
        "features": {**base_features, **pro_features, **enterprise_features},
        "upgrade_cta": "pricing" if tier == "explorer" and not developer_access else None,
    }

@app.get("/api/billing/usage/current")
async def get_current_billing_usage():
    state = _load_atlas_state()
    usage = _current_usage_snapshot_from_state(state)
    usage.update(
        {
            "auth_mode": _auth_mode_from_state(state),
            "active_account_id": _active_account_id(state),
            "user_id": _atlas_user_id(state),
        }
    )
    return usage

@app.post("/api/entitlements/tier")
async def set_tier(body: Dict[str, Any]):
    """Set the user's tier (for testing / admin use)."""
    if _AUTH_REQUIRED and not _request_is_admin():
        return {"status": "error", "error": "Admin privileges required for entitlement changes."}
    tier = str(body.get("tier") or "explorer").strip().lower()
    if tier not in {"explorer", "pro", "enterprise"}:
        return {"status": "error", "error": "Invalid tier. Use: explorer, pro, enterprise"}
    state = _load_atlas_state()
    state["tier"] = tier
    state["tier_updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    _append_audit_event(
        kind="tier_change",
        message="Entitlement tier updated",
        details={"tier": tier, "developer_access": bool(state.get("developer_access", False)), "account_id": _active_account_id(state)},
        source="entitlements",
        actor="user",
        tier=tier,
    )
    return {"status": "ok", "tier": tier, "active_account_id": _active_account_id(state), "user_id": _atlas_user_id(state)}

@app.get("/api/account/profile")
async def get_account_profile():
    state = _load_atlas_state()
    workspace = _build_workspace_accounts_snapshot(state)
    profile = _normalized_account_profile(state)
    completion = _profile_completion(profile)
    return {
        "status": "ok",
        "profile": profile,
        "profile_complete": all(completion.values()),
        "profile_completion": completion,
        "updated_at": state.get("account_profile_updated_at"),
        "auth_mode": _auth_mode_from_state(state),
        "session_scope": "workspace_multi_account",
        "tier": str(state.get("tier") or "explorer").strip().lower(),
        "developer_access": bool(state.get("developer_access", False)),
        "active_account_id": workspace.get("active_account_id"),
        "available_accounts": workspace.get("accounts"),
        "user_id": _atlas_user_id(state),
    }

@app.post("/api/account/profile")
async def set_account_profile(body: Dict[str, Any]):
    state = _load_atlas_state()
    profile = state.get("account_profile") if isinstance(state.get("account_profile"), dict) else {}
    for key in ("display_name", "email", "organization"):
        if key in body:
            profile[key] = str(body.get(key) or "").strip()
    state["account_profile"] = profile
    state["account_profile_updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    _append_audit_event(
        kind="profile_update",
        message="Account profile updated",
        details={"profile_fields": sorted(list(profile.keys())), "account_id": _active_account_id(state)},
        source="account",
        actor="user",
        tier=str(state.get("tier") or "explorer"),
    )
    normalized = _normalized_account_profile(state)
    completion = _profile_completion(normalized)
    return {
        "status": "ok",
        "profile": normalized,
        "profile_complete": all(completion.values()),
        "profile_completion": completion,
        "updated_at": state.get("account_profile_updated_at"),
        "active_account_id": _active_account_id(state),
        "user_id": _atlas_user_id(state),
    }

@app.post("/api/account/developer-access")
async def set_developer_access(body: Dict[str, Any]):
    if _AUTH_REQUIRED and not _request_is_admin():
        return {"status": "error", "error": "Admin privileges required for developer-access changes."}
    enabled = bool(body.get("enabled"))
    state = _load_atlas_state()
    state["developer_access"] = enabled
    state["developer_access_updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    _append_audit_event(
        kind="developer_access",
        message="Developer full-access mode toggled",
        details={"enabled": enabled, "account_id": _active_account_id(state)},
        source="entitlements",
        actor="user",
        tier="enterprise" if enabled else str(state.get("tier") or "explorer"),
    )
    return {
        "status": "ok",
        "developer_access": enabled,
        "auth_mode": _auth_mode_from_state(state),
        "effective_tier": "developer" if enabled else str(state.get("tier") or "explorer"),
        "updated_at": state.get("developer_access_updated_at"),
        "active_account_id": _active_account_id(state),
        "user_id": _atlas_user_id(state),
    }

@app.get("/api/account/workspace")
async def get_account_workspace():
    state = _load_atlas_state()
    return _build_workspace_accounts_snapshot(state)

@app.post("/api/account/workspace")
async def mutate_account_workspace(body: Dict[str, Any]):
    state = _load_atlas_state()
    action = str(body.get("action") or "").strip().lower()
    accounts = state.get("accounts") if isinstance(state.get("accounts"), dict) else {}
    sessions = state.get("account_sessions") if isinstance(state.get("account_sessions"), dict) else {}
    active_account_id = _active_account_id(state)

    if action == "create":
        raw_label = str(body.get("display_name") or body.get("label") or body.get("account_id") or "New account").strip()
        account_id = _normalize_account_id(body.get("account_id") or raw_label, fallback="account")
        if account_id in accounts:
            return {"status": "error", "error": f"Account already exists: {account_id}"}
        profile = {
            "display_name": raw_label or "Operator",
            "email": str(body.get("email") or "").strip(),
            "organization": str(body.get("organization") or "").strip(),
        }
        now = datetime.now(timezone.utc).isoformat()
        accounts[account_id] = {
            "profile": profile,
            "tier": "explorer",
            "developer_access": False,
            "created_at": now,
            "updated_at": now,
            "profile_updated_at": now,
        }
        sessions[account_id] = {"status": "no_session", "updated_at": now}
        if bool(body.get("activate", True)):
            _persist_active_account_collections(state)
            state["accounts"] = accounts
            state["account_sessions"] = sessions
            state["active_account_id"] = account_id
            _ensure_account_collections(state)
        else:
            state["accounts"] = accounts
            state["account_sessions"] = sessions
        state["updated_at"] = now
        _save_atlas_state(state)
        _append_audit_event(
            kind="account_created",
            message="Workspace account created",
            details={"account_id": account_id, "active": bool(body.get("activate", True))},
            source="account",
            actor="user",
            tier=str(state.get("tier") or "explorer"),
        )
        snapshot = _build_workspace_accounts_snapshot(state)
        return {"status": "ok", "action": action, **snapshot}

    if action == "switch":
        target_id = _normalize_account_id(body.get("account_id"), fallback="")
        if not target_id or target_id not in accounts:
            return {"status": "error", "error": "Unknown account_id"}
        _persist_active_account_collections(state)
        state["accounts"] = accounts
        state["account_sessions"] = sessions
        state["active_account_id"] = target_id
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _ensure_account_collections(state)
        _save_atlas_state(state)
        _append_audit_event(
            kind="account_switch",
            message="Workspace account switched",
            details={"account_id": target_id},
            source="account",
            actor="user",
            tier=str(state.get("tier") or "explorer"),
        )
        snapshot = _build_workspace_accounts_snapshot(state)
        return {"status": "ok", "action": action, **snapshot}

    if action == "delete":
        target_id = _normalize_account_id(body.get("account_id"), fallback="")
        if not target_id or target_id not in accounts:
            return {"status": "error", "error": "Unknown account_id"}
        if len(accounts) <= 1:
            return {"status": "error", "error": "At least one workspace account must remain."}
        if target_id == active_account_id:
            _persist_active_account_collections(state)
        accounts.pop(target_id, None)
        sessions.pop(target_id, None)
        if target_id == active_account_id:
            replacement_id = sorted(accounts.keys())[0]
            state["active_account_id"] = replacement_id
            _ensure_account_collections(state)
        else:
            state["accounts"] = accounts
            state["account_sessions"] = sessions
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_atlas_state(state)
        _append_audit_event(
            kind="account_deleted",
            message="Workspace account deleted",
            details={"account_id": target_id},
            source="account",
            actor="user",
            tier=str(state.get("tier") or "explorer"),
        )
        snapshot = _build_workspace_accounts_snapshot(state)
        return {"status": "ok", "action": action, **snapshot}

    return {"status": "error", "error": "Unsupported action. Use create, switch, or delete."}

@app.post("/api/account/delete-request")
async def request_account_deletion(request: Request):
    """
    GDPR Article 17 — Right to erasure.
    Initiates a soft-delete with a 30-day grace period.
    The user can cancel at any point before the grace period expires.
    """
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    body = await request.json()
    reason = str(body.get("reason", "")).strip()[:500]
    feedback = str(body.get("feedback", "")).strip()[:1000]

    existing = _get_deletion_request(uid)
    if existing:
        return JSONResponse({
            "status": "already_requested",
            "message": "An account deletion request is already pending.",
            "scheduled_delete_at": existing.get("scheduled_delete_at"),
            "request_id": existing.get("id"),
        })

    from datetime import timedelta
    scheduled = (datetime.now(timezone.utc) + timedelta(days=_DELETION_GRACE_DAYS)).isoformat()
    record = {
        "id": str(uuid.uuid4()),
        "user_id": uid,
        "email": user.get("email", ""),
        "status": "pending",
        "reason": reason,
        "feedback": feedback,
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "scheduled_delete_at": scheduled,
        "cancelled_at": None,
        "completed_at": None,
    }
    items = _load_deletion_requests()
    items.append(record)
    _save_deletion_requests(items)
    _append_audit_event(
        kind="account_delete_requested",
        message=f"Account deletion requested by user {uid}",
        details={"reason": reason, "scheduled_delete_at": scheduled},
        source="account",
        actor=uid,
        tier="user",
    )
    # Notify the user via the notifications system
    _create_notification(
        title="Account deletion scheduled",
        body=f"Your account is scheduled for permanent deletion in {_DELETION_GRACE_DAYS} days. You can cancel this request any time before then.",
        kind="warning",
        user_id=uid,
        action_url="/account",
    )
    return {
        "status": "ok",
        "message": f"Account deletion requested. Your data will be permanently deleted in {_DELETION_GRACE_DAYS} days unless you cancel.",
        "request_id": record["id"],
        "scheduled_delete_at": scheduled,
        "grace_days": _DELETION_GRACE_DAYS,
    }

@app.get("/api/account/delete-status")
async def get_deletion_status(request: Request):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    req = _get_deletion_request(uid)
    if not req:
        return {"status": "ok", "deletion_pending": False}
    from datetime import timedelta
    scheduled = datetime.fromisoformat(req["scheduled_delete_at"])
    now = datetime.now(timezone.utc)
    days_remaining = max(0, (scheduled - now).days)
    return {
        "status": "ok",
        "deletion_pending": True,
        "request_id": req["id"],
        "requested_at": req["requested_at"],
        "scheduled_delete_at": req["scheduled_delete_at"],
        "days_remaining": days_remaining,
        "can_cancel": days_remaining > 0,
    }

@app.post("/api/account/delete-cancel")
async def cancel_account_deletion(request: Request):
    """Cancel a pending deletion within the grace period."""
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")
    items = _load_deletion_requests()
    matched = False
    for r in items:
        if r.get("user_id") == uid and r.get("status") == "pending":
            r["status"] = "cancelled"
            r["cancelled_at"] = datetime.now(timezone.utc).isoformat()
            matched = True
            break
    if not matched:
        return JSONResponse({"status": "error", "error": "No pending deletion request found."}, status_code=404)
    _save_deletion_requests(items)
    _append_audit_event(
        kind="account_delete_cancelled",
        message=f"Account deletion cancelled by user {uid}",
        details={},
        source="account",
        actor=uid,
        tier="user",
    )
    _create_notification(
        title="Account deletion cancelled",
        body="Your account deletion request has been cancelled. Your account remains active.",
        kind="info",
        user_id=uid,
    )
    return {"status": "ok", "message": "Account deletion request cancelled. Your account remains fully active."}

@app.post("/api/account/export-data")
async def export_account_data(request: Request):
    """
    GDPR Article 20 — Right to data portability.
    Returns a structured export of all data associated with this user.
    """
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = user.get("id", "local")

    state = _load_atlas_state()
    notes = [n for n in _load_json_file(NOTES_FILE) if str(n.get("user_id") or "") == uid]
    activities = [a for a in _load_json_file(AGENT_ACTIVITY_FILE) if str(a.get("user_id") or "") == uid]
    notifs = [n for n in _load_notifications() if n.get("user_id") == uid or n.get("user_id") is None]
    ratings = [r for r in _load_message_feedback() if str(r.get("user_id") or "") == uid]

    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user_id": uid,
        "email": user.get("email", ""),
        "profile": state.get("profile", {}),
        "learner_model": state.get("learner_model", {}),
        "session_history_count": len(state.get("sessions", [])),
        "notes_count": len(notes),
        "notifications_count": len(notifs),
        "activity_count": len(activities),
        "notes": notes[:200],
        "notifications": notifs[:100],
        "activity": activities[:100],
        "message_feedback": ratings[-500:],
        "deletion_requests": [r for r in _load_deletion_requests() if r.get("user_id") == uid],
    }
    _append_audit_event(
        kind="account_data_exported",
        message=f"Data export requested by user {uid}",
        details={},
        source="account",
        actor=uid,
        tier="user",
    )
    return JSONResponse(
        content=export,
        headers={"Content-Disposition": "attachment; filename=mammoth-data-export.json"},
    )

@app.get("/api/rag/context/{user_id}")
async def get_user_rag_context(user_id: str, request: Request):
    """Retrieve reusable AI-derived context for a user (no PII)."""
    store = get_rag_context_store()
    entries = store.retrieve(user_id, limit=50)
    return {"user_id": user_id, "entries": entries, "count": len(entries)}

@app.delete("/api/rag/context/{user_id}")
async def delete_user_rag_context(user_id: str, request: Request):
    """GDPR wipe — delete all AI-derived context for a user."""
    store = get_rag_context_store()
    store.delete_user_data(user_id)
    return {"status": "wiped", "user_id": user_id}

@app.post("/api/rag/context/{user_id}")
async def store_user_rag_context(user_id: str, payload: dict, request: Request):
    """Store an AI-derived context entry for a user."""
    store = get_rag_context_store()
    context_type = payload.get("context_type", "general")
    content = payload.get("content", {})
    tags = payload.get("tags", [])
    ttl_hours = int(payload.get("ttl_hours", 72))
    entry_id = store.store(
        user_id=user_id,
        topic=context_type,
        content_type="api_context",
        content=content,
        source_agent="api",
        tags=tags,
        ttl_hours=ttl_hours,
    )
    return {"status": "stored", "entry_id": entry_id, "user_id": user_id}

@app.get("/api/audit/log")
async def get_audit_log(limit: int = 50, severity: str = None):
    """Get recent audit log entries, optionally filtered by severity."""
    entries = _audit.query(limit=limit, min_severity=severity if severity else "DEBUG")
    return {"entries": entries, "count": len(entries)}

@app.post("/api/audit/diagnose")
async def run_audit_diagnostics(payload: dict = {}):
    """Run system diagnostics and return findings."""
    findings = _audit.diagnose()
    return {"findings": findings, "count": findings.get("entries", 0)}

@app.delete("/api/audit/user/{user_id}")
async def clear_user_audit_data(user_id: str):
    """Privacy wipe — remove all audit entries for a user."""
    _audit.clear_user_data(user_id)
    return {"status": "cleared", "user_id": user_id}

@app.get('/api/download-docx/{filename:path}')
def download_docx_file(filename: str):
    from fastapi.responses import FileResponse
    safe = os.path.basename(str(filename or ""))
    if not safe.endswith('.docx') or '..' in safe or safe != filename:
        return JSONResponse({"status": "error", "error": "Invalid document name."}, status_code=400)
    blocked = _require_signed_in_api()
    if blocked is not None:
        return blocked
    path = GENERATED_DOCS_DIR / safe
    # Same 404 for "missing" and "not yours" so filenames can't be probed.
    if not _generated_doc_visible(safe) or not path.is_file():
        return JSONResponse({"status": "error", "error": "Document not found."}, status_code=404)
    return FileResponse(str(path), filename=safe, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')

