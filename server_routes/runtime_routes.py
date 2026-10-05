# Route fragment loaded by api_server._load_route_fragments().
# Not importable on its own: handlers execute in api_server globals, so keep helpers there.

@app.middleware("http")
async def auth_guard_middleware(request: Request, call_next):
    if not (request.url.path.startswith("/api/") or request.url.path.startswith("/agent/")):
        return await call_next(request)

    optional_path = request.method.upper() == "OPTIONS" or _is_auth_optional_path(request.url.path)
    token = _extract_bearer_token(request)
    user = _resolve_supabase_user(token) if token else None

    if user is None and _AUTH_REQUIRED and not optional_path:
        return JSONResponse({"status": "error", "error": "Authentication required"}, status_code=401)

    if user is not None:
        effective_user = user
    elif _AUTH_REQUIRED:
        effective_user = {"id": "anonymous", "email": "", "is_admin": False}
    else:
        effective_user = {"id": "local", "email": "", "is_admin": True}
    token_user, token_email, token_admin = _set_request_auth_context(request, effective_user)
    try:
        return await call_next(request)
    finally:
        _REQUEST_USER_ID.reset(token_user)
        _REQUEST_USER_EMAIL.reset(token_email)
        _REQUEST_IS_ADMIN.reset(token_admin)

@app.get("/api/status")
async def get_status():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    uptime_s = int(time.time() - _START_TIME)
    h, rem = divmod(uptime_s, 3600)
    m, s   = divmod(rem, 60)
    uptime_str = f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

    engines = {}
    if _engine_registry_ok:
        try:
            engines = EngineRegistry.list_engines()
        except Exception:
            pass

    agents = []
    if _agent_registry_ok:
        try:
            agents = await agent_registry.list_agents()
        except Exception:
            pass

    buildlog = _read_json(BUILDLOG_FILE)

    models = _models_snapshot()
    git_branch_result = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT))
    git_commit_result = _run_git_command(["rev-parse", "--short", "HEAD"], cwd=str(ROOT))
    git_branch = str(git_branch_result.get("stdout") or "").strip() if git_branch_result.get("status") == "ok" else "unknown"
    git_commit = str(git_commit_result.get("stdout") or "").strip() if git_commit_result.get("status") == "ok" else "unknown"

    return {
        "status": "ok",
        "python_version": sys.version,
        "uptime": uptime_str,
        "uptime_seconds": uptime_s,
        "engine_count": len(engines),
        "agent_count": len(agents),
        "cli_commands_run": len(buildlog),
        "active_models": max(1, len(models.get("local_models_installed", []))),
        "active_adapter": models.get("active_adapter"),
        "active_model": models.get("active_model"),
        "git_branch": git_branch or "unknown",
        "git_commit": git_commit or "unknown",
        "repo_root": str(ROOT),
    }

@app.get("/api/runtime/deploy-snapshot")
async def runtime_deploy_snapshot():
    state = _load_atlas_state()
    usage = _current_usage_snapshot_from_state(state)
    runtime = _runtime_status_snapshot()
    git_branch_result = _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT))
    git_commit_result = _run_git_command(["rev-parse", "--short", "HEAD"], cwd=str(ROOT))
    git_branch = str(git_branch_result.get("stdout") or "").strip() if git_branch_result.get("status") == "ok" else "unknown"
    git_commit = str(git_commit_result.get("stdout") or "").strip() if git_commit_result.get("status") == "ok" else "unknown"
    return {
        "status": "ok",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(ROOT),
        "git_branch": git_branch or "unknown",
        "git_commit": git_commit or "unknown",
        "runtime_state": runtime.get("state"),
        "active_adapter": runtime.get("active_adapter"),
        "active_model": runtime.get("active_model"),
        "usage_warning_level": usage.get("warning_level"),
        "usage_percent": usage.get("percent_used"),
    }

@app.get("/api/agents")
async def get_agents():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    if _agent_registry_ok:
        try:
            manifests = await agent_registry.list_agents()
            return [
                {
                    "id":           m.agent_id,
                    "name":         m.name,
                    "version":      m.version,
                    "status":       m.status.value if hasattr(m.status, "value") else str(m.status),
                    "capabilities": m.capabilities,
                    "level":        m.level,
                    "endpoint":     m.endpoint,
                }
                for m in manifests
            ]
        except Exception:
            pass

    # fallback — scan agents/ directory
    agents_dir = ROOT / "src" / "mammoth_os" / "agents"
    results = []
    if agents_dir.exists():
        for f in sorted(agents_dir.glob("*_agent.py")):
            name = f.stem.replace("_", " ").title().replace(" ", "")
            results.append({
                "id":           f.stem,
                "name":         name,
                "version":      "v1.0.0",
                "status":       "IDLE",
                "capabilities": [],
                "level":        1,
                "endpoint":     f"http://localhost:8000/agents/{f.stem}",
            })
    return results

@app.post("/agent/coding/run")
async def run_coding_agent_endpoint(payload: Any):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return await _dispatch_http_agent("coding", payload)

@app.post("/agent/shell/run")
async def run_shell_agent_endpoint(payload: Any):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    prompt = _coerce_http_agent_prompt(payload)
    if not prompt:
        return {"status": "error", "error": "command is required", "agent": "shell"}

    payload_dict = payload if isinstance(payload, dict) else {}
    cwd = str(payload_dict.get("cwd") or ROOT)
    timeout = int(payload_dict.get("timeout") or 120)
    allow_mutating = bool(payload_dict.get("allow_mutating") or False)

    try:
        from mammoth_os.agents.shell_agent import ShellAgent
        agent = ShellAgent()
        result = await agent.run(prompt, cwd=cwd, allow_mutating=allow_mutating, timeout=timeout)
        return {
            "status": result.get("status", "ok"),
            "agent": "shell",
            "result": result,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": _sanitize_runtime_error_message(exc, "The shell agent could not complete the command. MammothOS is running in a safe fallback mode until the runtime is healthy again."),
            "agent": "shell",
        }

