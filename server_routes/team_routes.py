# Route fragment loaded by api_server._load_route_fragments().
# Not importable on its own: handlers execute in api_server globals, so keep helpers there.

@app.get("/api/team/workflow-templates")
async def list_workflow_templates():
    """List all workflow templates"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        templates = _TEAM_WORKFLOW_MANAGER.templates.list()
        return {
            "status": "ok",
            "templates": [t.to_dict() for t in templates],
            "count": len(templates),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/workflow-templates")
async def create_workflow_template(body: Dict[str, Any]):
    """Create a new workflow template"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        name = str(body.get("name", "")).strip()
        description = str(body.get("description", "")).strip()
        intent = str(body.get("intent", "")).strip()
        prompt_shape = body.get("prompt_shape", {})
        required_approvals = body.get("required_approvals", [])
        estimated_duration_min = int(body.get("estimated_duration_min", 30))
        owner = str(body.get("owner", "") or _REQUEST_USER_ID.get())
        tags = body.get("tags", [])

        if not name or not intent:
            return {"status": "error", "message": "name and intent are required"}

        template = _TEAM_WORKFLOW_MANAGER.templates.create(
            name=name,
            description=description,
            intent=intent,
            prompt_shape=prompt_shape,
            required_approvals=required_approvals,
            estimated_duration_min=estimated_duration_min,
            owner=owner,
            tags=tags,
        )
        _append_activity(
            f"Workflow template created: {name}",
            agent_id="team_workflows",
            kind="workflow_template_created",
            details={"template_id": template.id, "name": name},
        )
        return {"status": "ok", "template": template.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/team/workflow-templates/{template_id}")
async def get_workflow_template(template_id: str):
    """Get a specific workflow template"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        template = _TEAM_WORKFLOW_MANAGER.templates.get(template_id)
        if not template:
            return {"status": "error", "message": "Template not found"}
        return {"status": "ok", "template": template.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/workflow-templates/{template_id}")
async def update_workflow_template(template_id: str, body: Dict[str, Any]):
    """Update a workflow template"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        update_dict = {k: v for k, v in body.items() if k not in {"id", "created_at"}}
        template = _TEAM_WORKFLOW_MANAGER.templates.update(template_id, **update_dict)
        if not template:
            return {"status": "error", "message": "Template not found"}
        _append_activity(
            f"Workflow template updated: {template.name}",
            agent_id="team_workflows",
            kind="workflow_template_updated",
            details={"template_id": template_id},
        )
        return {"status": "ok", "template": template.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/team/workflow-templates/{template_id}")
async def delete_workflow_template(template_id: str):
    """Delete a workflow template"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        success = _TEAM_WORKFLOW_MANAGER.templates.delete(template_id)
        if not success:
            return {"status": "error", "message": "Template not found"}
        _append_activity(
            f"Workflow template deleted: {template_id}",
            agent_id="team_workflows",
            kind="workflow_template_deleted",
            details={"template_id": template_id},
        )
        return {"status": "ok", "message": "Template deleted"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/team/approval-policies")
async def list_approval_policies():
    """List all approval policies"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        policies = _TEAM_WORKFLOW_MANAGER.policies.list()
        return {
            "status": "ok",
            "policies": [p.to_dict() for p in policies],
            "count": len(policies),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/approval-policies")
async def create_approval_policy(body: Dict[str, Any]):
    """Create a new approval policy"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        name = str(body.get("name", "")).strip()
        policy_type = str(body.get("policy_type", "")).strip()
        triggers = body.get("triggers", [])
        required_reviewers = body.get("required_reviewers", [])
        auto_approve_conditions = body.get("auto_approve_conditions", {})
        owner = str(body.get("owner", "") or _REQUEST_USER_ID.get())

        if not name or not policy_type:
            return {"status": "error", "message": "name and policy_type are required"}

        policy = _TEAM_WORKFLOW_MANAGER.policies.create(
            name=name,
            policy_type=policy_type,
            triggers=triggers,
            required_reviewers=required_reviewers,
            auto_approve_conditions=auto_approve_conditions,
            owner=owner,
        )
        _append_activity(
            f"Approval policy created: {name}",
            agent_id="team_workflows",
            kind="approval_policy_created",
            details={"policy_id": policy.id, "name": name},
        )
        return {"status": "ok", "policy": policy.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/team/approval-policies/{policy_id}")
async def get_approval_policy(policy_id: str):
    """Get a specific approval policy"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        policy = _TEAM_WORKFLOW_MANAGER.policies.get(policy_id)
        if not policy:
            return {"status": "error", "message": "Policy not found"}
        return {"status": "ok", "policy": policy.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/approval-policies/{policy_id}")
async def update_approval_policy(policy_id: str, body: Dict[str, Any]):
    """Update an approval policy"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        update_dict = {k: v for k, v in body.items() if k not in {"id", "created_at"}}
        policy = _TEAM_WORKFLOW_MANAGER.policies.update(policy_id, **update_dict)
        if not policy:
            return {"status": "error", "message": "Policy not found"}
        _append_activity(
            f"Approval policy updated: {policy.name}",
            agent_id="team_workflows",
            kind="approval_policy_updated",
            details={"policy_id": policy_id},
        )
        return {"status": "ok", "policy": policy.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/team/approval-policies/{policy_id}")
async def delete_approval_policy(policy_id: str):
    """Delete an approval policy"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        success = _TEAM_WORKFLOW_MANAGER.policies.delete(policy_id)
        if not success:
            return {"status": "error", "message": "Policy not found"}
        _append_activity(
            f"Approval policy deleted: {policy_id}",
            agent_id="team_workflows",
            kind="approval_policy_deleted",
            details={"policy_id": policy_id},
        )
        return {"status": "ok", "message": "Policy deleted"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/team/runbooks")
async def list_runbooks():
    """List all runbooks"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        runbooks = _TEAM_WORKFLOW_MANAGER.runbooks.list()
        return {
            "status": "ok",
            "runbooks": [r.to_dict() for r in runbooks],
            "count": len(runbooks),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/runbooks")
async def create_runbook(body: Dict[str, Any]):
    """Create a new runbook"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        name = str(body.get("name", "")).strip()
        description = str(body.get("description", "")).strip()
        steps_data = body.get("steps", [])
        owner = str(body.get("owner", "") or _REQUEST_USER_ID.get())
        tags = body.get("tags", [])
        enabled = bool(body.get("enabled", True))

        if not name:
            return {"status": "error", "message": "name is required"}

        # Convert steps to RunbookStep objects
        steps = []
        for idx, step_data in enumerate(steps_data):
            if isinstance(step_data, dict):
                step_data = dict(step_data)  # Make a copy
                if "step_index" not in step_data:
                    step_data["step_index"] = idx
                steps.append(RunbookStep.from_dict(step_data))
            else:
                steps.append(step_data)

        runbook = _TEAM_WORKFLOW_MANAGER.runbooks.create(
            name=name,
            description=description,
            steps=steps,
            owner=owner,
            tags=tags,
            enabled=enabled,
        )
        _append_activity(
            f"Runbook created: {name}",
            agent_id="team_workflows",
            kind="runbook_created",
            details={"runbook_id": runbook.id, "name": name, "step_count": len(steps)},
        )
        return {"status": "ok", "runbook": runbook.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/team/runbooks/{runbook_id}")
async def get_runbook(runbook_id: str):
    """Get a specific runbook"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        runbook = _TEAM_WORKFLOW_MANAGER.runbooks.get(runbook_id)
        if not runbook:
            return {"status": "error", "message": "Runbook not found"}
        return {"status": "ok", "runbook": runbook.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/runbooks/{runbook_id}")
async def update_runbook(runbook_id: str, body: Dict[str, Any]):
    """Update a runbook"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        update_dict = {k: v for k, v in body.items() if k not in {"id", "created_at"}}
        
        # Handle steps specially
        if "steps" in update_dict:
            steps_data = update_dict["steps"]
            steps = []
            for idx, step_data in enumerate(steps_data):
                if isinstance(step_data, dict):
                    step_data = dict(step_data)
                    if "step_index" not in step_data:
                        step_data["step_index"] = idx
                    steps.append(RunbookStep.from_dict(step_data))
                else:
                    steps.append(step_data)
            update_dict["steps"] = steps
        
        runbook = _TEAM_WORKFLOW_MANAGER.runbooks.update(runbook_id, **update_dict)
        if not runbook:
            return {"status": "error", "message": "Runbook not found"}
        _append_activity(
            f"Runbook updated: {runbook.name}",
            agent_id="team_workflows",
            kind="runbook_updated",
            details={"runbook_id": runbook_id},
        )
        return {"status": "ok", "runbook": runbook.to_dict()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.delete("/api/team/runbooks/{runbook_id}")
async def delete_runbook(runbook_id: str):
    """Delete a runbook"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        success = _TEAM_WORKFLOW_MANAGER.runbooks.delete(runbook_id)
        if not success:
            return {"status": "error", "message": "Runbook not found"}
        _append_activity(
            f"Runbook deleted: {runbook_id}",
            agent_id="team_workflows",
            kind="runbook_deleted",
            details={"runbook_id": runbook_id},
        )
        return {"status": "ok", "message": "Runbook deleted"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/runbooks/{runbook_id}/execute")
async def execute_runbook(runbook_id: str, body: Dict[str, Any]):
    """Start execution of a runbook"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        dry_run = bool(body.get("dry_run", False))
        result = _TEAM_WORKFLOW_MANAGER.engine.execute_runbook(runbook_id, dry_run=dry_run)
        
        if result.get("status") == "started":
            _append_activity(
                f"Runbook execution started: {runbook_id}",
                agent_id="team_workflows",
                kind="runbook_execution_started",
                details={
                    "runbook_id": runbook_id,
                    "execution_id": result.get("execution_id"),
                    "dry_run": dry_run,
                },
            )
        
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/team/runbooks/{runbook_id}/execute/{execution_id}")
async def get_execution_status(runbook_id: str, execution_id: str):
    """Get status of a runbook execution"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        execution = _TEAM_WORKFLOW_MANAGER.executions.get(execution_id)
        if not execution:
            return {"status": "error", "message": "Execution not found"}
        if execution.runbook_id != runbook_id:
            return {"status": "error", "message": "Execution does not match runbook"}
        
        return {
            "status": "ok",
            "execution": execution.to_dict(),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/runbooks/{runbook_id}/execute/{execution_id}/next-step")
async def get_next_step(runbook_id: str, execution_id: str):
    """Get the next step to execute"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        execution = _TEAM_WORKFLOW_MANAGER.executions.get(execution_id)
        if not execution or execution.runbook_id != runbook_id:
            return {"status": "error", "message": "Execution not found"}
        
        result = _TEAM_WORKFLOW_MANAGER.engine.get_next_step(execution_id)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/runbooks/{runbook_id}/execute/{execution_id}/step-result")
async def record_step_result(runbook_id: str, execution_id: str, body: Dict[str, Any]):
    """Record result of a step execution"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        execution = _TEAM_WORKFLOW_MANAGER.executions.get(execution_id)
        if not execution or execution.runbook_id != runbook_id:
            return {"status": "error", "message": "Execution not found"}
        
        step_result = body.get("result", {})
        success = bool(body.get("success", False))
        
        if success:
            result = _TEAM_WORKFLOW_MANAGER.engine.complete_step(execution_id, step_result)
        else:
            error_msg = str(body.get("error", "Unknown error"))
            result = _TEAM_WORKFLOW_MANAGER.engine.fail_step(execution_id, error_msg)
        
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/runbooks/{runbook_id}/execute/{execution_id}/request-approval")
async def request_approval_for_step(runbook_id: str, execution_id: str):
    """Request approval for the current step"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        execution = _TEAM_WORKFLOW_MANAGER.executions.get(execution_id)
        if not execution or execution.runbook_id != runbook_id:
            return {"status": "error", "message": "Execution not found"}
        
        result = _TEAM_WORKFLOW_MANAGER.engine.request_approval(execution_id)
        
        # Also create an approval record in the main approvals system
        if result.get("status") == "ok":
            approval_record = _create_approval_record(
                task_id=execution_id,
                agent_id="team_workflows",
                operation="runbook_step_approval",
                target=f"Runbook {runbook_id}, Step {execution.current_step}",
                preview={
                    "runbook_id": runbook_id,
                    "execution_id": execution_id,
                    "step_index": execution.current_step,
                    "policy_id": result.get("policy_id"),
                    "required_reviewers": result.get("required_reviewers"),
                },
            )
            result["approval_record_id"] = approval_record.get("id")
        
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/team/runbooks/{runbook_id}/execute/{execution_id}/approve/{approval_id}")
async def approve_step(runbook_id: str, execution_id: str, approval_id: str, body: Dict[str, Any]):
    """Approve a pending step"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        execution = _TEAM_WORKFLOW_MANAGER.executions.get(execution_id)
        if not execution or execution.runbook_id != runbook_id:
            return {"status": "error", "message": "Execution not found"}
        
        approved_by = str(body.get("approved_by", "") or _REQUEST_USER_ID.get())
        result = _TEAM_WORKFLOW_MANAGER.engine.approve_step(execution_id, approval_id, approved_by)
        
        if result.get("status") == "ok":
            _approve_record(approval_id)
            _append_activity(
                f"Runbook step approved in execution {execution_id}",
                agent_id="team_workflows",
                kind="runbook_step_approved",
                details={
                    "runbook_id": runbook_id,
                    "execution_id": execution_id,
                    "approval_id": approval_id,
                    "approved_by": approved_by,
                },
            )
        
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/team/runbooks/{runbook_id}/history")
async def get_runbook_history(runbook_id: str):
    """Get execution history for a runbook"""
    blocked = _require_admin_api()
    if blocked is not None:
        return blocked
    try:
        executions = _TEAM_WORKFLOW_MANAGER.executions.list_by_runbook(runbook_id)
        return {
            "status": "ok",
            "runbook_id": runbook_id,
            "executions": [e.to_dict() for e in executions],
            "count": len(executions),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

