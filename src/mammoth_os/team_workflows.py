"""
Team Workflow Primitives for MammothOS
Provides reusable workflow templates, approval policies, and runbooks for teams.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, asdict, field


# ── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class WorkflowTemplate:
    """Reusable workflow template for teams"""
    id: str
    name: str
    description: str
    intent: str  # What this workflow accomplishes
    prompt_shape: Dict[str, Any]  # Template for prompt/parameters
    required_approvals: List[str]  # List of approval policy IDs
    estimated_duration_min: int
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    owner: str = ""
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "WorkflowTemplate":
        return WorkflowTemplate(**data)


@dataclass
class ApprovalPolicy:
    """Policy governing approvals for a workflow"""
    id: str
    name: str
    policy_type: str  # "require_all", "require_any_one", "auto_approve"
    triggers: List[str]  # Workflow events that trigger this policy
    required_reviewers: List[str]  # User IDs or roles
    auto_approve_conditions: Dict[str, Any]  # Conditions for auto-approval
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    owner: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ApprovalPolicy":
        return ApprovalPolicy(**data)


@dataclass
class RunbookStep:
    """Individual step in a runbook"""
    step_index: int
    template_id: str
    approvals_policy_id: Optional[str]
    on_fail: str  # "pause", "rollback", "continue"
    params: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RunbookStep":
        return RunbookStep(**data)


@dataclass
class Runbook:
    """Multi-step workflow runbook"""
    id: str
    name: str
    description: str
    steps: List[RunbookStep]
    owner: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: List[str] = field(default_factory=list)
    enabled: bool = True
    dry_run_mode: bool = False

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["steps"] = [step.to_dict() if isinstance(step, RunbookStep) else step for step in self.steps]
        return data

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Runbook":
        steps = data.get("steps", [])
        data["steps"] = [
            RunbookStep.from_dict(step) if isinstance(step, dict) else step
            for step in steps
        ]
        return Runbook(**data)


@dataclass
class RunbookExecution:
    """Tracks execution of a runbook"""
    id: str
    runbook_id: str
    started_at: str
    ended_at: Optional[str] = None
    status: str = "running"  # running, completed, failed, paused
    current_step: int = 0
    step_results: List[Dict[str, Any]] = field(default_factory=list)
    approvals_pending: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RunbookExecution":
        return RunbookExecution(**data)


# ── Manager Classes ──────────────────────────────────────────────────────────

class WorkflowTemplateManager:
    """CRUD operations for workflow templates"""
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path / "workflow_templates.json"
        self.storage_path.parent.mkdir(exist_ok=True, parents=True)
        self._ensure_storage()

    def _ensure_storage(self):
        if not self.storage_path.exists():
            self.storage_path.write_text(json.dumps([], indent=2))

    def _load(self) -> List[Dict[str, Any]]:
        try:
            content = self.storage_path.read_text()
            return json.loads(content) if content.strip() else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, templates: List[Dict[str, Any]]):
        self.storage_path.write_text(json.dumps(templates, indent=2))

    def create(self, name: str, description: str, intent: str, prompt_shape: Dict[str, Any],
               required_approvals: Optional[List[str]] = None, 
               estimated_duration_min: int = 30,
               owner: str = "", tags: Optional[List[str]] = None) -> WorkflowTemplate:
        """Create a new workflow template"""
        template = WorkflowTemplate(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            intent=intent,
            prompt_shape=prompt_shape,
            required_approvals=required_approvals or [],
            estimated_duration_min=estimated_duration_min,
            owner=owner,
            tags=tags or [],
        )
        templates = self._load()
        templates.append(template.to_dict())
        self._save(templates)
        return template

    def list(self) -> List[WorkflowTemplate]:
        """List all workflow templates"""
        templates = self._load()
        return [WorkflowTemplate.from_dict(t) for t in templates]

    def get(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get a specific template"""
        for t in self._load():
            if t.get("id") == template_id:
                return WorkflowTemplate.from_dict(t)
        return None

    def update(self, template_id: str, **kwargs) -> Optional[WorkflowTemplate]:
        """Update a template"""
        templates = self._load()
        for t in templates:
            if t.get("id") == template_id:
                t.update({k: v for k, v in kwargs.items() if v is not None})
                t["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save(templates)
                return WorkflowTemplate.from_dict(t)
        return None

    def delete(self, template_id: str) -> bool:
        """Delete a template"""
        templates = self._load()
        original_count = len(templates)
        templates = [t for t in templates if t.get("id") != template_id]
        if len(templates) < original_count:
            self._save(templates)
            return True
        return False


class ApprovalPolicyManager:
    """CRUD operations for approval policies"""
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path / "approval_policies.json"
        self.storage_path.parent.mkdir(exist_ok=True, parents=True)
        self._ensure_storage()

    def _ensure_storage(self):
        if not self.storage_path.exists():
            self.storage_path.write_text(json.dumps([], indent=2))

    def _load(self) -> List[Dict[str, Any]]:
        try:
            content = self.storage_path.read_text()
            return json.loads(content) if content.strip() else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, policies: List[Dict[str, Any]]):
        self.storage_path.write_text(json.dumps(policies, indent=2))

    def create(self, name: str, policy_type: str, triggers: List[str],
               required_reviewers: Optional[List[str]] = None,
               auto_approve_conditions: Optional[Dict[str, Any]] = None,
               owner: str = "") -> ApprovalPolicy:
        """Create a new approval policy"""
        policy = ApprovalPolicy(
            id=str(uuid.uuid4()),
            name=name,
            policy_type=policy_type,
            triggers=triggers,
            required_reviewers=required_reviewers or [],
            auto_approve_conditions=auto_approve_conditions or {},
            owner=owner,
        )
        policies = self._load()
        policies.append(policy.to_dict())
        self._save(policies)
        return policy

    def list(self) -> List[ApprovalPolicy]:
        """List all approval policies"""
        policies = self._load()
        return [ApprovalPolicy.from_dict(p) for p in policies]

    def get(self, policy_id: str) -> Optional[ApprovalPolicy]:
        """Get a specific policy"""
        for p in self._load():
            if p.get("id") == policy_id:
                return ApprovalPolicy.from_dict(p)
        return None

    def update(self, policy_id: str, **kwargs) -> Optional[ApprovalPolicy]:
        """Update a policy"""
        policies = self._load()
        for p in policies:
            if p.get("id") == policy_id:
                p.update({k: v for k, v in kwargs.items() if v is not None})
                p["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save(policies)
                return ApprovalPolicy.from_dict(p)
        return None

    def delete(self, policy_id: str) -> bool:
        """Delete a policy"""
        policies = self._load()
        original_count = len(policies)
        policies = [p for p in policies if p.get("id") != policy_id]
        if len(policies) < original_count:
            self._save(policies)
            return True
        return False


class RunbookManager:
    """CRUD operations for runbooks"""
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path / "runbooks.json"
        self.storage_path.parent.mkdir(exist_ok=True, parents=True)
        self._ensure_storage()

    def _ensure_storage(self):
        if not self.storage_path.exists():
            self.storage_path.write_text(json.dumps([], indent=2))

    def _load(self) -> List[Dict[str, Any]]:
        try:
            content = self.storage_path.read_text()
            return json.loads(content) if content.strip() else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, runbooks: List[Dict[str, Any]]):
        self.storage_path.write_text(json.dumps(runbooks, indent=2))

    def create(self, name: str, description: str, steps: List[Dict[str, Any]],
               owner: str = "", tags: Optional[List[str]] = None,
               enabled: bool = True) -> Runbook:
        """Create a new runbook"""
        parsed_steps = [
            RunbookStep.from_dict(step) if isinstance(step, dict) else step
            for step in steps
        ]
        runbook = Runbook(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            steps=parsed_steps,
            owner=owner,
            tags=tags or [],
            enabled=enabled,
        )
        runbooks = self._load()
        runbooks.append(runbook.to_dict())
        self._save(runbooks)
        return runbook

    def list(self) -> List[Runbook]:
        """List all runbooks"""
        runbooks = self._load()
        return [Runbook.from_dict(r) for r in runbooks]

    def get(self, runbook_id: str) -> Optional[Runbook]:
        """Get a specific runbook"""
        for r in self._load():
            if r.get("id") == runbook_id:
                return Runbook.from_dict(r)
        return None

    def update(self, runbook_id: str, **kwargs) -> Optional[Runbook]:
        """Update a runbook"""
        runbooks = self._load()
        for r in runbooks:
            if r.get("id") == runbook_id:
                # Handle steps specially
                if "steps" in kwargs:
                    steps = kwargs.pop("steps")
                    r["steps"] = [
                        step.to_dict() if isinstance(step, RunbookStep) else step
                        for step in steps
                    ]
                r.update({k: v for k, v in kwargs.items() if v is not None})
                r["updated_at"] = datetime.now(timezone.utc).isoformat()
                self._save(runbooks)
                return Runbook.from_dict(r)
        return None

    def delete(self, runbook_id: str) -> bool:
        """Delete a runbook"""
        runbooks = self._load()
        original_count = len(runbooks)
        runbooks = [r for r in runbooks if r.get("id") != runbook_id]
        if len(runbooks) < original_count:
            self._save(runbooks)
            return True
        return False


