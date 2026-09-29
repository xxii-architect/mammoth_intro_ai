# Team Workflows System

The Team Workflows system provides repeatable, auditable ways for teams to run complex workflows without re-typing prompts or approval gates every time.

## Overview

The system consists of three main components:

### 1. **Workflow Templates**
Saved prompts and parameter templates that define how a workflow should execute.

**Fields:**
- `id`: Unique identifier
- `name`: Template name
- `description`: What this template does
- `intent`: The goal/purpose of the workflow
- `prompt_shape`: Template for parameters/inputs
- `required_approvals`: List of approval policy IDs
- `estimated_duration_min`: Expected execution time
- `tags`: Categorization tags
- `owner`: Creator/owner of the template

**Use Cases:**
- "Deploy to production" template
- "Run test suite" template
- "Generate documentation" template
- "Code review" template

### 2. **Approval Policies**
Rules governing who needs to approve workflow steps.

**Fields:**
- `id`: Unique identifier
- `name`: Policy name
- `policy_type`: 
  - `require_all`: All reviewers must approve
  - `require_any_one`: Any single approval is sufficient
  - `auto_approve`: Automatic approval (for trusted workflows)
- `triggers`: Events that trigger this policy
- `required_reviewers`: Users/roles who can approve
- `auto_approve_conditions`: Conditions for automatic approval

**Use Cases:**
- "Founders approve all production deploys"
- "Engineers can self-approve tests"
- "Security team reviews all data access changes"

### 3. **Runbooks**
Multi-step workflows combining templates and approval policies.

**Fields:**
- `id`: Unique identifier
- `name`: Runbook name
- `description`: What this runbook accomplishes
- `steps`: Array of RunbookStep objects
  - `step_index`: Position in the workflow
  - `template_id`: Reference to a template
  - `approvals_policy_id`: Reference to approval policy (optional)
  - `on_fail`: Action on failure (`pause`, `rollback`, `continue`)
  - `params`: Step-specific parameters
- `owner`: Creator/owner
- `tags`: Categorization
- `enabled`: Whether this runbook is active
- `dry_run_mode`: Preview mode (no actual execution)

## API Endpoints

### Workflow Templates
```
GET    /api/team/workflow-templates                 # List all templates
POST   /api/team/workflow-templates                 # Create template
GET    /api/team/workflow-templates/{template_id}   # Get template
POST   /api/team/workflow-templates/{template_id}   # Update template
DELETE /api/team/workflow-templates/{template_id}   # Delete template
```

### Approval Policies
```
GET    /api/team/approval-policies                  # List all policies
POST   /api/team/approval-policies                  # Create policy
GET    /api/team/approval-policies/{policy_id}      # Get policy
POST   /api/team/approval-policies/{policy_id}      # Update policy
DELETE /api/team/approval-policies/{policy_id}      # Delete policy
```

### Runbooks
```
GET    /api/team/runbooks                           # List all runbooks
POST   /api/team/runbooks                           # Create runbook
GET    /api/team/runbooks/{runbook_id}              # Get runbook
POST   /api/team/runbooks/{runbook_id}              # Update runbook
DELETE /api/team/runbooks/{runbook_id}              # Delete runbook
```

### Runbook Execution
```
POST   /api/team/runbooks/{runbook_id}/execute
       # Start execution (request body: { dry_run: boolean })
       # Returns: { status, execution_id, total_steps }

GET    /api/team/runbooks/{runbook_id}/execute/{execution_id}
       # Get execution status

POST   /api/team/runbooks/{runbook_id}/execute/{execution_id}/next-step
       # Get the next step to execute

POST   /api/team/runbooks/{runbook_id}/execute/{execution_id}/step-result
       # Record step result
       # Body: { success: boolean, result: {...}, error?: string }

POST   /api/team/runbooks/{runbook_id}/execute/{execution_id}/request-approval
       # Request approval for current step

POST   /api/team/runbooks/{runbook_id}/execute/{execution_id}/approve/{approval_id}
       # Approve a pending step
       # Body: { approved_by: string }

GET    /api/team/runbooks/{runbook_id}/history
       # Get execution history for a runbook
```

## Usage Examples

### 1. Creating a Workflow Template

```python
# Create a template for deploying to production
template = manager.templates.create(
    name="Deploy to Production",
    description="Safe production deployment with health checks",
    intent="Deploy application to production environment",
    prompt_shape={
        "environment": "production",
        "version": "latest",
        "rollback_enabled": True,
    },
    required_approvals=["founder_approval"],
    estimated_duration_min=45,
    tags=["deployment", "production"]
)
```

