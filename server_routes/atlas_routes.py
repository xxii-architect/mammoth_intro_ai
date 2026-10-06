# Route fragment loaded by api_server._load_route_fragments().
# Not importable on its own: handlers execute in api_server globals, so keep helpers there.

@app.post("/agent/atlas/run")
async def run_atlas_agent_endpoint(payload: Any):
    return await _dispatch_http_agent("atlas", payload)

@app.get("/api/atlas/status")
async def atlas_status():
    state = _load_atlas_state()
    _hydrate_learner_state(state, user_id=_atlas_user_id(state))
    _sync_resume_packet(state)
    return _decorate_atlas_state(state)

@app.get("/api/atlas/modules")
async def atlas_modules():
    state = _load_atlas_state()
    active_track = _resolve_module_track(state.get("module_id"), state.get("topic"))
    return {
        "status": "ok",
        "modules": _atlas_module_catalog(),
        "active_module": _serialize_module_track(active_track),
    }

@app.get("/api/atlas/library")
async def atlas_library():
    state = _load_atlas_state()
    _hydrate_learner_state(state, user_id=_atlas_user_id(state))
    return await _build_atlas_library_snapshot(state)

@app.get("/api/atlas/learner")
async def atlas_learner():
    state = _load_atlas_state()
    learner_state = _hydrate_learner_state(state, user_id=_atlas_user_id(state))
    return {"status": "ok", "learner_model": learner_state, "learner_context": state.get("learner_context")}