class RunbookExecutionManager:
    """Manages execution of runbooks"""
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path / "runbook_executions.json"
        self.storage_path.parent.mkdir(exist_ok=True, parents=True)
        self._ensure_storage()

    def _ensure_storage(self):
        if not self.storage_path.exists():
            self.storage_path.write_text(json.dumps([], indent=2))

    def _load(self) -> List[Dict[str, Any]]:
        try:
            content = self.storage_path.read_text()
            return json.loads(content) if content.strip() else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save(self, executions: List[Dict[str, Any]]):
        self.storage_path.write_text(json.dumps(executions, indent=2))

    def create(self, runbook_id: str, dry_run: bool = False) -> RunbookExecution:
        """Create a new execution record"""
        execution = RunbookExecution(
            id=str(uuid.uuid4()),
            runbook_id=runbook_id,
            started_at=datetime.now(timezone.utc).isoformat(),
            dry_run=dry_run,
        )
        executions = self._load()
        executions.append(execution.to_dict())
        self._save(executions)
        return execution

    def get(self, execution_id: str) -> Optional[RunbookExecution]:
        """Get execution by ID"""
        for e in self._load():
            if e.get("id") == execution_id:
                return RunbookExecution.from_dict(e)
        return None

    def list_by_runbook(self, runbook_id: str) -> List[RunbookExecution]:
        """List all executions for a runbook"""
        executions = self._load()
        return [
            RunbookExecution.from_dict(e)
            for e in executions
            if e.get("runbook_id") == runbook_id
        ]

    def update(self, execution_id: str, **kwargs) -> Optional[RunbookExecution]:
        """Update an execution"""
        executions = self._load()
        for e in executions:
            if e.get("id") == execution_id:
                e.update({k: v for k, v in kwargs.items() if v is not None})
                self._save(executions)
                return RunbookExecution.from_dict(e)
        return None

    def append_step_result(self, execution_id: str, step_index: int,
                          result: Dict[str, Any]) -> Optional[RunbookExecution]:
        """Append result for a step"""
        execution = self.get(execution_id)
        if not execution:
            return None
        
        step_result = {
            "step_index": step_index,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            **result
        }
        execution.step_results.append(step_result)
        return self.update(execution_id, step_results=execution.step_results)

    def add_approval_pending(self, execution_id: str, step_index: int,
                            policy_id: str, required_reviewers: List[str]) -> Optional[RunbookExecution]:
        """Add pending approval for a step"""
        execution = self.get(execution_id)
        if not execution:
            return None
        
        approval = {
            "id": str(uuid.uuid4()),
            "step_index": step_index,
            "policy_id": policy_id,
            "required_reviewers": required_reviewers,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        execution.approvals_pending.append(approval)
        return self.update(execution_id, approvals_pending=execution.approvals_pending)

    def approve_pending(self, execution_id: str, approval_id: str,
                       approved_by: str) -> Optional[RunbookExecution]:
        """Mark an approval as approved"""
        execution = self.get(execution_id)
        if not execution:
            return None
        
        for approval in execution.approvals_pending:
            if approval.get("id") == approval_id:
                approval["status"] = "approved"
                approval["approved_by"] = approved_by
                approval["approved_at"] = datetime.now(timezone.utc).isoformat()
                break
        
        return self.update(execution_id, approvals_pending=execution.approvals_pending)


# ── Execution Engine ─────────────────────────────────────────────────────────

class RunbookExecutionEngine:
    """Executes runbooks step-by-step with approval gates"""
    
    def __init__(self, templates_mgr: WorkflowTemplateManager,
                 policies_mgr: ApprovalPolicyManager,
                 runbooks_mgr: RunbookManager,
                 executions_mgr: RunbookExecutionManager):
        self.templates = templates_mgr
        self.policies = policies_mgr
        self.runbooks = runbooks_mgr
        self.executions = executions_mgr

    def execute_runbook(self, runbook_id: str, dry_run: bool = False) -> Dict[str, Any]:
        """Start execution of a runbook"""
        runbook = self.runbooks.get(runbook_id)
        if not runbook:
            return {"status": "error", "message": "Runbook not found"}
        
        if not runbook.enabled:
            return {"status": "error", "message": "Runbook is disabled"}

        execution = self.executions.create(runbook_id, dry_run=dry_run)
        
        return {
            "status": "started",
            "execution_id": execution.id,
            "runbook_id": runbook_id,
            "dry_run": dry_run,
            "total_steps": len(runbook.steps),
        }

    def get_next_step(self, execution_id: str) -> Dict[str, Any]:
        """Get the next step to execute"""
        execution = self.executions.get(execution_id)
        if not execution:
            return {"status": "error", "message": "Execution not found"}

        runbook = self.runbooks.get(execution.runbook_id)
        if not runbook:
            return {"status": "error", "message": "Runbook not found"}

        if execution.status != "running":
            return {
                "status": "complete",
                "execution_status": execution.status,
                "message": f"Execution is {execution.status}"
            }

        if execution.current_step >= len(runbook.steps):
            self.executions.update(
                execution_id,
                status="completed",
                ended_at=datetime.now(timezone.utc).isoformat()
            )
            return {"status": "complete", "message": "All steps completed"}

        step = runbook.steps[execution.current_step]
        template = self.templates.get(step.template_id)
        if not template:
            return {"status": "error", "message": f"Template {step.template_id} not found"}

        return {
            "status": "ok",
            "execution_id": execution_id,
            "step_index": step.step_index,
            "step_number": execution.current_step + 1,
            "total_steps": len(runbook.steps),
            "template": template.to_dict(),
            "params": step.params,
            "requires_approval": bool(step.approvals_policy_id),
            "approval_policy_id": step.approvals_policy_id,
        }

    def request_approval(self, execution_id: str) -> Dict[str, Any]:
        """Request approval for current step"""
        execution = self.executions.get(execution_id)
        if not execution:
            return {"status": "error", "message": "Execution not found"}

        runbook = self.runbooks.get(execution.runbook_id)
        if not runbook or execution.current_step >= len(runbook.steps):
            return {"status": "error", "message": "Invalid step"}

        step = runbook.steps[execution.current_step]
        if not step.approvals_policy_id:
            return {"status": "error", "message": "This step doesn't require approval"}

        policy = self.policies.get(step.approvals_policy_id)
        if not policy:
            return {"status": "error", "message": "Policy not found"}

        # Add to pending approvals
        self.executions.add_approval_pending(
            execution_id,
            step.step_index,
            policy.id,
            policy.required_reviewers
        )

        return {
            "status": "ok",
            "approval_requested": True,
            "policy_id": policy.id,
            "policy_name": policy.name,
            "required_reviewers": policy.required_reviewers,
            "approvals_pending": len(execution.approvals_pending) + 1,
        }

    def approve_step(self, execution_id: str, approval_id: str,
                     approved_by: str = "user") -> Dict[str, Any]:
        """Approve a pending step"""
        execution = self.executions.get(execution_id)
        if not execution:
            return {"status": "error", "message": "Execution not found"}

        self.executions.approve_pending(execution_id, approval_id, approved_by)

        return {
            "status": "ok",
            "message": "Step approved",
            "execution_id": execution_id,
        }

    def complete_step(self, execution_id: str, step_result: Dict[str, Any]) -> Dict[str, Any]:
        """Mark current step as complete and move to next"""
        execution = self.executions.get(execution_id)
        if not execution:
            return {"status": "error", "message": "Execution not found"}

        # Record the step result
        self.executions.append_step_result(
            execution_id,
            execution.current_step,
            step_result
        )

        # Move to next step
        self.executions.update(
            execution_id,
            current_step=execution.current_step + 1
        )

        return {
            "status": "ok",
            "message": "Step completed",
            "next_step_index": execution.current_step + 1,
        }

    def fail_step(self, execution_id: str, error_message: str) -> Dict[str, Any]:
        """Handle step failure"""
        execution = self.executions.get(execution_id)
        if not execution:
            return {"status": "error", "message": "Execution not found"}

        runbook = self.runbooks.get(execution.runbook_id)
        if not runbook or execution.current_step >= len(runbook.steps):
            return {"status": "error", "message": "Invalid step"}

        step = runbook.steps[execution.current_step]
        
        # Record the failure
        self.executions.append_step_result(
            execution_id,
            execution.current_step,
            {"status": "failed", "error": error_message}
        )

        # Handle failure based on step configuration
        if step.on_fail == "pause":
            self.executions.update(
                execution_id,
                status="paused",
                error_message=error_message
            )
            return {
                "status": "paused",
                "message": "Execution paused due to step failure",
                "error": error_message,
            }
        elif step.on_fail == "rollback":
            # Rollback would require additional state tracking
            self.executions.update(
                execution_id,
                status="failed",
                error_message=error_message,
                ended_at=datetime.now(timezone.utc).isoformat()
            )
            return {
                "status": "rollback",
                "message": "Execution rolled back",
                "error": error_message,
            }
        else:  # continue
            self.executions.update(
                execution_id,
                current_step=execution.current_step + 1
            )
            return {
                "status": "continue",
                "message": "Execution continuing despite step failure",
                "error": error_message,
            }


# ── TeamWorkflowManager ──────────────────────────────────────────────────────

class TeamWorkflowManager:
    """Unified interface for team workflow operations"""
    
    def __init__(self, storage_path: Path):
        self.storage_path = storage_path
        self.templates = WorkflowTemplateManager(storage_path)
        self.policies = ApprovalPolicyManager(storage_path)
        self.runbooks = RunbookManager(storage_path)
        self.executions = RunbookExecutionManager(storage_path)
        self.engine = RunbookExecutionEngine(self.templates, self.policies, self.runbooks, self.executions)

    def to_dict(self) -> Dict[str, Any]:
        """Export all workflows, policies, and runbooks"""
        return {
            "templates": [t.to_dict() for t in self.templates.list()],
            "policies": [p.to_dict() for p in self.policies.list()],
            "runbooks": [r.to_dict() for r in self.runbooks.list()],
        }

    def from_dict(self, data: Dict[str, Any]):
        """Import workflows, policies, and runbooks"""
        # Load templates
        existing_templates = self.templates._load()
        for template_data in data.get("templates", []):
            existing_templates.append(template_data)
        self.templates._save(existing_templates)

        # Load policies
        existing_policies = self.policies._load()
        for policy_data in data.get("policies", []):
            existing_policies.append(policy_data)
        self.policies._save(existing_policies)

        # Load runbooks
        existing_runbooks = self.runbooks._load()
        for runbook_data in data.get("runbooks", []):
            existing_runbooks.append(runbook_data)
        self.runbooks._save(existing_runbooks)
