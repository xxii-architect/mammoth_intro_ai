"""
Test suite for Team Workflows system
"""

import json
import sys
from pathlib import Path
import tempfile
import shutil

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mammoth_os.team_workflows import (
    TeamWorkflowManager,
    WorkflowTemplate,
    ApprovalPolicy,
    Runbook,
    RunbookStep,
)


def test_workflow_templates():
    """Test workflow template CRUD operations"""
    print("Testing Workflow Templates...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TeamWorkflowManager(Path(tmpdir))
        
        # Create
        template = manager.templates.create(
            name="Deploy to Production",
            description="Production deployment workflow",
            intent="Deploy application to production",
            prompt_shape={"version": "string", "rollback": "boolean"},
            required_approvals=["approval_1"],
            estimated_duration_min=45,
            tags=["deployment", "production"]
        )
        
        assert template.name == "Deploy to Production"
        assert template.id is not None
        print("  OK: Template created")
        
        # Read
        retrieved = manager.templates.get(template.id)
        assert retrieved is not None
        assert retrieved.name == "Deploy to Production"
        print("  OK: Template retrieved")
        
        # List
        templates = manager.templates.list()
        assert len(templates) == 1
        print("  OK: Templates listed")
        
        # Update
        updated = manager.templates.update(
            template.id,
            name="Deploy to Production (Updated)"
        )
        assert updated.name == "Deploy to Production (Updated)"
        print("  OK: Template updated")
        
        # Delete
        success = manager.templates.delete(template.id)
        assert success
        templates_after = manager.templates.list()
        assert len(templates_after) == 0
        print("  OK: Template deleted")


def test_approval_policies():
    """Test approval policy CRUD operations"""
    print("\nTesting Approval Policies...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TeamWorkflowManager(Path(tmpdir))
        
        # Create
        policy = manager.policies.create(
            name="Founder Approval",
            policy_type="require_all",
            triggers=["production_deploy"],
            required_reviewers=["founder@company.com"],
        )
        
        assert policy.name == "Founder Approval"
        assert policy.policy_type == "require_all"
        print("  OK: Policy created")
        
        # Read
        retrieved = manager.policies.get(policy.id)
        assert retrieved is not None
        print("  OK: Policy retrieved")
        
        # List
        policies = manager.policies.list()
        assert len(policies) == 1
        print("  OK: Policies listed")
        
        # Update
        updated = manager.policies.update(
            policy.id,
            policy_type="require_any_one"
        )
        assert updated.policy_type == "require_any_one"
        print("  OK: Policy updated")
        
        # Delete
        success = manager.policies.delete(policy.id)
        assert success
        print("  OK: Policy deleted")


def test_runbooks():
    """Test runbook CRUD operations"""
    print("\nTesting Runbooks...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TeamWorkflowManager(Path(tmpdir))
        
        # Create template first
        template = manager.templates.create(
            name="Test Template",
            description="Test",
            intent="Test intent",
            prompt_shape={},
        )
        
        # Create runbook
        steps = [
            RunbookStep(
                step_index=0,
                template_id=template.id,
                approvals_policy_id=None,
                on_fail="pause",
                params={}
            )
        ]
        
        runbook = manager.runbooks.create(
            name="Test Runbook",
            description="Test runbook",
            steps=steps,
        )
        
        assert runbook.name == "Test Runbook"
        assert len(runbook.steps) == 1
        print("  OK: Runbook created")
        
        # Read
        retrieved = manager.runbooks.get(runbook.id)
        assert retrieved is not None
        print("  OK: Runbook retrieved")
        
        # List
        runbooks = manager.runbooks.list()
        assert len(runbooks) == 1
        print("  OK: Runbooks listed")
        
        # Update
        updated = manager.runbooks.update(
            runbook.id,
            name="Test Runbook (Updated)"
        )
        assert updated.name == "Test Runbook (Updated)"
        print("  OK: Runbook updated")
        
        # Delete
        success = manager.runbooks.delete(runbook.id)
        assert success
        print("  OK: Runbook deleted")


def test_runbook_execution():
    """Test runbook execution"""
    print("\nTesting Runbook Execution...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TeamWorkflowManager(Path(tmpdir))
        
        # Create template
        template = manager.templates.create(
            name="Test Template",
            description="Test",
            intent="Test intent",
            prompt_shape={},
        )
        
        # Create runbook
        steps = [
            RunbookStep(
                step_index=0,
                template_id=template.id,
                approvals_policy_id=None,
                on_fail="pause",
                params={}
            ),
            RunbookStep(
                step_index=1,
                template_id=template.id,
                approvals_policy_id=None,
                on_fail="pause",
                params={}
            ),
        ]
        
        runbook = manager.runbooks.create(
            name="Test Runbook",
            description="Test runbook",
            steps=steps,
        )
        
        # Start execution
        result = manager.engine.execute_runbook(runbook.id, dry_run=False)
        assert result["status"] == "started"
        execution_id = result["execution_id"]
        print("  OK: Execution started")
        
        # Get execution
        execution = manager.executions.get(execution_id)
        assert execution is not None
        assert execution.status == "running"
        print("  OK: Execution retrieved")
        
        # Get next step
        step_result = manager.engine.get_next_step(execution_id)
        assert step_result["status"] == "ok"
        assert step_result["step_number"] == 1
        print("  OK: Next step retrieved")
        
        # Complete step
        complete_result = manager.engine.complete_step(
            execution_id,
            {"status": "completed"}
        )
        assert complete_result["status"] == "ok"
        print("  OK: Step completed")
        
        # Get next step again
        step_result2 = manager.engine.get_next_step(execution_id)
        assert step_result2["status"] == "ok"
        assert step_result2["step_number"] == 2
        print("  OK: Second step retrieved")
        
        # Complete second step
        manager.engine.complete_step(execution_id, {"status": "completed"})
        
        # Get next step should now return complete
        step_result3 = manager.engine.get_next_step(execution_id)
        assert step_result3["status"] == "complete"
        print("  OK: All steps completed")
        
        # Get execution history
        history = manager.executions.list_by_runbook(runbook.id)
        assert len(history) == 1
        print("  OK: Execution history retrieved")


def test_approval_flow():
    """Test approval workflow"""
    print("\nTesting Approval Flow...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TeamWorkflowManager(Path(tmpdir))
        
        # Create approval policy
        policy = manager.policies.create(
            name="Test Policy",
            policy_type="require_all",
            triggers=["test"],
            required_reviewers=["reviewer@company.com"],
        )
        
        # Create template
        template = manager.templates.create(
            name="Test Template",
            description="Test",
            intent="Test intent",
            prompt_shape={},
            required_approvals=[policy.id],
        )
        
        # Create runbook with approval
        steps = [
            RunbookStep(
                step_index=0,
                template_id=template.id,
                approvals_policy_id=policy.id,
                on_fail="pause",
                params={}
            )
        ]
        
        runbook = manager.runbooks.create(
            name="Test Runbook",
            description="Test runbook",
            steps=steps,
        )
        
        # Start execution
        result = manager.engine.execute_runbook(runbook.id)
        execution_id = result["execution_id"]
        print("  OK: Execution started")
        
        # Get next step with approval requirement
        step_result = manager.engine.get_next_step(execution_id)
        assert step_result["requires_approval"] is True
        print("  OK: Approval required detected")
        
        # Request approval
        approval_result = manager.engine.request_approval(execution_id)
        assert approval_result["status"] == "ok"
        approval_id = approval_result.get("approval_id") or "test-approval"
        print("  OK: Approval requested")
        
        # Get execution to check pending approvals
        execution = manager.executions.get(execution_id)
        assert len(execution.approvals_pending) > 0
        print("  OK: Approval pending registered")
        
        # Approve step
        approve_result = manager.engine.approve_step(
            execution_id,
            execution.approvals_pending[0]["id"],
            approved_by="reviewer@company.com"
        )
        assert approve_result["status"] == "ok"
        print("  OK: Step approved")
        
        # Verify approval is marked
        execution = manager.executions.get(execution_id)
        assert execution.approvals_pending[0]["status"] == "approved"
        print("  OK: Approval status updated")


def test_export_import():
    """Test export and import of workflows"""
    print("\nTesting Export/Import...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = TeamWorkflowManager(Path(tmpdir))
        
        # Create template
        template = manager.templates.create(
            name="Test Template",
            description="Test",
            intent="Test intent",
            prompt_shape={},
        )
        
        # Create policy
        policy = manager.policies.create(
            name="Test Policy",
            policy_type="require_all",
            triggers=["test"],
        )
        
        # Create runbook
        runbook = manager.runbooks.create(
            name="Test Runbook",
            description="Test",
            steps=[],
        )
        
        # Export
        exported = manager.to_dict()
        assert len(exported["templates"]) == 1
        assert len(exported["policies"]) == 1
        assert len(exported["runbooks"]) == 1
        print("  OK: Workflows exported")
        
        # Create new manager and import
        with tempfile.TemporaryDirectory() as tmpdir2:
            manager2 = TeamWorkflowManager(Path(tmpdir2))
            manager2.from_dict(exported)
            
            # Verify import
            templates = manager2.templates.list()
            policies = manager2.policies.list()
            runbooks = manager2.runbooks.list()
            
            assert len(templates) == 1
            assert len(policies) == 1
            assert len(runbooks) == 1
            print("  OK: Workflows imported")


def main():
    """Run all tests"""
    print("=" * 60)
    print("Team Workflows Test Suite")
    print("=" * 60)
    
    try:
        test_workflow_templates()
        test_approval_policies()
        test_runbooks()
        test_runbook_execution()
        test_approval_flow()
        test_export_import()
        
        print("\n" + "=" * 60)
        print("All tests passed!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\nTest failed: {e}")
        return 1
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