@app.get("/api/health")
async def get_health():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    env_file = ROOT / ".env"
    env_exists = env_file.exists()
    env_values = _read_env_vars()
    env_vars: Dict[str, bool] = {}
    openai_ok = False
    supabase_ok = False
    for k, v in env_values.items():
        env_vars[k] = bool(v)
    openai_ok = bool(env_values.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))
    supabase_ok = bool(env_values.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL"))
    models = _models_snapshot()

    # check git
    git_ok = (ROOT / ".git").exists()

    # check venv
    venv_paths = [ROOT / ".venv", ROOT / "venv"]
    active_venv = next((path for path in venv_paths if path.exists()), venv_paths[0])
    venv_ok = any(path.exists() for path in venv_paths)

    services = [
        {
            "label":  "Backend API",
            "detail": ":8000 FastAPI",
            "status": "green" if _port_open(8000) else "red",
            "up":     _port_open(8000),
        },
    ]
    # The Vite dev server only exists in local development. Production serves the
    # built frontend, so the check is skipped there, and locally a stopped dev
    # server is a warning rather than a release blocker.
    if not _AUTH_REQUIRED:
        dev_port = _dev_server_port()
        dev_up = _port_open(dev_port)
        services.append({
            "label":  f"React Dev Server ({dev_port})",
            "detail": f":{dev_port} Vite",
            "status": "green" if dev_up else "yellow",
            "up":     dev_up,
        })
    services += [
        {
            "label":  ".env Config",
            "detail": str(env_file),
            "status": "green" if env_exists else "red",
            "up":     env_exists,
        },
        {
            "label":  "Git Repository",
            "detail": str(ROOT),
            "status": "green" if git_ok else "red",
            "up":     git_ok,
        },
        {
            "label":  "Python venv",
            "detail": str(active_venv),
            "status": "green" if venv_ok else "yellow",
            "up":     venv_ok,
        },
        {
            "label":  "OpenAI Key",
            "detail": "OPENAI_API_KEY in .env",
            "status": "green" if openai_ok else "yellow",
            "up":     openai_ok,
        },
        {
            "label":  "Supabase URL",
            "detail": "SUPABASE_URL in .env",
            "status": "green" if supabase_ok else "yellow",
            "up":     supabase_ok,
        },
        {
            "label":  "Ollama Runtime",
            "detail": models.get("ollama_base_url", "http://localhost:11434"),
            "status": "green" if models.get("ollama_running") else "yellow",
            "up":     bool(models.get("ollama_running")),
        },
    ]

    runtime = _runtime_status_snapshot()
    red_services = [service["label"] for service in services if service.get("status") == "red"]
    yellow_services = [service["label"] for service in services if service.get("status") == "yellow"]

    return {
        "services": services,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "env_keys": list(env_vars.keys()),
        "summary": {
            "healthy_services": len([service for service in services if service.get("status") == "green"]),
            "total_services": len(services),
            "red_services": red_services,
            "yellow_services": yellow_services,
        },
        "runtime": runtime,
        "health_gate": _health_gate_snapshot(services=services, runtime=runtime, env_exists=env_exists, venv_ok=venv_ok, git_ok=git_ok),
    }

@app.delete("/api/approvals/{record_id}")
async def delete_approval(record_id: str):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _delete_approval_record(record_id)

@app.get("/api/models")
async def get_models():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _models_snapshot()

@app.get("/api/telemetry/trust-metrics")
async def get_telemetry_trust_metrics(hours: int = 2):
    """
    GET /api/telemetry/trust-metrics
    Returns aggregated trust metrics (confidence, contradiction rate, citations) for the last N hours.
    Query params:
      - hours: int (default 2) — time window in hours
    """
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    
    metrics = _telemetry.get_metrics_for_window(hours=hours)
    return {
        "status": "ok",
        "metrics": metrics,
        "window_hours": hours,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

@app.get("/api/telemetry/release-readiness")
async def get_telemetry_release_readiness():
    """
    GET /api/telemetry/release-readiness
    Returns release readiness score (0-100) and go/no-go recommendation based on:
      - Confidence trend (must be >= 0.72 avg)
      - Contradiction rate < 8%
      - Citation coverage (avg >= 2.5 citations per response)
      - No critical provider errors in last 2 hours
    """
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    
    readiness = _telemetry.get_release_readiness()
    return {
        "status": "ok",
        "release_readiness": readiness,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

@app.get("/api/telemetry/provenance-metrics")
async def get_provenance_metrics(limit: int = 100, hours: int = 24):
    """
    GET /api/telemetry/provenance-metrics
    Returns provenance contract validation metrics from responses.
    Query params:
      - limit: int (default 100) — max number of metrics to return
      - hours: int (default 24) — time window in hours
    """
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    
    try:
        all_metrics = _read_json(TRUST_METRICS_FILE)
        if not isinstance(all_metrics, list):
            all_metrics = []
        
        # Filter by time window
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_metrics = []
        for metric in all_metrics:
            try:
                metric_time = datetime.fromisoformat(metric.get("timestamp", "").replace("Z", "+00:00"))
                if metric_time >= cutoff:
                    recent_metrics.append(metric)
            except Exception:
                pass
        
        # Sort by timestamp descending and limit results
        recent_metrics.sort(key=lambda m: m.get("timestamp", ""), reverse=True)
        recent_metrics = recent_metrics[:limit]
        
        # Aggregate statistics
        total_count = len(recent_metrics)
        passed_count = sum(1 for m in recent_metrics if m.get("validation_passed"))
        failed_count = total_count - passed_count
        avg_confidence = (
            sum(float(m.get("confidence", 0)) for m in recent_metrics) / total_count
            if total_count > 0 else 0
        )
        providers = {}
        for m in recent_metrics:
            provider = m.get("provider", "unknown")
            providers.setdefault(provider, 0)
            providers[provider] += 1
        
        return {
            "status": "ok",
            "metrics": recent_metrics,
            "aggregate": {
                "total": total_count,
                "passed": passed_count,
                "failed": failed_count,
                "pass_rate": passed_count / total_count if total_count > 0 else 0,
                "avg_confidence": round(avg_confidence, 3),
                "providers": providers,
            },
            "window_hours": hours,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "metrics": [],
            "aggregate": {},
        }

@app.post("/api/telemetry/record")
async def record_telemetry(body: Dict[str, Any]):
    """
    POST /api/telemetry/record
    Record a trust metric from an agent/provider response.
    Body:
      {
        "provider": "string",  // e.g. "gpt-4o-mini", "claude-3.5-sonnet", "deepseek"
        "confidence": float,   // 0.0-1.0
        "contradiction_count": int,
        "citation_count": int,
        "response_latency_ms": float
      }
    """
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    
    provider = str(body.get("provider", "unknown"))
    confidence = float(body.get("confidence", 0.5))
    contradiction_count = int(body.get("contradiction_count", 0))
    citation_count = int(body.get("citation_count", 0))
    response_latency_ms = float(body.get("response_latency_ms", 0.0))
    
    _telemetry.record_response(
        provider=provider,
        confidence=confidence,
        contradiction_count=contradiction_count,
        citation_count=citation_count,
        response_latency_ms=response_latency_ms,
    )
    
    return {
        "status": "ok",
        "recorded": {
            "provider": provider,
            "confidence": confidence,
            "contradiction_count": contradiction_count,
            "citation_count": citation_count,
            "response_latency_ms": response_latency_ms,
        },
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

@app.get("/api/telemetry/summary")
async def get_telemetry_summary():
    """
    GET /api/telemetry/summary
    Returns complete telemetry dashboard data: metrics, trends, and release readiness.
    """
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    
    summary = _telemetry.get_summary()
    return {
        "status": "ok",
        "data": summary,
    }

@app.get("/api/runtime/status")

async def get_runtime_status():
    return _merge_latest_runtime_status(_runtime_status_snapshot())

@app.get("/api/ui/active-project")
async def get_active_ui_project():
    state = _load_ui_state()
    return {
        "status": "ok" if state.get("exists") else "missing",
        "contract_version": "v2",
        "active_ui_project": state.get("active_ui_project") or "",
        "active_ui_dir": state.get("active_ui_dir") or "",
        "exists": bool(state.get("exists")),
        "state_file": state.get("state_file") or "",
    }

@app.get("/api/activity")
async def get_activity():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _load_activity_events()

@app.post("/api/activity")
async def add_activity(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _append_activity(
        str(body.get("message", "")),
        agent_id=str(body.get("agent_id", "") or ""),
        task_id=str(body.get("task_id", "") or ""),
        kind=str(body.get("kind", "event") or "event"),
        details=body.get("details") or {},
    )

@app.get("/api/tasks")
async def get_tasks():
    blocked = _require_signed_in_api()
    if blocked is not None:
        return blocked
    return _visible_tasks()

@app.post("/api/tasks")
async def upsert_task(body: Dict[str, Any]):
    blocked = _require_signed_in_api()
    if blocked is not None:
        return blocked
    task_id = str(body.get("id") or "").strip() or f"task-{uuid.uuid4().hex[:8]}"
    if not _request_is_admin():
        existing = next((t for t in _load_tasks() if isinstance(t, dict) and t.get("id") == task_id), None)
        if existing is not None and str(existing.get("owner_id") or "") != _current_request_user_id(""):
            return JSONResponse({"status": "error", "error": "Task not found."}, status_code=404)
    return _upsert_task(
        task_id,
        str(body.get("title", "Untitled task")),
        status=str(body.get("status", "queued") or "queued"),
        agent_id=str(body.get("agent_id", "") or ""),
        description=str(body.get("description", "") or ""),
        details=body.get("details") or {},
    )

@app.get("/api/observability/runs")
async def get_observability_runs():
    runs: List[Dict[str, Any]] = []
    tasks = _visible_tasks()
    for task in tasks[-20:]:
        details = task.get("details") if isinstance(task.get("details"), dict) else {}
        source = str(details.get("source") or "task").strip() or "task"
        run_status = str(task.get("status") or details.get("plan_status") or "unknown").strip() or "unknown"
        trace_id = str(details.get("trace_id") or task.get("trace_id") or "").strip()
        runs.append(
            build_observability_run(
                run_id=str(task.get("id") or ""),
                source=source,
                title=str(task.get("title") or "Task").strip() or "Task",
                status=run_status,
                created_at=task.get("created_at") or "",
                updated_at=task.get("updated_at") or task.get("created_at") or "",
                objective=str(details.get("objective") or task.get("description") or "").strip(),
                plan_profile=str(details.get("plan_profile") or "").strip(),
                trace_id=trace_id,
                summary=str(task.get("description") or "").strip()[:240],
                replay=details.get("replay") if isinstance(details.get("replay"), dict) else {},
                progress=details if details else {},
                details=details,
            )
        )

    state = _load_atlas_state()
    for plan in [item for item in (state.get("plan_history") or []) if isinstance(item, dict)][-12:]:
        progress = plan.get("progress") if isinstance(plan.get("progress"), dict) else {}
        runs.append(
            build_observability_run(
                run_id=str(plan.get("plan_id") or ""),
                source="atlas_plan",
                title=str(plan.get("objective") or "Atlas plan").strip() or "Atlas plan",
                status=str(plan.get("plan_status") or "unknown").strip() or "unknown",
                created_at=plan.get("created_at") or "",
                updated_at=plan.get("created_at") or "",
                objective=str(plan.get("objective") or "").strip(),
                plan_profile=str(plan.get("plan_profile") or "").strip(),
                trace_id=str(plan.get("trace_id") or "").strip(),
                summary=str((plan.get("synthesis") or {}).get("learner_summary") or "").strip()[:240],
                replay=plan.get("replay") if isinstance(plan.get("replay"), dict) else {},
                progress=progress,
                details=plan,
            )
        )

    runs.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
    # Activity, approvals, and snapshots are platform-wide operator data.
    is_admin = _request_is_admin()
    recent_activities = _load_activity_events()[-40:] if is_admin else []
    approvals = _load_approvals()[-20:] if is_admin else []
    snapshots = _load_snapshots()[-20:] if is_admin else []
    return {
        "status": "ok",
        "contract_version": "v2",
        "summary": {
            "run_count": len(runs[:25]),
            "activity_count": len(recent_activities),
            "approval_count": len(approvals),
            "snapshot_count": len(snapshots),
        },
        "runs": runs[:25],
        "activities": recent_activities,
        "approvals": approvals,
        "snapshots": snapshots,
    }

@app.post("/api/plan")
async def create_plan_endpoint(body: Dict[str, Any]):
    """
    Planner → Orchestrator → Task Queue → Executor pipeline.

    Request body
    ------------
    goal          : str   – high-level objective (required)
    constraints   : dict  – optional planner hints (budget, time, agents)
    execute       : bool  – False = plan-only; True = run tasks immediately
    approval_mode : bool  – gate each task behind pending_approval status
    trace_id      : str   – optional caller-supplied trace correlation ID

    Response (plan-only)
    --------------------
    { status, plan_id, trace_id, goal, task_count, tasks,
      total_estimated_minutes }

    Response (execute=true)
    -----------------------
    { status, plan_id, trace_id, goal, task_count,
      total_estimated_minutes, task_results }
    """
    goal = str(
        body.get("goal") or body.get("objective") or body.get("prompt") or ""
    ).strip()
    constraints = (
        body.get("constraints")
        if isinstance(body.get("constraints"), dict)
        else {}
    )
    execute = bool(body.get("execute", False))
    approval_mode = bool(body.get("approval_mode", False))

    if not goal:
        return JSONResponse(
            status_code=422,
            content={"status": "error", "error": "goal is required"},
        )

    trace_id = str(body.get("trace_id") or new_trace_id("plan"))
    plan_id = f"plan-{uuid.uuid4().hex[:8]}"

    # ── Step 1: Planner decomposes the goal into an ordered task list ──────
    from mammoth_os.agent_registry import load_agent, run_agent as _run_agent

    planner = load_agent("planner")
    plan = await planner.create_plan(goal, constraints)
    tasks = plan.get("tasks") or []
    total_minutes = plan.get("total_estimated_minutes", 0)
    # Defensive title synthesis — guard against LLM schema drift
    for _t in tasks:
        if not _t.get("title"):
            _agent_label = str(_t.get("agent") or "task").replace("_", " ").title()
            _t["title"] = f"{_agent_label}: {goal[:50]}"

    _upsert_task(
        plan_id,
        "plan",
        status="planned",
        agent_id="planner",
        description=goal,
        details={
            "goal": goal,
            "task_count": len(tasks),
            "execute": execute,
            "approval_mode": approval_mode,
            "trace_id": trace_id,
        },
    )
    _append_activity(
        "Plan created",
        agent_id="planner",
        task_id=plan_id,
        kind="plan_created",
        details={"goal": goal, "task_count": len(tasks), "trace_id": trace_id},
    )

    # ── Plan-only mode: return the task graph without running anything ─────
    if not execute:
        return {
            "status": "planned",
            "plan_id": plan_id,
            "trace_id": trace_id,
            "goal": goal,
            "task_count": len(tasks),
            "tasks": tasks,
            "total_estimated_minutes": total_minutes,
        }

    # ── Step 2: Orchestrator coordinates execution order (depends_on graph) ─
    # ── Step 3: Task queue buffers each unit of work ────────────────────────
    # ── Step 4: Executor dispatches to the assigned agent ───────────────────
    completed: Dict[str, Any] = {}
    task_results = []

    for task in tasks:
        task_id = str(task.get("task_id") or uuid.uuid4().hex[:8])
        agent_slug = str(task.get("agent") or "orchestrator")
        task_input = dict(task.get("input") or {})
        depends_on = task.get("depends_on") or []

        # Inject upstream task outputs as context for dependent tasks
        for dep_id in depends_on:
            if dep_id in completed:
                task_input.setdefault("context", {})
                task_input["context"][dep_id] = completed[dep_id]

        if approval_mode:
            task_results.append(
                {
                    "task_id": task_id,
                    "agent": agent_slug,
                    "status": "pending_approval",
                    "title": task.get("title", ""),
                    "input": task_input,
                }
            )
            continue

        try:
            result = await asyncio.to_thread(_run_agent, agent_slug, task_input)
            completed[task_id] = result
            task_results.append(
                {
                    "task_id": task_id,
                    "agent": agent_slug,
                    "status": str(result.get("status") or "ok"),
                    "title": task.get("title", ""),
                    "result": result,
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "api/plan executor: task %s (%s) failed: %s",
                task_id,
                agent_slug,
                exc,
            )
            task_results.append(
                {
                    "task_id": task_id,
                    "agent": agent_slug,
                    "status": "error",
                    "title": task.get("title", ""),
                    "error": str(exc),
                }
            )

    errored = [r for r in task_results if r.get("status") == "error"]
    final_status = (
        "pending_approval"
        if approval_mode
        else ("partial" if errored else "ok")
    )

    _upsert_task(
        plan_id,
        "plan",
        status=final_status,
        agent_id="orchestrator",
        description=goal,
        details={"completed_tasks": len(completed), "errored_tasks": len(errored)},
    )
    _append_activity(
        "Plan executed",
        agent_id="orchestrator",
        task_id=plan_id,
        kind="plan_completed",
        details={
            "goal": goal,
            "status": final_status,
            "task_count": len(tasks),
            "errored": len(errored),
            "trace_id": trace_id,
        },
    )

    return {
        "status": final_status,
        "plan_id": plan_id,
        "trace_id": trace_id,
        "goal": goal,
        "task_count": len(tasks),
        "total_estimated_minutes": total_minutes,
        "task_results": task_results,
    }

@app.post("/api/plan-execute")
async def plan_execute(body: Dict[str, Any]):
    objective = str(body.get("objective", "") or body.get("prompt", "")).strip()
    temperature = body.get("temperature", 0.4)
    approval_mode = bool(body.get("approval_mode"))
    stop_on_failure = bool(body.get("stop_on_failure", True))
    plan_profile = _normalize_plan_profile(body.get("plan_profile"))
    coding_intent = _normalize_coding_intent(body.get("coding_intent")) or _default_coding_intent_for_profile(plan_profile)

    if not objective:
        return {"status": "error", "error": "objective is required"}

    plan_id = f"plan-{uuid.uuid4().hex[:8]}"
    steps = _build_plan_steps(objective, plan_profile, coding_intent)

    if bool(body.get("dry_run")):
        return {
            "status": "ok",
            "dry_run": True,
            "objective": objective,
            "plan_profile": plan_profile,
            "coding_intent": coding_intent,
            "plan_status": "preview",
            "progress": {"total": len(steps), "executed": 0, "completed": 0, "pending_approval": 0, "failed": 0},
            "plan_steps": [
                {
                    "id": step["id"],
                    "title": step["title"],
                    "agent_id": step["agent_id"],
                    "intent": step["intent"],
                    "prompt": step["prompt"],
                    "kind": step.get("kind") or "agent",
                    "status": "planned",
                    "requires_approval": approval_mode and (step["agent_id"] == "coding_agent" or bool(step.get("approval_contract"))),
                }
                for step in steps
            ],
        }

    requested_ids = body.get("step_ids")
    if isinstance(requested_ids, list) and requested_ids:
        wanted = {str(item) for item in requested_ids}
        steps = [step for step in steps if step["id"] in wanted or step.get("kind") == "synthesis"]
        if not any(step.get("kind") != "synthesis" for step in steps):
            return {"status": "error", "error": "step_ids did not match any planned step"}

    _upsert_task(
        plan_id,
        "plan+execute run",
        status="active",
        agent_id="orchestrator",
        description=objective,
        details={
            "objective": objective,
            "step_count": len(steps),
            "approval_mode": approval_mode,
            "plan_profile": plan_profile,
            "coding_intent": coding_intent,
        },
    )
    _append_activity(
        "Started plan+execute run",
        agent_id="orchestrator",
        task_id=plan_id,
        kind="plan_started",
        details={"objective": objective, "step_count": len(steps), "plan_profile": plan_profile, "coding_intent": coding_intent},
    )

    step_results = await _execute_plan_steps(
        plan_id=plan_id,
        steps=steps,
        objective=objective,
        temperature=float(temperature),
        approval_mode=approval_mode,
        stop_on_failure=stop_on_failure,
        activity_agent_id="orchestrator",
    )

    failed_count = sum(1 for s in step_results if s["status"] == "failed")
    pending_count = sum(1 for s in step_results if s["status"] == "pending_approval")
    completed_count = sum(1 for s in step_results if s["status"] == "completed")
    executed_count = len(step_results)
    total_count = len(steps)
    runtime_snapshot = _summarize_plan_run(
        step_results,
        objective=objective,
        plan_profile=plan_profile,
        coding_intent=coding_intent,
        approval_mode=approval_mode,
    )

    if failed_count > 0:
        plan_status = "failed"
    elif pending_count > 0:
        plan_status = "pending_approval"
    else:
        plan_status = "completed"

    _upsert_task(
        plan_id,
        "plan+execute run",
        status=plan_status,
        agent_id="orchestrator",
        description=objective,
        details={
            "objective": objective,
            "plan_profile": plan_profile,
            "coding_intent": coding_intent,
            "total": total_count,
            "executed": executed_count,
            "completed": completed_count,
            "pending_approval": pending_count,
            "failed": failed_count,
            "current_lane": runtime_snapshot.get("current_lane") or {},
            "approvals_needed": runtime_snapshot.get("approvals_needed") or [],
            "approvals_needed_count": runtime_snapshot.get("approvals_needed_count") or 0,
            "replay": runtime_snapshot.get("replay") or {},
        },
    )

    _append_activity(
        f"Plan+execute run {plan_status}",
        agent_id="orchestrator",
        task_id=plan_id,
        kind="plan_completed" if plan_status != "failed" else "plan_failed",
        details={"objective": objective, "plan_profile": plan_profile, "coding_intent": coding_intent, "executed": executed_count, "failed": failed_count},
    )

    response = {
        "status": "ok",
        "plan_id": plan_id,
        "objective": objective,
        "plan_profile": plan_profile,
        "coding_intent": coding_intent,
        "plan_status": plan_status,
        "progress": {
            "total": total_count,
            "executed": executed_count,
            "completed": completed_count,
            "pending_approval": pending_count,
            "failed": failed_count,
        },
        "plan_steps": step_results,
        **runtime_snapshot,
        "summary": _plan_run_summary(step_results),
        "provider": "orchestrator",
        "confidence": 0.9 if plan_status == "completed" else 0.6,  # Lower confidence if partial/failed
        "citations": ["Plan step execution", "Task tracking"],
        "contradictions": ["approved" if pending_count > 0 else ""],
    }
    return _wrap_response_with_trust(response, endpoint="/api/plan-execute", response_type="general")

@app.get("/api/autonomous/runs")
async def get_autonomous_runs():
    state = _load_atlas_state()
    recent_runs: List[Dict[str, Any]] = []

    def _run_status_for(value: Any, *, fallback: str = "active") -> str:
        normalized = str(value or fallback).strip().lower()
        valid = {"completed", "pending_approval", "failed", "active", "running", "queued", "unknown"}
        if normalized in valid:
            return normalized
        if normalized in {"success", "succeeded"}:
            return "completed"
        if normalized in {"waiting", "approval", "needs_approval"}:
            return "pending_approval"
        return fallback

    def _run_label(objective: Any, *, status: str, profile: Any) -> str:
        raw = str(objective or "Autonomous run").strip()
        label = raw if raw else "Autonomous run"
        if len(label) > 72:
            label = f"{label[:69]}..."
        profile_name = str(profile or "balanced").strip() or "balanced"
        return f"{label} • {status} • {profile_name}"


    plan_tasks = [
        task for task in _visible_tasks()
        if (
            str(task.get("id", "")).startswith("plan-")
            or str(task.get("title", "")).strip() == "plan+execute run"
        )
    ]
    for task in plan_tasks[-12:]:
        details = task.get("details") if isinstance(task.get("details"), dict) else {}
        approvals_needed = details.get("approvals_needed") if isinstance(details.get("approvals_needed"), list) else []
        current_lane = details.get("current_lane") if isinstance(details.get("current_lane"), dict) else {}
        status = _run_status_for(task.get("status") or details.get("plan_status"), fallback="active")
        objective = details.get("objective") or task.get("description") or ""
        profile_name = _normalize_plan_profile(details.get("plan_profile"))
        lane_count = int(bool(current_lane)) + len(approvals_needed)
        entry = {
            "run_id": task.get("id"),
            "source": "plan_execute",
            "objective": objective,
            "run_label": _run_label(objective, status=status, profile=profile_name),
            "plan_profile": profile_name,
            "coding_intent": _normalize_coding_intent(details.get("coding_intent")) or _default_coding_intent_for_profile(details.get("plan_profile")),
            "plan_status": status,
            "status": status,
            "created_at": task.get("created_at") or task.get("updated_at") or "",
            "updated_at": task.get("updated_at") or task.get("created_at") or "",
            "progress": {
                "total": int(details.get("total") or details.get("step_count") or 0),
                "executed": int(details.get("executed") or 0),
                "completed": int(details.get("completed") or 0),
                "pending_approval": int(details.get("pending_approval") or 0),
                "failed": int(details.get("failed") or 0),
            },
            "current_lane": current_lane,
            "approvals_needed": approvals_needed,
            "approvals_needed_count": int(details.get("approvals_needed_count") or len(approvals_needed)),
            "lane_count": lane_count,
            "replay": details.get("replay") or {
                "execution_mode": "plan",
                "objective": objective,
                "plan_profile": profile_name,
                "coding_intent": _normalize_coding_intent(details.get("coding_intent")) or _default_coding_intent_for_profile(details.get("plan_profile")),
                "approval_mode": bool(details.get("pending_approval") or details.get("approval_mode")),
                "step_count": int(details.get("step_count") or details.get("total") or 0),
            },
        }
        recent_runs.append(entry)

    for plan in [item for item in (state.get("plan_history") or []) if isinstance(item, dict)][-12:]:
        progress = plan.get("progress") if isinstance(plan.get("progress"), dict) else {}
        approvals_needed = plan.get("approvals_needed") if isinstance(plan.get("approvals_needed"), list) else []
        current_lane = plan.get("current_lane") if isinstance(plan.get("current_lane"), dict) else {}
        status = _run_status_for(plan.get("plan_status"), fallback="active")
        objective = plan.get("objective") or ""
        profile_name = _normalize_plan_profile(plan.get("plan_profile"))
        lane_count = int(bool(current_lane)) + len(approvals_needed)
        entry = {
            "run_id": plan.get("plan_id"),
            "source": "atlas_plan",
            "objective": objective,
            "run_label": _run_label(objective, status=status, profile=profile_name),
            "plan_profile": profile_name,
            "coding_intent": _normalize_coding_intent(plan.get("coding_intent")) or _default_coding_intent_for_profile(plan.get("plan_profile")),
            "plan_status": status,
            "status": status,
            "created_at": plan.get("created_at") or "",
            "updated_at": plan.get("created_at") or "",
            "progress": {
                "total": int(progress.get("total") or 0),
                "executed": int(progress.get("executed") or 0),
                "completed": int(progress.get("completed") or 0),
                "pending_approval": int(progress.get("pending_approval") or 0),
                "failed": int(progress.get("failed") or 0),
            },
            "current_lane": current_lane,
            "approvals_needed": approvals_needed,
            "approvals_needed_count": int(plan.get("approvals_needed_count") or len(approvals_needed)),
            "lane_count": lane_count,
            "replay": plan.get("replay") or {
                "execution_mode": "plan",
                "objective": objective,
                "plan_profile": profile_name,
                "coding_intent": _normalize_coding_intent(plan.get("coding_intent")) or _default_coding_intent_for_profile(plan.get("plan_profile")),
                "approval_mode": bool(progress.get("pending_approval")),
                "step_count": int(progress.get("total") or 0),
            },
        }
        recent_runs.append(entry)

    recent_runs.sort(key=lambda run: str(run.get("created_at") or ""), reverse=True)
    recent_runs = recent_runs[:20]

    latest_run = recent_runs[0] if recent_runs else {}
    summary = {
        "total_runs": len(recent_runs),
        "completed": sum(1 for run in recent_runs if run.get("plan_status") == "completed"),
        "pending_approval": sum(1 for run in recent_runs if run.get("plan_status") == "pending_approval"),
        "failed": sum(1 for run in recent_runs if run.get("plan_status") == "failed"),
        "active": sum(1 for run in recent_runs if run.get("plan_status") in {"active", "running", "pending_approval"}),
        "latest_run_at": latest_run.get("created_at") or "",
        "latest_run_status": latest_run.get("status") or "unknown",
        "latest_run_label": latest_run.get("run_label") or latest_run.get("objective") or "Autonomous run",
        "awaiting_approval": sum(int(run.get("approvals_needed_count") or 0) for run in recent_runs),
    }

    return {
        "status": "ok",
        "contract_version": "v1",
        "profiles": ["atlas", "coding", "coding_only", "balanced", "autonomous"],
        "summary": summary,
        "runs": recent_runs,
    }

@app.post("/api/run")
async def run_agent(body: Dict[str, Any]):
    intent = str(body.get("intent", "")).strip()
    payload = body.get("payload") or {}
    if not payload:
        _top = {k: v for k, v in body.items() if k in {"prompt", "query", "topic", "content", "context"}}
        if _top:
            payload = _top
    payload_dict = dict(payload) if isinstance(payload, dict) else {}
    temperature = body.get("temperature", 0.7)
    requested_agent_id = str(body.get("agent_id", "")).strip()
    tracked_agent_id = requested_agent_id or _agent_id_from_intent(intent)
    prompt_text = str(payload_dict.get("prompt", "") or "").strip()
    display_prompt = prompt_text
    history_turns = _normalize_conversation_history(payload_dict.get("history"))
    llm_background = _compose_llm_background(history_turns, payload_dict.pop("background", ""))
    if "history" in payload_dict:
        payload_dict = _apply_conversation_history(payload_dict, history_turns, _runtime_agent_name(intent, tracked_agent_id))
        prompt_text = str(payload_dict.get("prompt", "") or "").strip()
    payload = payload_dict if isinstance(payload, dict) else payload
    approval_mode = bool(body.get("approval_mode") or payload_dict.get("approval_mode") or payload_dict.get("preview_only"))
    coding_intent = _normalize_coding_intent(payload_dict.get("coding_intent")) or _normalize_coding_intent(intent)
    trace_id = str(body.get("trace_id") or new_trace_id("run"))
    runtime_status = _runtime_status_snapshot()
    preflight_checks: List[Dict[str, Any]] = []
    if runtime_status.get("state") != "ready":
        preflight_checks.append({
            "name": "runtime_state",
            "status": "warn",
            "detail": str(runtime_status.get("recommendation") or runtime_status.get("issue") or "Runtime is degraded."),
        })
    if approval_mode:
        preflight_checks.append({
            "name": "approval_mode",
            "status": "pass",
            "detail": "Approval gating is enabled for this run.",
        })
    if runtime_status.get("active_adapter") == "local":
        preflight_checks.append({
            "name": "local_fallback",
            "status": "warn",
            "detail": "The runtime is using local fallback mode.",
        })
    preflight = {
        "contract_version": "v2",
        "status": "warn" if any(item.get("status") == "warn" for item in preflight_checks) else "ok",
        "checks": preflight_checks,
    }

    thought_steps: List[Dict[str, Any]] = []

    def _think(label: str, detail: str = "", status: str = "info") -> None:
        thought_steps.append({"ts": _ts(), "label": label, "detail": detail, "status": status})

    def _is_failure_payload(value: Any) -> bool:
        if isinstance(value, dict):
            if value.get("status") == "error":
                return True
            if value.get("passed") is False:
                return True
            result = value.get("result")
            if isinstance(result, dict) and result.get("passed") is False:
                return True
            return any(_is_failure_payload(child) for child in value.values())
        if isinstance(value, list):
            return any(_is_failure_payload(item) for item in value)
        return False

    _think("Received request", f"intent={intent!r}  agent={requested_agent_id!r}  approval_mode={approval_mode}")
    if history_turns:
        _think("Conversation context", f"{len(history_turns)} earlier turn(s) available to the model as background")
    elif llm_background:
        _think("Earlier results", "Results from earlier plan steps available to the model as background")

    task_id = f"task-{uuid.uuid4().hex[:8]}"
    task = _upsert_task(
        task_id,
        f"{intent or 'agent'} run",
        status="active",
        agent_id=tracked_agent_id,
        description=display_prompt or "Agent execution started",
        details={"intent": intent, "temperature": temperature, "approval_mode": approval_mode, "trace_id": trace_id, "history_turns": len(history_turns)},
    )
    _append_activity(
        f"Started task for {intent or 'agent'}",
        agent_id=tracked_agent_id,
        task_id=task_id,
        kind="task_started",
        trace_id=trace_id,
        details={"prompt": display_prompt[:220], "temperature": temperature, "approval_mode": approval_mode, "trace_id": trace_id},
    )

    manifest = None
    if _agent_registry_ok and tracked_agent_id:
        try:
            manifest = await agent_registry.get_agent(tracked_agent_id)
            if manifest is None and not tracked_agent_id.endswith("_agent"):
                manifest = await agent_registry.get_agent(f"{tracked_agent_id}_agent")
            if manifest:
                manifest.status = AgentStatus.ACTIVE
                manifest.last_heartbeat = datetime.now(timezone.utc)
                _think("Agent resolved", f"name={manifest.name!r}  type={getattr(manifest, 'agent_type', 'unknown')!r}", "success")
            else:
                _think("Agent not in registry", f"id={tracked_agent_id!r} — will fall back to intent routing", "warning")
        except Exception:
            manifest = None

    try:
        runtime_agent = _runtime_agent_name(intent, tracked_agent_id)
        if not _mutation_allowed() and (
            tracked_agent_id in _PRIVILEGED_AGENT_IDS
            or runtime_agent in _PRIVILEGED_RUNTIME_AGENTS
            or intent in _PRIVILEGED_INTENTS
        ):
            _think("Privileged agent denied", "owner/admin privileges required for host-executing agents", "error")
            denied = _owner_mutation_denied(intent or tracked_agent_id or runtime_agent)
            _upsert_task(task_id, task["title"], status="failed", agent_id=tracked_agent_id, description="Privileged agent blocked", details={"intent": intent, "trace_id": trace_id})
            return {
                "status": "error",
                "task_id": task_id,
                "agent_id": tracked_agent_id,
                "result": denied,
                "thought_steps": thought_steps,
                "runtime_status": runtime_status,
                "trace_id": trace_id,
                "preflight": preflight,
            }
        execution_policy = _execution_policy_for_run(body, payload_dict, runtime_agent=runtime_agent)
        preflight_checks.append(
            {
                "name": "execution_contract",
                "status": "pass",
                "detail": f"max_attempts={execution_policy['max_attempts']} required_fields={','.join(execution_policy['required_fields'])}",
            }
        )
        preflight = {
            "contract_version": "v2",
            "status": "warn" if any(item.get("status") == "warn" for item in preflight_checks) else "ok",
            "checks": preflight_checks,
        }
        _think("Routing decision", f"runtime_agent={runtime_agent!r}  agent_id={tracked_agent_id!r}")
        coding_op, coding_payload = _parse_coding_operation(payload_dict, prompt_text)
        if runtime_agent == "coding" and coding_op:
            if not _mutation_allowed():
                _think("Mutation denied", "owner/admin privileges required for code mutation", "error")
                result = _owner_mutation_denied(coding_op)
                _upsert_task(
                    task_id,
                    task["title"],
                    status="failed",
                    agent_id=tracked_agent_id,
                    description=prompt_text or "Mutation blocked",
                    details={"intent": intent, "error": result.get("error"), "trace_id": trace_id},
                )
                _append_activity(
                    "Blocked non-owner mutation attempt",
                    agent_id=tracked_agent_id,
                    task_id=task_id,
                    kind="mutation_blocked",
                    trace_id=trace_id,
                    details={"operation": coding_op, "trace_id": trace_id},
                )
                return {
                    "status": "error",
                    "task_id": task_id,
                    "agent_id": tracked_agent_id,
                    "result": result,
                    "thought_steps": thought_steps,
                    "runtime_status": runtime_status,
                    "trace_id": trace_id,
                    "preflight": preflight,
                }
            _think("Operation parsed", f"op={coding_op!r}  target={coding_payload.get('file_path','?')!r}")
            if approval_mode:
                preview = _build_operation_preview(coding_op, coding_payload)
                approval = _create_approval_record(
                    task_id,
                    agent_id=tracked_agent_id or "coding_agent",
                    operation=coding_op,
                    target=str(coding_payload.get("file_path", "")) or "unknown",
                    preview=preview,
                    payload=coding_payload,
                    requested_by="user",
                    trace_id=trace_id,
                )
                _upsert_task(
                    task_id,
                    task["title"],
                    status="pending_approval",
                    agent_id=tracked_agent_id,
                    description=prompt_text or "Approval required for file change",
                    details={"intent": intent, "temperature": temperature, "approval_id": approval["id"], "trace_id": trace_id},
                )
                _append_activity(
                    f"Requested approval for {coding_op}",
                    agent_id=tracked_agent_id,
                    task_id=task_id,
                    kind="approval_requested",
                    trace_id=trace_id,
                    details={"approval_id": approval["id"], "target": approval["target"], "trace_id": trace_id},
                )
                _think("Queued for approval", f"approval_id={approval['id']}  op={coding_op!r}  target={approval['target']!r}", "warning")
                result = {
                    "status": "pending_approval",
                    "runtime_agent": runtime_agent,
                    "operation": coding_op,
                    "approval": approval,
                    "preview": preview,
                }
            else:
                _think("Executing file operation", f"op={coding_op!r}  direct=True")
                raw_result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _run_file_operation(coding_op, coding_payload)
                )
                _think("File operation done", f"status={raw_result.get('status','?')!r}  path={raw_result.get('path','?')!r}", "success")
                result = {
                    "status": "ok",
                    "runtime_agent": runtime_agent,
                    "operation": coding_op,
                    "output": raw_result,
                }
        elif runtime_agent and (runtime_agent == "custodial" or (_agent_registry_ok and runtime_agent in AGENTS)):
            handled_special_result = False
            payload_for_agent: Any = prompt_text or json.dumps(payload)
            payload_agents = {"plant_the_seed", "market_intel", "reflection", "brand_voice", "community_engine", "tutor", "reasoning", "coding", "browser", "task_queue", "mammoth_guide", "planner", "search"}
            if runtime_agent in payload_agents:
                payload_for_agent = dict(payload) if isinstance(payload, dict) else {}
                if not isinstance(payload_for_agent, dict):
                    payload_for_agent = {}
                if prompt_text:
                    if runtime_agent == "coding":
                        payload_for_agent.setdefault("prompt", prompt_text)
                        payload_for_agent.setdefault("task", prompt_text)
                        payload_for_agent.setdefault("files", [])
                        payload_for_agent.setdefault("context", {})
                        if coding_intent:
                            payload_for_agent.setdefault("coding_intent", coding_intent)
                    elif runtime_agent == "brand_voice":
                        payload_for_agent.setdefault("content", prompt_text)
                        payload_for_agent.setdefault("prompt", prompt_text)
                        payload_for_agent.setdefault("mode", "stakeholder_summary")
                        payload_for_agent.setdefault("tone", "rugged")
                        payload_for_agent.setdefault("audience", "operator")
                    elif runtime_agent == "browser":
                        payload_for_agent.setdefault("prompt", prompt_text)
                        if prompt_text.lower().startswith(("http://", "https://")) and not payload_for_agent.get("url"):
                            payload_for_agent["url"] = prompt_text
                    elif runtime_agent == "task_queue":
                        payload_for_agent.setdefault("prompt", prompt_text)
                    elif runtime_agent == "mammoth_guide":
                        payload_for_agent.setdefault("message", prompt_text)
                    else:
                        if not payload_for_agent.get("topic") and not payload_for_agent.get("prompt") and not payload_for_agent.get("problem"):
                            payload_for_agent["topic"] = prompt_text
                        if runtime_agent == "tutor" and not payload_for_agent.get("prompt"):
                            payload_for_agent["prompt"] = prompt_text
                        if runtime_agent == "reasoning" and not payload_for_agent.get("problem"):
                            payload_for_agent["problem"] = prompt_text
                    if runtime_agent == "planner":
                        payload_for_agent.setdefault("goal", prompt_text)
                    if runtime_agent == "search":
                        payload_for_agent.setdefault("query", prompt_text)
                elif isinstance(payload, dict):
                    payload_for_agent.setdefault("prompt", payload.get("prompt") or payload.get("content") or payload.get("task") or "")
                if runtime_agent == "coding":
                    # Server-forced: non-admins never touch host files, host tests, or the shared vector store.
                    payload_for_agent["host_access"] = _mutation_allowed()
                    payload_for_agent["context"] = dict(payload_for_agent.get("context") or {})
                    payload_for_agent["context"].setdefault("source", prompt_text or payload_for_agent.get("task") or "")
                    payload_for_agent["context"].setdefault("files", payload_for_agent.get("files") or [])
                    if payload_for_agent.get("target"):
                        payload_for_agent["context"].setdefault("target", payload_for_agent.get("target"))
                    if coding_intent:
                        payload_for_agent["context"]["coding_intent"] = coding_intent
                        payload_for_agent["intent"] = coding_intent
                if runtime_agent == "search":
                    # Server-forced: workspace search reads the platform repo, so it is owner/admin-only.
                    payload_for_agent["host_access"] = _mutation_allowed()
                if runtime_agent == "browser":
                    # Server-forced: non-admins can't reach private/metadata addresses or other users' sessions.
                    privileged = _mutation_allowed()
                    payload_for_agent["allow_private_network"] = privileged
                    payload_for_agent["session_scope"] = "" if privileged else f"user:{_current_request_user_id('anonymous')}"
            if runtime_agent in ("research_agent", "research"):
                if not isinstance(payload_for_agent, dict):
                    payload_for_agent = {"prompt": str(payload_for_agent or ""), "intent": str(intent or ""), "context": {}}
                else:
                    payload_for_agent.setdefault("prompt", prompt_text or "")
                    payload_for_agent["intent"] = str(intent or "")
            approval_contract = body.get("approval_contract") if isinstance(body.get("approval_contract"), dict) else {}
            if not approval_contract and isinstance(payload_for_agent, dict) and isinstance(payload_for_agent.get("approval_contract"), dict):
                approval_contract = payload_for_agent.get("approval_contract") or {}
            if approval_mode and runtime_agent in {"brand_voice", "community_engine"} and approval_contract:
                operation = str(approval_contract.get("operation") or f"{runtime_agent}_publish").strip()
                target = str(
                    approval_contract.get("target")
                    or payload_for_agent.get("target")
                    or prompt_text
                    or runtime_agent
                ).strip()
                _think("Previewing approval-aware content", f"operation={operation!r}  target={target!r}")
                raw_result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _with_llm_background(llm_background, registry_run_agent, runtime_agent, payload_for_agent)
                )
                preview = _build_non_coding_approval_preview(operation, payload_for_agent, raw_result)
                approval = _create_approval_record(
                    task_id,
                    agent_id=tracked_agent_id or f"{runtime_agent}_agent",
                    operation=operation,
                    target=target or runtime_agent,
                    preview=preview,
                    payload={**payload_for_agent, "approval_contract": approval_contract},
                    requested_by="user",
                    trace_id=trace_id,
                )
                _upsert_task(
                    task_id,
                    task["title"],
                    status="pending_approval",
                    agent_id=tracked_agent_id,
                    description=prompt_text or f"Approval required for {runtime_agent}",
                    details={"intent": intent, "temperature": temperature, "approval_id": approval["id"], "trace_id": trace_id},
                )
                _append_activity(
                    f"Requested approval for {runtime_agent}",
                    agent_id=tracked_agent_id,
                    task_id=task_id,
                    kind="approval_requested",
                    trace_id=trace_id,
                    details={"approval_id": approval["id"], "target": approval["target"], "trace_id": trace_id},
                )
                _think("Queued for approval", f"approval_id={approval['id']}  operation={operation!r}  target={approval['target']!r}", "warning")
                result = {
                    "status": "pending_approval",
                    "runtime_agent": runtime_agent,
                    "operation": operation,
                    "approval": approval,
                    "preview": preview,
                }
                handled_special_result = True
            if runtime_agent == "custodial":
                from mammoth_os.agents.custodial_agent import CustodialAgent

                custodial_agent = CustodialAgent(router=None, storage_root=str(MAMMOTH_DIR / "custodial"))
                payload_for_agent = dict(payload) if isinstance(payload, dict) else {}
                if prompt_text and not payload_for_agent.get("prompt"):
                    payload_for_agent["prompt"] = prompt_text
                custodial_prompt = prompt_text or str(payload_for_agent.get("prompt") or payload_for_agent.get("topic") or "").strip()
                action = str(
                    payload_for_agent.get("action")
                    or payload_for_agent.get("operation")
                    or custodial_agent._infer_intent(custodial_prompt or json.dumps(payload_for_agent))
                ).strip().lower() or "lifecycle"
                workspace = str(payload_for_agent.get("workspace") or payload_for_agent.get("target") or "").strip() or str(Path.cwd())
                action_payload = dict(payload_for_agent.get("details") or {}) if isinstance(payload_for_agent.get("details"), dict) else {}
                if payload_for_agent.get("snapshot_id"):
                    action_payload["snapshot_id"] = str(payload_for_agent.get("snapshot_id") or "").strip()

                mutation_actions = {"cleanup", "clean", "prune", "restore", "rollback", "snapshot", "checkpoint"}
                if approval_mode and action in mutation_actions:
                    preview_payload = dict(action_payload)
                    preview_payload["dry_run"] = True
                    if action in {"restore", "rollback"} and not preview_payload.get("snapshot_id"):
                        preview_payload["snapshot_id"] = str(payload_for_agent.get("snapshot_id") or "").strip()
                    preview = await custodial_agent.execute_action(action, workspace, preview_payload)
                    if action in {"cleanup", "clean", "prune"}:
                        approval_operation = "custodial_cleanup"
                    elif action in {"restore", "rollback"}:
                        approval_operation = "custodial_restore"
                    else:
                        approval_operation = "custodial_snapshot"
                    approval = _create_approval_record(
                        task_id,
                        agent_id=tracked_agent_id or "custodial_agent",
                        operation=approval_operation,
                        target=workspace,
                        preview=preview,
                        payload={
                            "action": action,
                            "workspace": workspace,
                            "details": action_payload,
                            "snapshot_id": payload_for_agent.get("snapshot_id"),
                        },
                        requested_by="user",
                        trace_id=trace_id,
                    )
                    _upsert_task(
                        task_id,
                        task["title"],
                        status="pending_approval",
                        agent_id=tracked_agent_id,
                        description=prompt_text or f"Approval required for {action}",
                        details={"intent": intent, "temperature": temperature, "approval_id": approval["id"], "trace_id": trace_id},
                    )
                    _append_activity(
                        f"Requested approval for custodial {action}",
                        agent_id=tracked_agent_id,
                        task_id=task_id,
                        kind="approval_requested",
                        trace_id=trace_id,
                        details={"approval_id": approval["id"], "target": approval["target"], "trace_id": trace_id},
                    )
                    _think("Queued for approval", f"approval_id={approval['id']}  action={action!r}  target={approval['target']!r}", "warning")
                    result = {
                        "status": "pending_approval",
                        "runtime_agent": runtime_agent,
                        "operation": action,
                        "approval": approval,
                        "preview": preview,
                    }
                    handled_special_result = True
                else:
                    _think("Executing custodial action", f"action={action!r}  workspace={workspace!r}")
                    raw_result = await custodial_agent.execute_action(action, workspace, action_payload)
                    _think("Custodial action done", f"status={raw_result.get('status','?')!r}  action={raw_result.get('action', action)!r}", "success")
                    result = {
                        "status": raw_result.get("status", "ok"),
                        "runtime_agent": runtime_agent,
                        "operation": action,
                        "output": raw_result,
                    }
                    handled_special_result = True

            if runtime_agent != "custodial" and not handled_special_result:
                _think("Execution loop plan", f"runtime_agent={runtime_agent!r} max_attempts={execution_policy['max_attempts']}")
                attempts: List[Dict[str, Any]] = []
                final_envelope: Dict[str, Any] = {}
                verification: Dict[str, Any] = {"passed": False, "checks": [], "failed_checks": []}
                raw_result: Any = None
                last_failure_detail = ""
                for attempt in range(1, int(execution_policy.get("max_attempts") or 1) + 1):
                    attempt_payload = payload_for_agent
                    if isinstance(payload_for_agent, dict):
                        attempt_payload = dict(payload_for_agent)
                        attempt_payload["execution_contract"] = {
                            "attempt": attempt,
                            "max_attempts": execution_policy["max_attempts"],
                            "required_fields": execution_policy["required_fields"],
                            "previous_failure": last_failure_detail,
                        }
                    _think("Dispatching to agent", f"attempt={attempt} runtime_agent={runtime_agent!r}")
                    raw_result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: _with_llm_background(llm_background, registry_run_agent, runtime_agent, attempt_payload)
                    )
                    final_envelope = _normalize_agent_output(runtime_agent, raw_result)
                    verification = _verify_execution_contract(final_envelope, execution_policy)
                    attempts.append(
                        {
                            "attempt": attempt,
                            "status": final_envelope.get("status"),
                            "summary": final_envelope.get("summary", ""),
                            "passed": verification.get("passed", False),
                            "checks": verification.get("checks", []),
                        }
                    )
                    _think(
                        "Verify step",
                        f"attempt={attempt} passed={verification.get('passed')} status={final_envelope.get('status')!r}",
                        "success" if verification.get("passed") else "warning",
                    )
                    if verification.get("passed"):
                        break
                    if final_envelope.get("status") == "pending_approval":
                        break
                    failed_checks = verification.get("failed_checks") if isinstance(verification.get("failed_checks"), list) else []
                    last_failure_detail = "; ".join(str(item.get("name") or "check_failed") for item in failed_checks if isinstance(item, dict))
                    if attempt < int(execution_policy.get("max_attempts") or 1):
                        _think("Retrying run", f"attempt={attempt + 1} reason={last_failure_detail or 'verification_failed'}", "warning")

                _think("Agent returned", f"type={type(raw_result).__name__}  preview={str(raw_result)[:120]!r}", "success")
                status = "ok" if verification.get("passed") or final_envelope.get("status") == "pending_approval" else "error"
                result = {
                    "status": status,
                    "runtime_agent": runtime_agent,
                    "output": final_envelope.get("output", raw_result),
                    "execution_loop": {
                        "plan": execution_policy,
                        "attempts": attempts,
                        "verification": verification,
                    },
                }
                if runtime_agent == "planner":
                    _p_out = result.get("output") or {}
                    if isinstance(_p_out, dict) and not _p_out.get("tasks"):
                        _p_plan = (_p_out.get("plan") or {})
                        result["output"] = dict(list(_p_out.items()) + [("tasks", _p_plan.get("tasks") or [])])
                # Auto-seed: RAG + ATLAS + Library on any substantial text output
                _auto_out = result.get("output")
                if isinstance(_auto_out, dict):
                    _auto_text = "\n\n".join(filter(None, [
                        str(_auto_out.get("executive_summary") or ""),
                        str(_auto_out.get("findings") or ""),
                        str(_auto_out.get("summary") or ""),
                        str(_auto_out.get("content") or ""),
                        str(_auto_out.get("document") or ""),
                        str(_auto_out.get("report") or ""),
                        str(_auto_out.get("text") or ""),
                    ]))
                    _auto_title = str(_auto_out.get("title") or runtime_agent)
                    _auto_type = str(_auto_out.get("artifact_type") or "document")
                elif isinstance(_auto_out, str):
                    _auto_text, _auto_title, _auto_type = _auto_out, runtime_agent, "document"
                else:
                    _auto_text = ""
                if len(_auto_text) > 80:
                    try:
                        import uuid as _uuid
                        from datetime import datetime as _adt, timezone as _atz
                        _auto_payload = {
                            "id": _uuid.uuid5(_uuid.NAMESPACE_URL, _auto_title).hex,
                            "title": _auto_title,
                            "body": _auto_text[:4000],
                            "artifact_type": _auto_type,
                            "source_url": "",
                            "created_at": _adt.now(_atz.utc).isoformat(),
                        }
                        _auto_record = _normalize_workspace_artifact_record(_auto_payload)
                        if _auto_record:
                            _auto_state = _load_atlas_state()
                            _auto_arts = _normalize_workspace_artifact_collection(_auto_state.get("workspace_artifacts"))
                            _auto_arts = [x for x in _auto_arts if x.get("id") != _auto_record["id"]]
                            _auto_arts.insert(0, _auto_record)
                            _auto_state["workspace_artifacts"] = _auto_arts[:120]
                            _auto_state["updated_at"] = _adt.now(_atz.utc).isoformat()
                            _save_atlas_state(_auto_state)
                    except Exception as _e:
                        import logging; logging.getLogger("mammoth").warning("Library auto-save failed: %s", _e)
                attach_reasoning = runtime_agent == "tutor" and (
                    intent == "lesson_coaching" or (intent == "grade_submission" and _is_failure_payload(final_envelope.get("output", raw_result)))
                )
                if attach_reasoning:
                    if _is_failure_payload(final_envelope.get("output", raw_result)):
                        _think("Tutor failure detected", "Preparing reasoning guidance for the learner", "warning")
                    else:
                        _think("Coaching extension", "Attaching Socratic reasoning guidance", "info")
                    reasoning_payload = {
                        "problem": prompt_text or "Explain the tutoring failure and offer a micro-lesson.",
                        "context": {
                            "intent": intent,
                            "prompt": prompt_text,
                            "tutor_result": final_envelope.get("output", raw_result),
                            "mode": "coach" if intent == "lesson_coaching" else "tutor_hint",
                        },
                        "mode": "coach" if intent == "lesson_coaching" else "tutor_hint",
                    }
                    reasoning_result = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: _with_llm_background(llm_background, registry_run_agent, "reasoning", reasoning_payload)
                    )
                    _think("Reasoning guidance attached", f"preview={str(reasoning_result)[:120]!r}", "success")
                    result["reasoning"] = reasoning_result
        else:
            _think("Falling back to CortexRouter", f"intent={intent!r}  no matching AGENTS key", "warning")
            from mammoth_os.cortex.router import CortexRouter
            router = CortexRouter()
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _with_llm_background(llm_background, router.route, intent, payload)
            )
            _think("CortexRouter returned", f"status={result.get('status','?')!r}  preview={str(result)[:120]!r}", "success")

        if manifest:
            await asyncio.sleep(1.2)
            manifest.status = AgentStatus.IDLE
            manifest.last_heartbeat = datetime.now(timezone.utc)
            manifest.metadata["last_intent"] = intent
            manifest.metadata["last_run_at"] = datetime.now(timezone.utc).isoformat()

        if result.get("status") == "pending_approval":
            task_status = "pending_approval"
        elif result.get("status") == "error":
            task_status = "failed"
        else:
            task_status = "completed"
        _upsert_task(
            task_id,
            task["title"],
            status=task_status,
            agent_id=tracked_agent_id,
            description=prompt_text or "Agent execution completed",
            details={"intent": intent, "temperature": temperature, "result": str(result)[:1000]},
        )
        if task_status == "completed":
            _append_activity(
                f"Completed task for {intent or 'agent'}",
                agent_id=tracked_agent_id,
                task_id=task_id,
                kind="task_completed",
                trace_id=trace_id,
                details={"result": str(result)[:1000], "trace_id": trace_id},
            )
        elif task_status == "failed":
            _append_activity(
                f"Failed task for {intent or 'agent'}",
                agent_id=tracked_agent_id,
                task_id=task_id,
                kind="task_failed",
                trace_id=trace_id,
                details={"result": str(result)[:1000], "trace_id": trace_id},
            )

        _think("Run complete", f"task_status={task_status!r}", "success")
        # Score long_form_research on output quality, not temperature
        _lf_out = result.get("output") if isinstance(result, dict) else {}
        _lf_out = _lf_out if isinstance(_lf_out, dict) else {}
        _is_longform = (
            intent == "research_long_form"
            or _lf_out.get("artifact_type") == "long_form_research"
        )
        if _is_longform:
            if _lf_out.get("docx_filename"):
                _record_generated_doc_owner(str(_lf_out.get("docx_filename")))
            _secs = _lf_out.get("sections") or []
            _wc = int(_lf_out.get("word_count") or 0)
            _docx = bool(_lf_out.get("docx_filename"))
            _run_confidence = round(min(0.95,
                0.50
                + (0.20 if len(_secs) >= 6 else len(_secs) * 0.03)
                + (0.15 if _wc >= 4000 else _wc / 4000 * 0.15)
                + (0.10 if _docx else 0.0)
            ), 3)
        else:
            _run_confidence = round(1.0 - temperature, 3)
        response = {
            "status": "ok",
            "result": result,
            "intent": intent,
            "agent_id": tracked_agent_id,
            "temperature": temperature,
            "task_id": task_id,
            "trace_id": trace_id,
            "contract_version": "v2",
            "preflight": preflight,
            "runtime_notice": build_runtime_notice(runtime_status, trace_id=trace_id, agent_id=tracked_agent_id or "", context="run_agent"),
            "thought_steps": thought_steps,
            "provider": runtime_agent or "unknown",
            "confidence": _run_confidence,
            "citations": [],  # Agent runs typically don't have citations unless specified
            "contradictions": [],
        }
        # Determine response type from runtime_agent
        response_type = "coding" if runtime_agent == "coding" else "general"
        return _wrap_response_with_trust(response, endpoint="/api/run", response_type=response_type)
    except Exception as e:
        if manifest:
            manifest.status = AgentStatus.ERROR
            manifest.last_heartbeat = datetime.now(timezone.utc)
            manifest.metadata["last_error"] = str(e)

        _upsert_task(
            task_id,
            task["title"],
            status="failed",
            agent_id=tracked_agent_id,
            description=prompt_text or "Agent execution failed",
            details={"intent": intent, "temperature": temperature, "error": str(e)[:1000]},
        )
        _append_activity(
            f"Failed task for {intent or 'agent'}",
            agent_id=tracked_agent_id,
            task_id=task_id,
            kind="task_failed",
            trace_id=trace_id,
            details={"error": str(e)[:1000], "trace_id": trace_id},
        )

        _think("Run failed", str(e)[:200], "error")
        return {
            "status": "error",
            "error": str(e),
            "intent": intent,
            "agent_id": tracked_agent_id,
            "task_id": task_id,
            "trace_id": trace_id,
            "contract_version": "v2",
            "preflight": preflight,
            "runtime_notice": build_runtime_notice(runtime_status, trace_id=trace_id, agent_id=tracked_agent_id or "", context="run_agent"),
            "thought_steps": thought_steps,
        }

@app.get("/api/flashcards")
async def get_flashcards():
    state = _load_atlas_state()
    lesson_id = str(state.get("lesson_id") or "").strip()
    lesson_cards = _flashcards_for_lesson(state, lesson_id) if lesson_id else []
    stored_cards = _latest_stored_flashcards(state, limit=12)
    cards = lesson_cards or stored_cards or _build_lesson_flashcards(state)
    ui_cards = _flashcards_to_ui_cards(cards)
    topic = str(state.get("topic") or (state.get("current_lesson") or {}).get("title") or "").strip()
    return {
        "status": "ok",
        "cards": ui_cards,
        "lesson_id": lesson_id or None,
        "topic": topic or None,
    }

@app.post("/api/flashcards")
async def create_flashcards(body: Dict[str, Any]):
    cards_input = body.get("cards")
    normalized_cards = _normalize_flashcard_list(cards_input)
    if not normalized_cards:
        return JSONResponse(
            {"status": "error", "error": "cards must include at least one item with front/back (or q/a)."},
            status_code=400,
        )

    state = _load_atlas_state()
    lesson_id = str(body.get("lesson_id") or state.get("lesson_id") or "").strip()
    topic = str(
        body.get("topic")
        or body.get("lesson_title")
        or (state.get("current_lesson") or {}).get("title")
        or state.get("topic")
        or ""
    ).strip()
    payload = {
        "cards": normalized_cards,
        "topic": topic,
        "generated_by": str(body.get("generated_by") or "atlas").strip() or "atlas",
    }
    _append_study_aid(
        state,
        "flashcards",
        payload,
        lesson_id=lesson_id,
        lesson_title=topic,
    )
    _save_atlas_state(state)
    return {
        "status": "ok",
        "count": len(normalized_cards),
        "cards": _flashcards_to_ui_cards(normalized_cards),
        "lesson_id": lesson_id or None,
        "topic": topic or None,
    }

@app.get("/api/memory")
async def get_memory_entries(request: Request, limit: int = 50, memory_type: Optional[str] = None):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = str(user.get("id") or "local")
    account_id = _active_account_id(_load_atlas_state())
    entries = _MEMORY_ENGINE._entries
    entries = [
        e
        for e in entries
        if str((e.get("metadata") or {}).get("user_id") or "") == uid
        and _normalize_account_id((e.get("metadata") or {}).get("account_id") or "default") == account_id
    ]
    if memory_type:
        entries = [e for e in entries if e.get("memory_type") == memory_type]
    recent = entries[-limit:] if len(entries) > limit else entries
    recent = list(reversed(recent))
    return {
        "status": "ok",
        "total": len(entries),
        "entries": recent,
        "memory_types": list({e.get("memory_type", "semantic") for e in entries}),
    }

@app.post("/api/memory/search")
async def search_memory(request: Request, body: Dict[str, Any]):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = str(user.get("id") or "local")
    account_id = _active_account_id(_load_atlas_state())
    query = str(body.get("query") or "").strip()
    top_k = int(body.get("top_k") or 10)
    memory_type = body.get("memory_type")
    if not query:
        return {"status": "error", "error": "query is required"}
    raw_results = _MEMORY_ENGINE.retrieve(query, top_k=top_k * 5, memory_type=memory_type)
    if inspect.isawaitable(raw_results):
        raw_results = await raw_results
    results = [
        r for r in (raw_results or [])
        if str((r.get("metadata") or {}).get("user_id") or "") == uid
        and _normalize_account_id((r.get("metadata") or {}).get("account_id") or "default") == account_id
    ][:top_k]
    return {"status": "ok", "query": query, "results": results, "count": len(results)}

@app.post("/api/memory")
async def store_memory_entry(request: Request, body: Dict[str, Any]):
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    uid = str(user.get("id") or "local")
    account_id = _active_account_id(_load_atlas_state())
    content = str(body.get("content") or "").strip()
    if not content:
        return {"status": "error", "error": "content is required"}
    memory_type = str(body.get("memory_type") or "semantic")
    metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
    metadata = {**metadata, "user_id": uid, "account_id": account_id}
    try:
        entry_id = _MEMORY_ENGINE.store(content, memory_type=memory_type, metadata=metadata)
        if inspect.isawaitable(entry_id):
            entry_id = await entry_id
        return {"status": "ok", "id": entry_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.get("/api/approvals")
async def get_approvals():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _load_approvals()

@app.post("/api/approvals/{record_id}/approve")
async def approve_record_route(record_id: str):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _approve_record(record_id)

@app.get("/api/snapshots")
async def get_snapshots():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _load_snapshots()

@app.post("/api/snapshots/{snapshot_id}/restore")
async def restore_snapshot_route(snapshot_id: str):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return _restore_snapshot(snapshot_id)

@app.get("/api/release-readiness")
async def get_release_readiness():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    return await _release_readiness_snapshot()

@app.post("/api/terminal/exec")
async def terminal_exec(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    cmd = str(body.get("cmd", "")).strip()
    if not cmd:
        return {"stdout": "", "stderr": "No command provided.", "exit_code": 1}
    if not _is_allowed(cmd):
        _append_audit_event(
            kind="terminal_exec_denied",
            message="Terminal command blocked by allow-list",
            details={"cmd": cmd},
            source="terminal",
            actor="user",
        )
        return {
            "stdout": "",
            "stderr": f"Not in allow-list: {cmd}\nAllowed prefixes: {', '.join(sorted(ALLOW_PREFIXES))}",
            "exit_code": 1,
        }
    result = await _execute_terminal_command(cmd)
    _append_audit_event(
        kind="terminal_exec",
        message="Terminal command executed",
        details={"cmd": cmd, "exit_code": result["exit_code"]},
        source="terminal",
        actor="user",
    )
    return {
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "exit_code": result["exit_code"],
        "cwd": result.get("cwd", ""),
        "resolved": result.get("resolved", cmd),
        "timeout_seconds": result.get("timeout_seconds"),
    }

@app.get("/api/diagnostics/export")
async def export_diagnostics_snapshot():
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    release = await _release_readiness_snapshot()
    payload = {
        "status": "ok",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "release_readiness": release,
        "health": await get_health(),
        "entitlements": await get_entitlements(),
        "account_profile": await get_account_profile(),
        "activity": _load_activity_events()[-50:],
        "tasks": _load_tasks()[-50:],
        "approvals": _load_approvals()[-50:],
        "audit": _load_audit_log()[-100:],
    }
    json_payload = json.dumps(payload, indent=2)
    return PlainTextResponse(
        content=json_payload,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="mammoth-diagnostics-{datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}.json"'},
    )

@app.websocket("/ws/terminal")
async def terminal_ws(ws: WebSocket):
    if _AUTH_REQUIRED:
        token = str(ws.query_params.get("access_token") or "").strip()
        user = _resolve_supabase_user(token)
        if user is None or not user.get("is_admin"):
            await ws.close(code=1008)
            return
    await ws.accept()
    await ws.send_json({"line": "MammothOS Terminal ready. Type a command.", "type": "stdout"})
    try:
        while True:
            data = await ws.receive_json()
            cmd = data.get("cmd", "").strip()
            if not cmd:
                continue

            if not _is_allowed(cmd):
                await ws.send_json({"line": f"Not in allow-list: {cmd}", "type": "stderr"})
                await ws.send_json({"line": f"  Allowed prefixes: {', '.join(sorted(ALLOW_PREFIXES))}", "type": "stderr"})
                await ws.send_json({"line": f"[exit 1]", "type": "exit", "code": 1})
                continue

            await ws.send_json({"line": f"$ {cmd}", "type": "cmd"})
            result = await _execute_terminal_command(cmd)
            await ws.send_json({"line": f"[cwd] {result['cwd']}", "type": "stdout"})
            if result.get("stdout"):
                for line in result["stdout"].splitlines():
                    if line.strip():
                        await ws.send_json({"line": line, "type": "stdout"})
            if result.get("stderr"):
                for line in result["stderr"].splitlines():
                    if line.strip():
                        await ws.send_json({"line": line, "type": "stderr"})
            await ws.send_json({"line": f"[exit {result['exit_code']}]", "type": "exit", "code": result["exit_code"]})

    except WebSocketDisconnect:
        pass

@app.get("/api/runtime/execution-log")
async def get_execution_log(request: Request, limit: int = 50):
    """Phase 4: return recent agent/tool execution events for live runtime awareness."""
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)
    is_admin = user.get("is_admin", False)
    uid = user.get("id", "local")
    log = _load_execution_log()
    # Non-admins see only their own events
    if not is_admin:
        log = [e for e in log if e.get("user_id") in {uid, "system", "local"}]
    return {"status": "ok", "events": list(reversed(log[-limit:]))}

@app.get("/api/runtime/context-snapshot")
async def get_runtime_context_snapshot(request: Request):
    """Phase 4: return full live runtime awareness context for agents."""
    user = await _require_auth_user(request)
    if user is None:
        return JSONResponse({"status": "unauthorized"}, status_code=401)

    try:
        repo_ctx = _build_repo_context_snapshot()
    except Exception:
        repo_ctx = {}

    recent_events = list(reversed(_load_execution_log()[-10:]))
    state = _load_atlas_state()
    usage = _current_usage_snapshot_from_state(state)

    return {
        "status": "ok",
        "snapshot": {
            "ts": datetime.now(timezone.utc).isoformat(),
            "repo": repo_ctx,
            "recent_executions": recent_events,
            "usage": usage,
            "providers": {
                "openai": bool(os.getenv("OPENAI_API_KEY")),
                "deepseek": bool(os.getenv("DEEPSEEK_API_KEY")),
            },
            "uptime_seconds": int(time.time() - _START_TIME),
        },
    }