### 2. Creating an Approval Policy

```python
# Create a policy requiring founder approval
policy = manager.policies.create(
    name="Founder Approval",
    policy_type="require_all",
    triggers=["production_deploy"],
    required_reviewers=["founder@company.com"],
    auto_approve_conditions={},
)
```

### 3. Creating a Runbook

```python
# Create a runbook that combines templates
steps = [
    RunbookStep(
        step_index=0,
        template_id=template.id,
        approvals_policy_id=policy.id,
        on_fail="pause",
        params={"version": "1.2.3"}
    ),
    RunbookStep(
        step_index=1,
        template_id=healthcheck_template.id,
        approvals_policy_id=None,
        on_fail="continue",
        params={}
    ),
]

runbook = manager.runbooks.create(
    name="Production Deployment Workflow",
    description="Full deployment with approvals and health checks",
    steps=steps,
    tags=["production", "deployment"]
)
```

### 4. Executing a Runbook

```python
# Start execution
result = manager.engine.execute_runbook(runbook.id, dry_run=False)
execution_id = result["execution_id"]

# Get next step
step = manager.engine.get_next_step(execution_id)

# If approval is needed
if step.get("requires_approval"):
    manager.engine.request_approval(execution_id)
    # ... wait for approval ...
    manager.engine.approve_step(execution_id, approval_id, approved_by="user")

# Mark step complete
manager.engine.complete_step(execution_id, {"status": "completed"})

# Get history
history = manager.executions.list_by_runbook(runbook.id)
```

## UI Features

### Templates Tab
- 📋 **Library**: View all saved templates
- ✏️ **Create**: New template with parameters
- 📊 **Preview**: See template structure before use
- 🏷️ **Tags**: Filter templates by category

### Policies Tab
- ✅ **List Policies**: View approval rules
- ⚙️ **Configure**: Set up approval chains
- 👥 **Assign Reviewers**: Specify who can approve
- 🔄 **Chain Rules**: Build complex approval workflows

### Runbooks Tab
- ▶️ **Execute**: Run a runbook with live progress
- 🧪 **Dry Run**: Preview without committing
- 📈 **Progress**: Step-by-step status tracking
- ⏸️ **Pause on Approval**: Built-in approval gates
- 📜 **History**: See all past executions
- 🔄 **Rollback**: Undo failed steps (if configured)

## Step Failure Handling

When a step fails, the runbook responds based on the `on_fail` setting:

- **`pause`**: Execution pauses and waits for manual intervention
- **`rollback`**: Attempts to undo the step and stop execution
- **`continue`**: Logs the error but continues to the next step

## Audit Trail

All workflow operations are logged:
- Template creation/updates/deletions
- Policy changes
- Runbook execution start/end
- Approval decisions with timestamp and approver
- Step results and errors

## Integration with Main Approvals System

The team workflows system integrates with MammothOS's approval infrastructure:

1. When a step requires approval, a record is created in `/api/approvals`
2. Approvals can be reviewed from the main dashboard
3. Approval records include full context and execution history
4. All decisions are audit-logged

## Storage

Currently, workflows are stored in `.mammoth/` directory as JSON files:
- `.mammoth/workflow_templates.json`
- `.mammoth/approval_policies.json`
- `.mammoth/runbooks.json`
- `.mammoth/runbook_executions.json`

This allows for:
- Easy export/import of workflows
- Version control friendly format
- Quick backup and restore

## Best Practices

1. **Template Reusability**: Create templates for recurring tasks
2. **Clear Naming**: Use descriptive names for templates and policies
3. **Approval Minimalism**: Keep approval chains simple (2-3 reviewers max)
4. **Dry Run First**: Always test runbooks with `dry_run=true` before production
5. **Step Failure Planning**: Set appropriate `on_fail` behavior for each step
6. **Audit Review**: Regularly review approval logs for security
7. **Tagging**: Use consistent tags for filtering and discovery

## Future Enhancements

- Database persistence (PostgreSQL/Supabase)
- Scheduled runbook execution (cron-like)
- Conditional steps (if/else logic)
- Webhook triggers for automated workflows
- Slack/email notifications for approvals
- Runbook versioning and rollback
- Advanced metrics and analytics
- Custom step types and plugins