@app.post("/api/atlas/onboard")
async def atlas_onboard(body: Dict[str, Any]):
    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        task_id = f"atlas-onboard-{uuid.uuid4().hex[:8]}"
        preview = _build_operation_preview("atlas_onboard_update", {"onboarding": body})
        approval = _create_approval_record(
            task_id,
            agent_id="tutor_agent",
            operation="atlas_onboard_update",
            target="atlas/onboarding",
            preview=preview,
            payload={"onboarding": body},
            requested_by="user",
        )
        _upsert_task(
            task_id,
            "approval:atlas_onboard_update",
            status="pending_approval",
            agent_id="tutor_agent",
            description="ATLAS onboarding profile update pending approval",
            details={"approval_id": approval["id"]},
        )
        _append_activity(
            "ATLAS onboarding update queued for approval",
            agent_id="tutor_agent",
            task_id=task_id,
            kind="approval_requested",
            details={"approval_id": approval["id"]},
        )
        return {"status": "ok", "approval": approval, "preview": preview}
    try:
        return _apply_atlas_onboarding_update(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/atlas/learner/reset")
async def atlas_learner_reset(body: Optional[Dict[str, Any]] = None):
    body = body or {}
    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        task_id = f"atlas-learner-reset-{uuid.uuid4().hex[:8]}"
        preview = _build_operation_preview("atlas_learner_reset", {})
        approval = _create_approval_record(
            task_id,
            agent_id="tutor_agent",
            operation="atlas_learner_reset",
            target="atlas/learner",
            preview=preview,
            payload={},
            requested_by="user",
        )
        _upsert_task(
            task_id,
            "approval:atlas_learner_reset",
            status="pending_approval",
            agent_id="tutor_agent",
            description="ATLAS learner reset pending approval",
            details={"approval_id": approval["id"]},
        )
        _append_activity(
            "ATLAS learner reset queued for approval",
            agent_id="tutor_agent",
            task_id=task_id,
            kind="approval_requested",
            details={"approval_id": approval["id"]},
        )
        return {"status": "ok", "approval": approval, "preview": preview}
    return _apply_atlas_learner_reset()

@app.post("/api/atlas/lesson")
async def atlas_lesson(body: Dict[str, Any]):
    requested_topic = str(body.get("topic") or "").strip()
    module_track = _resolve_module_track(body.get("module_id"), requested_topic)
    topic = requested_topic or str((module_track or {}).get("topic") or "Python basics")
    curriculum_topic = _compose_module_curriculum_topic(topic, module_track)
    try:
        from mammoth_os.atlas_session import ATLASSession
        state = _load_atlas_state()
        learner_user_id = _atlas_user_id(state)
        session = ATLASSession(user_id=learner_user_id)
        learner_context = state.get("learner_context") or {}
        if not learner_context:
            _hydrate_learner_state(state, user_id=learner_user_id)
            learner_context = state.get("learner_context") or {}
        lesson_plan = build_lesson_plan(state, topic)
        difficulty = str(lesson_plan.get("difficulty") or learner_context.get("recommended_difficulty") or "beginner").strip().lower() or "beginner"
        curriculum_topic = _compose_module_curriculum_topic(topic, module_track, difficulty)
        if module_track:
            lesson_plan["module_track"] = _serialize_module_track(module_track)
            lesson_plan["curriculum_topic"] = curriculum_topic
        learner_context = {**learner_context, "lesson_plan": lesson_plan, "recommended_difficulty": difficulty}
        if module_track:
            learner_context["module_track"] = _serialize_module_track(module_track)
        difficulty = str(lesson_plan.get("difficulty") or learner_context.get("recommended_difficulty") or "beginner").strip().lower() or "beginner"
        exercise = await asyncio.get_event_loop().run_in_executor(
            None, lambda: session.start_lesson(curriculum_topic, difficulty=difficulty, learner_context=learner_context)
        )
        session.current_lesson = _decorate_lesson_for_module_track(session.current_lesson, module_track)
        exercise = _decorate_exercise_for_module_track(exercise, session.current_lesson, module_track)
        state.update({
            "status":           "active",
            "topic":            topic,
            "curriculum_topic": curriculum_topic,
            "current_exercise": exercise,
            "curriculum":       session.curriculum,
            "current_lesson":   session.current_lesson,
            "curriculum_id":    session._curriculum_id,
            "curriculum_origin": "generated",
            "lesson_id":        session._lesson_id,
            "lesson_plan":      lesson_plan,
            "module_id":        (module_track or {}).get("id"),
            "active_module":    _serialize_module_track(module_track),
            "updated_at":       datetime.now(timezone.utc).isoformat(),
        })
        _hydrate_learner_state(state, user_id=learner_user_id)
        _append_lesson_history(state, session.current_lesson or {}, exercise or {})
        tutor_delivery.touch_lesson(_lesson_telemetry(state), str(state.get("lesson_id") or ""))
        _attach_delivery_state(state)
        _sync_resume_packet(state, state.get("lesson_id"))
        _save_atlas_state(state)
        _append_audit_event(
            kind="atlas_lesson",
            message="ATLAS lesson started",
            details={"topic": topic, "difficulty": difficulty, "module_id": (module_track or {}).get("id")},
            source="atlas",
            actor="learner",
        )
        return {
            "status": "ok",
            "exercise": exercise,
            "learner_context": state.get("learner_context"),
            "active_module": _serialize_module_track(module_track),
            "curriculum_topic": curriculum_topic,
            "lesson_manifest": state.get("lesson_manifest"),
        }
    except Exception:
        logging.getLogger("mammoth.atlas").exception("Could not prepare a teaching-ready lesson")
        raise HTTPException(status_code=503, detail="Could not complete lesson preparation. Check your current lesson before retrying. Use the Curriculum learning agent to review drafts.")

@app.post("/api/atlas/submit")
async def atlas_submit(body: Dict[str, Any]):
    code = body.get("code", "")
    try:
        state = _load_atlas_state()
        learner_user_id = _atlas_user_id(state)
        from mammoth_os.atlas_session import ATLASSession
        session = ATLASSession(user_id=learner_user_id)
        session.curriculum       = state.get("curriculum")
        session.current_lesson   = state.get("current_lesson")
        session.current_exercise = state.get("current_exercise")
        session._curriculum_id   = state.get("curriculum_id")
        session._lesson_id       = state.get("lesson_id")
        current_exercise = state.get("current_exercise") or {}
        current_lesson = state.get("current_lesson") or {}
        active_track = _resolve_module_track(state.get("module_id"), state.get("topic"))
        submission_mode = str(current_exercise.get("submission_mode") or "").strip().lower() or (
            "code" if str(current_exercise.get("lesson_type") or "code").strip().lower() == "code" else "text"
        )

        if submission_mode == "text":
            response_text = str(body.get("response") or code or "").strip()
            from mammoth_os.lesson_assessment import assess_text_response
            try:
                result = await assess_text_response(response_text, current_lesson, current_exercise, str(state.get("lesson_id") or ""))
            except Exception:
                logging.getLogger("mammoth.atlas").exception("Lesson-grounded assessment unavailable; using labeled coverage feedback")
                result = _evaluate_text_submission(
                    response_text, lesson=current_lesson, exercise=current_exercise,
                    track=active_track, lesson_id=str(state.get("lesson_id") or ""),
                )
        else:
            files = {"solution.py": code}
            result = await session.submit(files)

        telemetry_entry = tutor_delivery.record_attempt(
            _lesson_telemetry(state), str(state.get("lesson_id") or ""), result
        )
        stall = tutor_delivery.stall_signal(telemetry_entry)
        if isinstance(result, dict):
            result["stall"] = stall
        state["last_submission"] = result
        _hydrate_learner_state(
            state,
            user_id=learner_user_id,
            lesson=state.get("current_lesson") or {},
            exercise=state.get("current_exercise") or {},
            result=result,
            topic=state.get("topic"),
            metadata={"error_fingerprint": None},
        )
        learner_context = state.get("learner_context") or {}
        adaptive_feedback = _build_submit_adaptation(learner_context, result)
        _record_submission_on_history(state, result)
        regenerated_exercise = None
        if (
            bool(body.get("regenerate_on_fail"))
            and not bool(result.get("passed"))
            and adaptive_feedback.get("remediation_needed")
        ):
            regenerated_exercise = _regenerate_current_exercise(
                state,
                reason="remediation_after_failed_submission",
            )
        _sync_resume_packet(state, state.get("lesson_id"))
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_atlas_state(state)
        try:
            _topic = str(state.get("topic") or "")
            _lesson_title = str(current_lesson.get("title") or current_lesson.get("objective") or "lesson")
            _outcome_label = "coverage checked (not verified mastery)" if result.get("mastery_evidence") is False else "passed" if bool(result.get("passed")) else "attempted"
            store_result = _MEMORY_ENGINE.store(
                f"Lesson '{_lesson_title}' on topic '{_topic}': {_outcome_label}. Score: {result.get('score') or 0}.",
                memory_type="atlas_outcome",
                metadata={
                    "lesson_id": str(state.get("lesson_id") or ""),
                    "topic": _topic,
                    "passed": bool(result.get("passed")),
                    "score": result.get("score"),
                    "user_id": learner_user_id,
                },
            )
            if inspect.isawaitable(store_result):
                await store_result
        except Exception:
            pass
        _append_audit_event(
            kind="atlas_submit",
            message="ATLAS submission evaluated",
            details={"passed": bool(result.get("passed")), "score": result.get("score")},
            source="atlas",
            actor="learner",
        )
        response = {
            "status": "ok",
            "result": result,
            "learner_context": state.get("learner_context"),
            "adaptive_feedback": adaptive_feedback,
            "current_exercise": state.get("current_exercise"),
            "regenerated_exercise": regenerated_exercise,
            "stall": stall,
            "provider": "atlas-tutor",
            "confidence": 0.85,  # ATLAS has high confidence in structured exercises
            "citations": ["Exercise library", "Curriculum standards"],
            "contradictions": [],
        }
        return _wrap_response_with_trust(response, endpoint="/api/atlas/submit", response_type="tutor")
    except Exception as e:
        return {"status": "error", "error": str(e)}

@app.post("/api/atlas/next")
async def atlas_next(body: Optional[Dict[str, Any]] = None):
    body = body if isinstance(body, dict) else {}
    state = _load_atlas_state()
    curriculum = state.get("curriculum", {})
    modules = curriculum.get("modules", []) if isinstance(curriculum, dict) else []
    lesson_id = str(state.get("lesson_id") or "").strip()
    if not lesson_id:
        return {"status": "ok", "message": "No active lesson to advance from."}

    history_entry = _matching_history_entry(state, lesson_id) or {}
    history_submission = history_entry.get("last_submission") if isinstance(history_entry.get("last_submission"), dict) else None
    gate = tutor_delivery.comprehension_gate(
        lesson_id=lesson_id,
        exercise=state.get("current_exercise") if isinstance(state.get("current_exercise"), dict) else {},
        telemetry_entry=_lesson_telemetry(state).get(lesson_id),
        history_submission=history_submission,
        override=bool(body.get("override")),
    )
    if not gate.get("allowed"):
        return {"status": "gated", "lesson_id": lesson_id, "gate": gate}

    next_lesson = None
    next_module = None
    for mod_idx, mod in enumerate(modules):
        lessons = mod.get("lessons", []) if isinstance(mod, dict) else []
        for i, lesson in enumerate(lessons):
            if str(lesson.get("lesson_id") or "").strip() != lesson_id:
                continue
            if i + 1 < len(lessons):
                next_lesson = lessons[i + 1]
                next_module = mod
                break
            if mod_idx + 1 < len(modules):
                next_module = modules[mod_idx + 1]
                next_lessons = next_module.get("lessons", []) if isinstance(next_module, dict) else []
                if next_lessons:
                    next_lesson = next_lessons[0]
                break
            return {"status": "ok", "message": "No more lessons in curriculum."}
        if next_lesson is not None:
            break

    if next_lesson is None:
        return {"status": "ok", "message": "No more lessons in current module"}

    next_module_id = str((next_module or {}).get("module_id") or (next_module or {}).get("id") or state.get("module_id") or "").strip()
    active_track = None if state.get("curriculum_origin") == "saved" else _resolve_module_track(next_module_id, state.get("topic"))
    if active_track is None and state.get("curriculum_origin") != "saved":
        active_track = _resolve_module_track((next_module or {}).get("title"), state.get("topic"))
    next_lesson = _decorate_lesson_for_module_track(next_lesson, active_track)

    next_active_module = _serialize_module_track(active_track) or {
        "id": next_module_id,
        "label": str((next_module or {}).get("title") or "Next module").strip(),
        "topic": str(state.get("topic") or "").strip(),
        "summary": "",
        "category": "",
        "icon": "",
        "lesson_type": "knowledge",
        "outcomes": [],
        "operator_note": "",
    }
    try:
        from mammoth_os.exercise_generator import generate_exercises_for_lesson
        _hydrate_learner_state(state, user_id=_atlas_user_id(state))
        context = state.get("learner_context") or {}
        plan = build_lesson_plan(state, state.get("topic"))
        context = {**context, "recommended_difficulty": plan["difficulty"], "lesson_plan": plan}
        generated = await asyncio.get_event_loop().run_in_executor(
            None, lambda: generate_exercises_for_lesson(next_lesson, count=1, difficulty=context.get("recommended_difficulty", "beginner"), learner_context=context)
        )
        if not generated:
            raise RuntimeError("No exercise generated")
        next_exercise = _decorate_exercise_for_module_track(generated[0], next_lesson, active_track)
    except Exception:
        logging.getLogger("mammoth.atlas").exception("Could not prepare next lesson exercise")
        raise HTTPException(status_code=503, detail="Could not prepare the next exercise. Your current lesson was not changed.")
    state["current_lesson"] = next_lesson
    state["lesson_id"] = next_lesson["lesson_id"]
    state["module_id"] = next_module_id or state.get("module_id")
    state["active_module"] = next_active_module
    state["current_exercise"] = next_exercise
    state["last_submission"] = None
    state["lesson_plan"] = build_lesson_plan(state, state.get("topic"))

    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _append_lesson_history(state, next_lesson, state.get("current_exercise") or {})
    tutor_delivery.touch_lesson(_lesson_telemetry(state), str(state.get("lesson_id") or ""))
    _attach_delivery_state(state)
    _sync_resume_packet(state, state.get("lesson_id"))
    _save_atlas_state(state)
    if gate.get("overridden"):
        _append_audit_event(
            kind="atlas_gate_override",
            message="Learner advanced past an unpassed exercise",
            details={"from_lesson_id": lesson_id, "reason": gate.get("reason")},
            source="atlas",
            actor="learner",
        )
    return {
        "status": "ok",
        "lesson": next_lesson,
        "exercise": state.get("current_exercise"),
        "module_id": state.get("module_id"),
        "active_module": state.get("active_module"),
        "lesson_id": state.get("lesson_id"),
        "lesson_manifest": state.get("lesson_manifest"),
        "gate": gate,
    }

@app.post("/api/atlas/back")
async def atlas_back():
    state = _load_atlas_state()
    history = state.get("lesson_history") or []
    if not isinstance(history, list) or len(history) < 2:
        return {"status": "ok", "message": "No previous lesson to return to."}
    history.pop()
    previous = history[-1]
    state["lesson_history"] = history
    state["current_lesson"] = previous.get("lesson") or {}
    state["lesson_id"] = previous.get("lesson_id")
    state["current_exercise"] = previous.get("exercise") or {}
    if isinstance(previous.get("last_submission"), dict):
        state["last_submission"] = previous.get("last_submission")
    _sync_resume_packet(state, state.get("lesson_id"))
    _attach_delivery_state(state)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_atlas_state(state)
    return {
        "status": "ok",
        "lesson": state.get("current_lesson"),
        "exercise": state.get("current_exercise"),
        "resume_packet": state.get("resume_packet"),
        "lesson_manifest": state.get("lesson_manifest"),
    }


@app.get("/api/atlas/agents")
async def atlas_learning_agents():
    blocked = _require_signed_in_api()
    if blocked is not None:
        return blocked
    allowed = {"tutor_agent", "curriculum_agent", "research_agent", "reflection_agent", "coding_agent", "browser_agent"}
    if not _agent_registry_ok:
        return JSONResponse({"status": "error", "error": "The learning agent registry is unavailable."}, status_code=503)
    try:
        manifests = await agent_registry.list_agents()
    except Exception:
        logging.getLogger("mammoth.atlas").exception("Could not load learning agent catalog")
        return JSONResponse({"status": "error", "error": "Could not load the learning agent catalog."}, status_code=503)
    return {"status": "ok", "agents": [
        {
            "id": manifest.agent_id,
            "name": manifest.name,
            "status": manifest.status.value if hasattr(manifest.status, "value") else str(manifest.status),
            "capabilities": manifest.capabilities,
        }
        for manifest in manifests if manifest.agent_id in allowed
    ]}


@app.get("/api/atlas/curricula")
async def atlas_curricula():
    blocked = _require_signed_in_api()
    if blocked is not None:
        return blocked
    from mammoth_os.curriculum_library import list_curricula
    try:
        return {"status": "ok", "curricula": list_curricula(_curriculum_library_path())}
    except (OSError, ValueError):
        logging.getLogger("mammoth.atlas").exception("Could not read curriculum library")
        raise HTTPException(status_code=503, detail="Could not read your curriculum library.")


@app.post("/api/atlas/curricula")
async def atlas_save_curriculum(body: Dict[str, Any]):
    blocked = _require_signed_in_api()
    if blocked is not None:
        return blocked
    from mammoth_os.curriculum_library import prepare_curriculum, save_curriculum, list_curricula
    try:
        course = prepare_curriculum(body.get("curriculum"))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        list_curricula(_curriculum_library_path())
    except (OSError, ValueError):
        logging.getLogger("mammoth.atlas").exception("Could not read curriculum library before save")
        raise HTTPException(status_code=503, detail="Could not read your curriculum library.")
    try:
        record = save_curriculum(_curriculum_library_path(), course)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OSError:
        logging.getLogger("mammoth.atlas").exception("Could not save curriculum")
        raise HTTPException(status_code=503, detail="Could not save your curriculum.")
    return {"status": "ok", **record}


@app.post("/api/atlas/curricula/start")
async def atlas_start_curriculum(body: Dict[str, Any]):
    blocked = _require_signed_in_api()
    if blocked is not None:
        return blocked
    from mammoth_os.atlas_session import ATLASSession
    from mammoth_os.curriculum_library import list_curricula, prepare_curriculum
    curriculum_id = str(body.get("curriculum_id") or "").strip()
    if not curriculum_id:
        raise HTTPException(status_code=400, detail="Choose a saved curriculum.")
    try:
        records = list_curricula(_curriculum_library_path())
    except (OSError, ValueError):
        logging.getLogger("mammoth.atlas").exception("Could not read curriculum for activation")
        raise HTTPException(status_code=503, detail="Could not read your curriculum library.")
    record = next((item for item in records if item["curriculum"].get("curriculum_id") == curriculum_id), None)
    if record is None:
        raise HTTPException(status_code=404, detail="Curriculum not found in your library.")
    try:
        course = prepare_curriculum(record["curriculum"])
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Saved curriculum needs review.") from exc
    if not course["quality"]["ready"]:
        return JSONResponse({"status": "draft", "error": "This curriculum needs authored lessons before it can start.", "quality": course["quality"]}, status_code=409)
    state = _load_atlas_state()
    user_id = _atlas_user_id(state)
    _hydrate_learner_state(state, user_id=user_id)
    context = state.get("learner_context") or {}
    session = ATLASSession(user_id=user_id)
    plan = build_lesson_plan(state, course["subject"])
    context = {**context, "recommended_difficulty": plan["difficulty"], "lesson_plan": plan}
    try:
        exercise = await asyncio.get_event_loop().run_in_executor(
            None, lambda: session.start_curriculum(course, difficulty=context.get("recommended_difficulty", "beginner"), learner_context=context)
        )
    except (ValueError, RuntimeError):
        logging.getLogger("mammoth.atlas").exception("Could not activate curriculum exercise")
        raise HTTPException(status_code=503, detail="Could not prepare the first exercise. Your active lesson was not changed.")
    state.update({
        "status": "active", "topic": course["subject"], "curriculum_topic": course["subject"],
        "curriculum": session.curriculum, "curriculum_id": session._curriculum_id,
        "curriculum_origin": "saved",
        "current_lesson": session.current_lesson, "lesson_id": session._lesson_id,
        "current_exercise": exercise, "active_module": None, "module_id": None,
        "last_submission": None, "lesson_plan": plan,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    _append_lesson_history(state, session.current_lesson or {}, exercise)
    tutor_delivery.touch_lesson(_lesson_telemetry(state), str(state["lesson_id"]))
    _attach_delivery_state(state)
    _sync_resume_packet(state, state["lesson_id"])
    _save_atlas_state(state)
    _append_audit_event(kind="atlas_curriculum_start", message="Saved curriculum activated",
                        details={"curriculum_id": curriculum_id}, source="atlas", actor="learner")
    return {"status": "ok", "curriculum_id": curriculum_id, "lesson_id": state["lesson_id"]}


@app.get("/api/atlas/recap")
async def atlas_recap():
    state = _load_atlas_state()
    recap = _build_lesson_recap(state)
    _append_study_aid(state, "recap", recap)
    _save_atlas_state(state)
    return {"status": "ok", "recap": recap}

@app.get("/api/atlas/quiz")
async def atlas_quiz():
    state = _load_atlas_state()
    quiz = _build_lesson_quiz(state)
    _append_study_aid(state, "quiz", quiz)
    _save_atlas_state(state)
    return {"status": "ok", "quiz": quiz}

@app.get("/api/atlas/review")
async def atlas_review():
    state = _load_atlas_state()
    review = _build_lesson_review(state)
    _append_study_aid(state, "review", review)
    _save_atlas_state(state)
    return {"status": "ok", "review": review}

@app.get("/api/atlas/flashcards")
async def atlas_flashcards():
    state = _load_atlas_state()
    flashcards = _build_lesson_flashcards(state)
    _append_study_aid(state, "flashcards", flashcards)
    _save_atlas_state(state)
    return {"status": "ok", "flashcards": flashcards}

@app.post("/api/atlas/plan")
async def atlas_plan(body: Optional[Dict[str, Any]] = None):
    state = _load_atlas_state()
    _hydrate_learner_state(state, user_id=_atlas_user_id(state))
    body = body or {}
    trace_id = str(body.get("trace_id") or new_trace_id("atlas"))
    plan_profile = _normalize_plan_profile(body.get("plan_profile") or "coding")
    coding_intent = _normalize_coding_intent(body.get("coding_intent")) or _default_coding_intent_for_profile(plan_profile)
    approval_mode = bool(body.get("approval_mode", False))
    steps = _build_atlas_plan_steps(state, plan_profile, coding_intent)
    plan_id = f"atlas-plan-{uuid.uuid4().hex[:8]}"
    objective = str((state.get("current_exercise") or {}).get("prompt") or state.get("topic") or "Current lesson")
    step_results = await _execute_plan_steps(
        plan_id=plan_id,
        steps=steps,
        objective=objective,
        temperature=0.3,
        approval_mode=approval_mode,
        stop_on_failure=True,
        activity_agent_id="tutor_agent",
    )

    completed_count = sum(1 for step in step_results if step["status"] == "completed")
    failed_count = sum(1 for step in step_results if step["status"] == "failed")
    pending_count = sum(1 for step in step_results if step["status"] == "pending_approval")
    total_count = len(step_results)
    plan_status = "completed" if failed_count == 0 and pending_count == 0 else "pending_approval" if pending_count > 0 else "failed"
    synthesis = _build_plan_synthesis(
        step_results,
        objective=objective,
        lesson_title=str((state.get("current_lesson") or {}).get("title") or (state.get("current_lesson") or {}).get("lesson_title") or ""),
    )
    plan = {
        "plan_id": plan_id,
        "trace_id": trace_id,
        "objective": objective,
        "plan_profile": plan_profile,
        "coding_intent": coding_intent,
        "plan_status": plan_status,
        "progress": {
            "total": total_count,
            "executed": total_count,
            "completed": completed_count,
            "pending_approval": pending_count,
            "failed": failed_count,
        },
        "plan_steps": step_results,
        "synthesis": synthesis,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **_summarize_plan_run(
            step_results,
            objective=objective,
            plan_profile=plan_profile,
            coding_intent=coding_intent,
            approval_mode=approval_mode,
        ),
    }
    state["active_plan"] = plan
    _append_plan_history(state, plan)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _append_activity(
        "ATLAS tutor plan generated",
        agent_id="tutor_agent",
        task_id=plan["plan_id"],
        kind="atlas_plan_generated",
        trace_id=trace_id,
        details={"plan_status": plan_status, "step_count": total_count, "plan_profile": plan_profile, "coding_intent": coding_intent, "trace_id": trace_id},
    )
    _append_audit_event(
        kind="atlas_plan",
        message="ATLAS plan generated",
        details={"plan_id": plan_id, "plan_profile": plan_profile, "coding_intent": coding_intent, "plan_status": plan_status, "trace_id": trace_id},
        source="atlas",
        actor="system",
    )
    _save_atlas_state(state)
    return {"status": "ok", "plan": plan, "plan_history": state.get("plan_history", []), "trace_id": trace_id, "observability": _build_atlas_observability(state)}

@app.post("/api/atlas/evals")
async def atlas_evals(body: Optional[Dict[str, Any]] = None):
    state = _load_atlas_state()
    evaluation = _run_atlas_evals(state)
    history = _load_eval_history()
    history.append(evaluation)
    if len(history) > 20:
        history = history[-20:]
    _write_json(ATLAS_EVALS_FILE, history)
    _append_audit_event(
        kind="atlas_eval",
        message="ATLAS eval run completed",
        details={"pass_count": int((evaluation.get("summary") or {}).get("pass_count") or 0), "fail_count": int((evaluation.get("summary") or {}).get("fail_count") or 0)},
        source="atlas",
        actor="system",
    )
    return {"status": "ok", "evaluation": evaluation, "history": history, "observability": _build_atlas_observability(state, eval_history=history)}

@app.post("/api/atlas/regenerate")
async def atlas_regenerate(body: Optional[Dict[str, Any]] = None):
    state = _load_atlas_state()
    reason = "manual_regeneration"
    if isinstance(body, dict):
        reason = str(body.get("reason") or reason)
    exercise = _regenerate_current_exercise(state, reason=reason)
    if not exercise:
        return {"status": "error", "error": "No active lesson available for regeneration."}
    _append_lesson_history(state, state.get("current_lesson") or {}, exercise or {})
    _sync_resume_packet(state, state.get("lesson_id"))
    _save_atlas_state(state)
    return {
        "status": "ok",
        "exercise": exercise,
        "reason": reason,
        "learner_context": state.get("learner_context"),
    }

@app.post("/api/atlas/apply")
async def atlas_apply(body: Dict[str, Any]):
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    operation = str(body.get("operation", "")).strip().lower()
    file_path = str(body.get("file_path", "")).strip()
    if operation not in {"create_file", "write_file", "apply_patch", "insert_after"}:
        return {"status": "error", "error": "Unsupported operation"}
    if not file_path:
        return {"status": "error", "error": "file_path is required"}

    payload: Dict[str, Any] = {"file_path": file_path}
    if operation == "apply_patch":
        payload["new_content"] = str(body.get("new_content", ""))
    elif operation == "insert_after":
        payload["anchor"] = str(body.get("anchor", ""))
        payload["content"] = str(body.get("content", ""))
    else:
        payload["content"] = str(body.get("content", ""))

    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        preview = _build_operation_preview(operation, payload)
        approval = _create_approval_record(
            f"atlas-{uuid.uuid4().hex[:8]}",
            agent_id="tutor_agent",
            operation=operation,
            target=file_path,
            preview=preview,
            payload=payload,
            requested_by="user",
        )
        _append_activity(
            f"ATLAS approval requested: {operation}",
            agent_id="tutor_agent",
            kind="atlas_apply",
            details={"file_path": file_path, "approval_id": approval["id"]},
        )
        return {"status": "ok", "operation": operation, "approval": approval, "preview": preview}

    result = await asyncio.get_event_loop().run_in_executor(
        None, lambda: _run_file_operation(operation, payload)
    )
    _append_activity(
        f"ATLAS apply operation: {operation}",
        agent_id="tutor_agent",
        kind="atlas_apply",
        details={"file_path": file_path, "result": result},
    )
    return {"status": "ok", "operation": operation, "result": result}

@app.post("/api/atlas/reset")
async def atlas_reset(body: Optional[Dict[str, Any]] = None):
    body = body or {}
    approval_mode = bool(body.get("approval_mode") or body.get("preview_only"))
    if approval_mode:
        task_id = f"atlas-reset-{uuid.uuid4().hex[:8]}"
        preview = _build_operation_preview("atlas_session_reset", {})
        approval = _create_approval_record(
            task_id,
            agent_id="tutor_agent",
            operation="atlas_session_reset",
            target="atlas/session",
            preview=preview,
            payload={},
            requested_by="user",
        )
        _upsert_task(
            task_id,
            "approval:atlas_session_reset",
            status="pending_approval",
            agent_id="tutor_agent",
            description="ATLAS session reset pending approval",
            details={"approval_id": approval["id"]},
        )
        _append_activity(
            "ATLAS session reset queued for approval",
            agent_id="tutor_agent",
            task_id=task_id,
            kind="approval_requested",
            details={"approval_id": approval["id"]},
        )
        return {"status": "ok", "approval": approval, "preview": preview}
    return _apply_atlas_session_reset()

@app.post("/api/atlas/chat")
async def atlas_chat(body: Dict[str, Any]):
    message = str(body.get("message", "")).strip()
    if not message:
        return {"status": "error", "error": "message is required"}

    trace_id = str(body.get("trace_id") or new_trace_id("chat"))
    state = _load_atlas_state()
    mode = str(body.get("mode") or "tutor").strip().lower() or "tutor"
    if mode in {"assistant", "general", "chat"}:
        mode = "assistant"
    elif mode not in {"tutor", "build"}:
        mode = "tutor"
    strict_guard = bool(body.get("strict_guard", True))
    regenerate_on_guard = bool(body.get("regenerate_on_guard"))
    page_context = _normalize_page_context(body.get("page_context"), body.get("page_snapshot"))
    repo_context_request = _normalize_repo_context_request(body.get("repo_context"))
    repo_context = _collect_repo_context_snapshot(repo_context_request) if repo_context_request else {}
    if not repo_context and (str(body.get("agent_id") or "").strip().lower() == "mammoth_guide" or message.lower().startswith("/guide")):
        repo_context = _collect_public_docs_context(message)
    repo_evidence_items = _repo_context_evidence_items(repo_context)
    attached_material_ids = body.get("attached_material_ids") if isinstance(body.get("attached_material_ids"), list) else []
    attached_material_context = await asyncio.to_thread(_collect_attached_atlas_material_context,
        user_id=_current_request_user_id(),
        material_ids=attached_material_ids,
        query=message,
    )
    current_lesson = state.get("current_lesson") or {}
    current_exercise = state.get("current_exercise") or {}
    last_submission = state.get("last_submission") or {}
    learner_context = state.get("learner_context") or {}
    _hydrate_learner_state(state, user_id=_atlas_user_id(state))
    lesson_plan = state.get("lesson_plan") or build_lesson_plan(state, state.get("topic"))
    resume_packet = state.get("resume_packet") or _build_resume_packet(state, state.get("lesson_id"))
    learner_context = {**(state.get("learner_context") or learner_context), "lesson_plan": lesson_plan}
    has_active_exercise = bool(current_exercise and current_exercise.get("prompt"))
    guard_triggered = mode in {"tutor", "build"} and strict_guard and has_active_exercise and _is_answer_seeking_request(message)
    _sync_resume_packet(state, state.get("lesson_id"))

    adapter = str(body.get("adapter", "")).strip()
    model = str(body.get("model", "")).strip()
    temperature = float(body.get("temperature", 0.2))

    history_key = "assistant_chat_history" if mode == "assistant" else "chat_history"
    history = state.get(history_key) or []
    if not isinstance(history, list):
        history = []
    history.append({
        "role": "user",
        "message": message,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "page": str(page_context.get("current_page") or ""),
    })

    slash = _parse_mammoth_chat_command(message)
    if slash and slash.get("kind") in {"web", "research"}:
        command_result = _run_internet_command(slash)
        internet_reply = str(command_result.get("reply") or "No response produced.")
        internet_evidence = [item for item in [command_result.get("evidence"), *repo_evidence_items] if isinstance(item, dict)]
        runtime_status = _runtime_status_snapshot()
        confidence = _derive_chat_confidence(
            runtime_status=runtime_status,
            evidence_items=internet_evidence,
            reply=internet_reply,
            base=0.78 if command_result.get("status") == "ok" else 0.46,
        )
        trust_metadata = _build_chat_trust_metadata(
            provider="internet-tool",
            confidence=confidence,
            evidence_items=internet_evidence,
            content=internet_reply,
            response_type="research" if slash.get("kind") == "research" else "general",
        )
        history.append({
            "role": "assistant",
            "message": internet_reply,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "adapter": "internet-tool",
            "model": "internet-tool",
            "mode": mode,
            "evidence_items": internet_evidence,
            "confidence": confidence,
            "trust_metadata": trust_metadata,
        })
        state[history_key] = history[-60:]
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _append_fab_usage_event(
            state,
            mode=mode,
            page_context=page_context,
            guard_triggered=False,
        )
        _save_atlas_state(state)
        return {
            "status": "ok" if command_result.get("status") == "ok" else "error",
            "reply": internet_reply,
            "adapter": "internet-tool",
            "model": "internet-tool",
            "chat_history": state[history_key],
            "guard_triggered": False,
            "mode": mode,
            "runtime_status": _runtime_status_snapshot(),
            "runtime_notice": None,
            "trace_id": trace_id,
            "confidence": confidence,
            "trust_metadata": trust_metadata,
            "evidence_items": internet_evidence,
        }
    if slash and slash.get("kind") == "error":
        return {"status": "error", "error": slash.get("error") or "Invalid command."}
    requested_agent_id = str(body.get("agent_id") or "").strip().lower()
    if mode == "assistant" and (requested_agent_id == "mammoth_guide" or (slash and slash.get("kind") == "guide")):
        guide_message = str(slash.get("message") if slash and slash.get("kind") == "guide" else message).strip()
        guide_payload = {
            "message": guide_message,
            "repo_context": repo_context,
            "page_context": page_context,
            "lesson_context": {
                "current_lesson": current_lesson,
                "current_exercise": current_exercise,
                "learner_context": learner_context,
                "attached_materials": attached_material_context.get("materials", []),
            },
        }
        guide_result = registry_run_agent("mammoth_guide", guide_payload)
        guide_reply = _render_chat_result(guide_result)
        guide_steps = guide_result.get("guide_steps") if isinstance(guide_result, dict) else None
        guide_branch = str(guide_result.get("branch") or repo_context.get("branch") or "main") if isinstance(guide_result, dict) else str(repo_context.get("branch") or "main")
        history.append(
            {
                "role": "assistant",
                "message": guide_reply,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "adapter": "mammoth-guide",
                "model": "mammoth-guide",
                "mode": mode,
                "guide_steps": guide_steps if isinstance(guide_steps, list) else [],
                "guide_branch": guide_branch,
                "attached_materials": attached_material_context.get("materials", []),
                "evidence_items": [
                    {
                        "source": "mammoth-guide",
                        "repo_context_used": bool(repo_context),
                        "branch": str(repo_context.get("branch") or "main"),
                    }
                ] + repo_evidence_items[:2],
            }
        )
        guide_evidence = history[-1].get("evidence_items") if isinstance(history[-1].get("evidence_items"), list) else []
        guide_confidence = _derive_chat_confidence(
            runtime_status=_runtime_status_snapshot(),
            evidence_items=guide_evidence,
            reply=guide_reply,
            base=0.74,
        )
        guide_trust = _build_chat_trust_metadata(
            provider="mammoth-guide",
            confidence=guide_confidence,
            evidence_items=guide_evidence,
            content=guide_reply,
            response_type="general",
        )
        history[-1]["confidence"] = guide_confidence
        history[-1]["trust_metadata"] = guide_trust
        state[history_key] = history[-60:]
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _append_fab_usage_event(
            state,
            mode=mode,
            page_context=page_context,
            guard_triggered=False,
        )
        _save_atlas_state(state)
        return {
            "status": "ok",
            "reply": guide_reply,
            "adapter": "mammoth-guide",
            "model": "mammoth-guide",
            "chat_history": state[history_key],
            "guard_triggered": False,
            "mode": mode,
            "runtime_status": _runtime_status_snapshot(),
            "runtime_notice": None,
            "trace_id": trace_id,
            "guide_steps": guide_steps if isinstance(guide_steps, list) else [],
            "guide_branch": guide_branch,
            "attached_materials_used": attached_material_context.get("materials", []),
            "confidence": guide_confidence,
            "trust_metadata": guide_trust,
            "evidence_items": guide_evidence,
        }

    if guard_triggered:
        regenerated_exercise = None
        if regenerate_on_guard:
            regenerated_exercise = _regenerate_current_exercise(
                state,
                reason="anti_cheat_guard_triggered",
            )
        guard_reply = (
            "I can't provide direct answer dumps for an active exercise. "
            "I can coach you step-by-step or generate a fresh parallel exercise."
        )
        if regenerated_exercise:
            guard_reply += "\n\n✅ I generated a new exercise variant so you can keep learning without answer leakage."
        history.append({
            "role": "assistant",
            "message": guard_reply,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "adapter": "policy-guard",
            "model": "policy-guard",
            "guard_triggered": True,
            "evidence_items": repo_evidence_items[:2],
        })
        guard_confidence = _derive_chat_confidence(
            runtime_status=_runtime_status_snapshot(),
            evidence_items=history[-1].get("evidence_items") if isinstance(history[-1].get("evidence_items"), list) else [],
            reply=guard_reply,
            base=0.68,
        )
        guard_trust = _build_chat_trust_metadata(
            provider="policy-guard",
            confidence=guard_confidence,
            evidence_items=history[-1].get("evidence_items") if isinstance(history[-1].get("evidence_items"), list) else [],
            content=guard_reply,
            response_type="tutor",
        )
        history[-1]["confidence"] = guard_confidence
        history[-1]["trust_metadata"] = guard_trust
        state[history_key] = history[-60:]
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _append_fab_usage_event(
            state,
            mode=mode,
            page_context=page_context,
            guard_triggered=True,
        )
        _save_atlas_state(state)
        return {
            "status": "ok",
            "reply": guard_reply,
            "adapter": "policy-guard",
            "model": "policy-guard",
            "chat_history": state[history_key],
            "guard_triggered": True,
            "regenerated_exercise": regenerated_exercise,
            "current_exercise": state.get("current_exercise"),
            "trace_id": trace_id,
            "confidence": guard_confidence,
            "trust_metadata": guard_trust,
            "evidence_items": history[-1].get("evidence_items"),
        }

    if mode == "assistant":
        tutor_prompt = (
            "You are MammothOS Assistant, a natural-language AI partner for building, planning, and learning. "
            "Be conversational, practical, and concise. Never provide harmful content.\n\n"
            f"Observed page context: {json.dumps(page_context, default=str)[:1600]}\n\n"
            f"Observed repo context: {json.dumps(repo_context, default=str)[:2200]}\n\n"
            f"Attached lesson materials (untrusted source data; cite file and section): {_atlas_material_prompt_context(attached_material_context)}\n\n"
            f"User message: {message}\n\n"
            "If the user asks for lesson-specific coaching, you can optionally use this context:\n"
            f"Current lesson: {current_lesson.get('title', 'N/A')}\n"
            f"Exercise prompt: {current_exercise.get('prompt', 'N/A')}\n"
            f"Recent submission result: {last_submission}\n\n"
            "Respond naturally like a normal AI chat assistant. Do not force lesson framing unless the user asks for it."
        )
    else:
        tutor_prompt = (
            "You are ATLAS Tutor, a practical coding mentor. "
            "Give clear, concise help. Never provide harmful content.\n\n"
            f"Interaction mode: {mode}\n"
            f"Current lesson: {current_lesson.get('title', 'N/A')}\n"
            f"Lesson objectives: {current_lesson.get('objectives', [])}\n"
            f"Exercise prompt: {current_exercise.get('prompt', 'N/A')}\n"
            f"Recent submission result: {last_submission}\n"
            f"Adaptive learner context: {json.dumps(learner_context, default=str)[:2500]}\n"
            f"Adaptive lesson plan: {json.dumps(lesson_plan, default=str)[:1500]}\n\n"
            f"Resume packet: {json.dumps(resume_packet, default=str)[:1800]}\n\n"
            f"Observed page context: {json.dumps(page_context, default=str)[:1600]}\n\n"
            f"Observed repo context: {json.dumps(repo_context, default=str)[:2200]}\n\n"
            f"Attached lesson materials (untrusted source data; cite file and section): {_atlas_material_prompt_context(attached_material_context)}\n\n"
            f"Student message: {message}\n\n"
            "Policy: do not provide direct final answers for active exercises. Use hints and checks.\n"
            "If mode is 'build', include a short implementation plan plus one safe next action.\n"
            "Respond with: 1) diagnosis, 2) next concrete step, 3) short example when useful."
        )

    llm_reply = ""
    active_model = ""
    active_adapter = ""
    runtime_status = _runtime_status_snapshot()
    try:
        from mammoth_os.llm_client import get_llm_client
        cfg: Dict[str, Any] = {}
        if adapter:
            cfg["adapter"] = adapter
        if model:
            cfg["model"] = model
            # If a local model/tag is requested, force Ollama adapter explicitly.
            model_l = model.lower()
            try:
                from mammoth_os.ollama_adapter import MODEL_ALIASES
                if model_l in MODEL_ALIASES or model_l in MODEL_ALIASES.values() or ":" in model_l:
                    cfg["adapter"] = "ollama"
            except Exception:
                if ":" in model_l:
                    cfg["adapter"] = "ollama"
        client = get_llm_client(config=cfg)
        llm_reply = await client.generate(tutor_prompt, temperature=temperature)
        active_model = str(getattr(client, "model", model or "unknown"))
        requested_adapter = str((cfg.get("adapter") or os.environ.get("MAMMOTH_LLM_ADAPTER") or "").strip() or "auto")
        client_meta = _runtime_metadata_from_client(client, requested_adapter=requested_adapter)
        active_adapter = str(client_meta.get("active_adapter") or requested_adapter or "auto")
        runtime_status = _runtime_status_snapshot()
        runtime_status["effective_adapter"] = active_adapter
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
    except Exception as e:
        runtime_status = _runtime_status_snapshot()
        safe_error = _sanitize_runtime_error_message(e)
        llm_reply = (
            "I could not reach the configured LLM runtime right now. "
            "MammothOS switched to a safe fallback path. "
            f"{runtime_status.get('recommendation')}"
        )
        if not active_model:
            active_model = "fallback-local"
        if not active_adapter:
            active_adapter = "fallback-local"
        runtime_status["error_type"] = type(e).__name__
        runtime_status["safe_error"] = safe_error
        _remember_runtime_status(runtime_status)

    assistant_evidence = list(repo_evidence_items[:2])
    if attached_material_context.get("count"):
        assistant_evidence.extend({
            "agent_id": "atlas-materials", "source": "attached-materials",
            "summary": material["name"] + ": " + ", ".join(section["location"] for section in material["sections"]),
            "file_id": material["file_id"], "status": material["processing_status"],
        } for material in attached_material_context["materials"])
    llm_confidence = _derive_chat_confidence(
        runtime_status=runtime_status,
        evidence_items=assistant_evidence,
        reply=llm_reply,
        base=0.72,
    )
    llm_trust = _build_chat_trust_metadata(
        provider=active_adapter or "unknown",
        confidence=llm_confidence,
        evidence_items=assistant_evidence,
        content=llm_reply,
        response_type="tutor" if mode != "assistant" else "general",
    )
    history.append({
        "role": "assistant",
        "message": llm_reply,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "adapter": active_adapter,
        "model": active_model,
        "mode": mode,
        "attached_materials": attached_material_context.get("materials", []),
        "evidence_items": assistant_evidence,
        "confidence": llm_confidence,
        "trust_metadata": llm_trust,
    })
    state[history_key] = history[-60:]
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _append_fab_usage_event(
        state,
        mode=mode,
        page_context=page_context,
        guard_triggered=False,
    )
    _save_atlas_state(state)

    return {
        "status": "ok",
        "reply": llm_reply,
        "adapter": active_adapter,
        "model": active_model,
        "chat_history": state[history_key],
        "guard_triggered": False,
        "mode": mode,
        "runtime_status": runtime_status,
        "runtime_notice": None if runtime_status.get("state") == "ready" else build_runtime_notice(runtime_status, trace_id=trace_id, agent_id="atlas_chat", context=mode, provider=active_adapter),
        "trace_id": trace_id,
        "attached_materials_used": attached_material_context.get("materials", []),
        "evidence_items": assistant_evidence,
        "confidence": llm_confidence,
        "trust_metadata": llm_trust,
    }

@app.post("/api/atlas/files/upload")
async def upload_atlas_file(file: UploadFile = File(...), tag: str = Form(default="other")):
    tag = tag.strip().lower() if tag.strip().lower() in _ATLAS_TAGS else "other"
    return await _document_upload(file, "atlas", tag)

@app.get("/api/atlas/files/capabilities")
async def atlas_file_capabilities():
    return {"status": "ok", **document_capabilities(), "usage": await asyncio.to_thread(_document_library(_current_request_user_id()).usage)}

@app.get("/api/atlas/files")
async def list_atlas_files():
    user_id = _current_request_user_id()
    index = await asyncio.to_thread(_load_atlas_files_index, user_id)
    return {"status": "ok", "files": [DocumentLibrary.public(f) for f in index]}

@app.get("/api/atlas/files/{file_id}/content")
async def get_atlas_file_content(file_id: str, query: str = ""):
    return await asyncio.to_thread(_document_content, "atlas", file_id, query)

@app.patch("/api/atlas/files/{file_id}")
async def update_atlas_file_tag(file_id: str, body: Dict[str, Any] = {}):
    new_tag = str(body.get("tag") or "other").strip().lower()
    try:
        return await asyncio.to_thread(_document_library(_current_request_user_id()).retag, "atlas", file_id, new_tag if new_tag in _ATLAS_TAGS else "other")
    except DocumentError as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=exc.status_code)

@app.delete("/api/atlas/files/{file_id}")
async def delete_atlas_file(file_id: str):
    return await asyncio.to_thread(_document_delete, "atlas", file_id)

@app.post("/api/atlas/lesson/ingest")
async def ingest_atlas_lesson(payload: dict, request: Request):
    """Ingest a lesson plan and ground it in RAG context."""
    user_id = payload.get("user_id", "anonymous")
    lesson = payload.get("lesson", {})
    source_file = payload.get("source_file", "")

    if not lesson:
        return {"status": "error", "message": "No lesson provided"}

    store = get_rag_context_store()
    store.store(
        user_id=user_id,
        topic="lesson_ingested",
        content_type="lesson_metadata",
        content={
            "title": lesson.get("title", ""),
            "topics": lesson.get("topics", []),
            "difficulty": lesson.get("difficulty", "intermediate"),
            "source_file": source_file,
        },
        source_agent="atlas",
        tags=["lesson", "atlas"] + lesson.get("topics", []),
        ttl_hours=168,
    )

    return {
        "status": "ingested",
        "lesson_title": lesson.get("title", ""),
        "user_id": user_id,
        "grounded": True,
    }
