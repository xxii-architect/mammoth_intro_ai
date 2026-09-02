import React, { useState, useEffect } from "react";
import "./TeamWorkflowsPage.css";

const TeamWorkflowsPage = () => {
  const [activeTab, setActiveTab] = useState("templates");
  const [templates, setTemplates] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [runbooks, setRunbooks] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedRunbook, setSelectedRunbook] = useState(null);
  const [executingRunbook, setExecutingRunbook] = useState(null);

  const apiBase = "http://localhost:8000/api/team";

  // Load templates
  useEffect(() => {
    if (activeTab === "templates") {
      loadTemplates();
    }
  }, [activeTab]);

  // Load policies
  useEffect(() => {
    if (activeTab === "policies") {
      loadPolicies();
    }
  }, [activeTab]);

  // Load runbooks
  useEffect(() => {
    if (activeTab === "runbooks") {
      loadRunbooks();
    }
  }, [activeTab]);

  const loadTemplates = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/workflow-templates`);
      const data = await response.json();
      if (data.status === "ok") {
        setTemplates(data.templates || []);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadPolicies = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/approval-policies`);
      const data = await response.json();
      if (data.status === "ok") {
        setPolicies(data.policies || []);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadRunbooks = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/runbooks`);
      const data = await response.json();
      if (data.status === "ok") {
        setRunbooks(data.runbooks || []);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const deleteTemplate = async (templateId) => {
    if (window.confirm("Delete this template?")) {
      try {
        const response = await fetch(`${apiBase}/workflow-templates/${templateId}`, {
          method: "DELETE",
        });
        const data = await response.json();
        if (data.status === "ok") {
          loadTemplates();
        }
      } catch (err) {
        setError(err.message);
      }
    }
  };

  const deletePolicy = async (policyId) => {
    if (window.confirm("Delete this policy?")) {
      try {
        const response = await fetch(`${apiBase}/approval-policies/${policyId}`, {
          method: "DELETE",
        });
        const data = await response.json();
        if (data.status === "ok") {
          loadPolicies();
        }
      } catch (err) {
        setError(err.message);
      }
    }
  };

  const deleteRunbook = async (runbookId) => {
    if (window.confirm("Delete this runbook?")) {
      try {
        const response = await fetch(`${apiBase}/runbooks/${runbookId}`, {
          method: "DELETE",
        });
        const data = await response.json();
        if (data.status === "ok") {
          loadRunbooks();
        }
      } catch (err) {
        setError(err.message);
      }
    }
  };

  const executeRunbook = async (runbookId, dryRun = false) => {
    setLoading(true);
    try {
      const response = await fetch(`${apiBase}/runbooks/${runbookId}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dry_run: dryRun }),
      });
      const data = await response.json();
      if (data.status === "started") {
        setExecutingRunbook({
          runbookId,
          executionId: data.execution_id,
          totalSteps: data.total_steps,
          dryRun,
        });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (executingRunbook) {
    return (
      <WorkflowExecutionPanel
        runbookId={executingRunbook.runbookId}
        executionId={executingRunbook.executionId}
        totalSteps={executingRunbook.totalSteps}
        dryRun={executingRunbook.dryRun}
        onComplete={() => {
          setExecutingRunbook(null);
          loadRunbooks();
        }}
        onCancel={() => setExecutingRunbook(null)}
      />
    );
  }

  return (
    <div className="team-workflows-page">
      <div className="header">
        <h1>🚀 Team Workflows</h1>
        <p>Reusable workflow templates, approval policies, and runbooks for your team</p>
      </div>

      {error && (
        <div className="error-banner">
          ⚠️ {error}
          <button onClick={() => setError("")}>×</button>
        </div>
      )}

      <div className="tabs">
        <button
          className={`tab ${activeTab === "templates" ? "active" : ""}`}
          onClick={() => setActiveTab("templates")}
        >
          📋 Templates
        </button>
        <button
          className={`tab ${activeTab === "policies" ? "active" : ""}`}
          onClick={() => setActiveTab("policies")}
        >
          ✅ Approval Policies
        </button>
        <button
          className={`tab ${activeTab === "runbooks" ? "active" : ""}`}
          onClick={() => setActiveTab("runbooks")}
        >
          ▶️ Runbooks
        </button>
      </div>

      <div className="content">
        {activeTab === "templates" && <TemplatesTab templates={templates} onDelete={deleteTemplate} onRefresh={loadTemplates} />}
        {activeTab === "policies" && <PoliciesTab policies={policies} onDelete={deletePolicy} onRefresh={loadPolicies} />}
        {activeTab === "runbooks" && (
          <RunbooksTab
            runbooks={runbooks}
            templates={templates}
            policies={policies}
            onDelete={deleteRunbook}
            onExecute={executeRunbook}
            onRefresh={loadRunbooks}
          />
        )}
      </div>

      {loading && <div className="loading">Loading...</div>}
    </div>
  );
};

const TemplatesTab = ({ templates, onDelete, onRefresh }) => {
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    intent: "",
    prompt_shape: {},
    estimated_duration_min: 30,
    tags: [],
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch("http://localhost:8000/api/team/workflow-templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      const data = await response.json();
      if (data.status === "ok") {
        setShowForm(false);
        setFormData({
          name: "",
          description: "",
          intent: "",
          prompt_shape: {},
          estimated_duration_min: 30,
          tags: [],
        });
        onRefresh();
      }
    } catch (err) {
      console.error("Error creating template:", err);
    }
  };

  return (
    <div className="tab-content">
      <div className="tab-header">
        <h2>Workflow Templates</h2>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ New Template"}
        </button>
      </div>

      {showForm && (
        <form className="form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>
          <div className="form-group">
            <label>Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>
          <div className="form-group">
            <label>Intent</label>
            <input
              type="text"
              value={formData.intent}
              onChange={(e) => setFormData({ ...formData, intent: e.target.value })}
              required
            />
          </div>
          <div className="form-group">
            <label>Estimated Duration (minutes)</label>
            <input
              type="number"
              value={formData.estimated_duration_min}
              onChange={(e) =>
                setFormData({ ...formData, estimated_duration_min: parseInt(e.target.value) })
              }
              min="1"
            />
          </div>
          <button type="submit" className="btn-primary">
            Create Template
          </button>
        </form>
      )}

      <div className="items-grid">
        {templates.length === 0 ? (
          <p className="empty">No templates yet. Create one to get started!</p>
        ) : (
          templates.map((template) => (
            <div key={template.id} className="item-card">
              <div className="item-header">
                <h3>{template.name}</h3>
                <button
                  className="btn-delete"
                  onClick={() => onDelete(template.id)}
                  title="Delete"
                >
                  🗑️
                </button>
              </div>
              <p className="item-description">{template.description}</p>
              <div className="item-meta">
                <span>🎯 {template.intent}</span>
                <span>⏱️ ~{template.estimated_duration_min}min</span>
              </div>
              {template.tags && template.tags.length > 0 && (
                <div className="tags">
                  {template.tags.map((tag) => (
                    <span key={tag} className="tag">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

const PoliciesTab = ({ policies, onDelete, onRefresh }) => {
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    policy_type: "require_all",
    triggers: [],
    required_reviewers: [],
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch("http://localhost:8000/api/team/approval-policies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      const data = await response.json();
      if (data.status === "ok") {
        setShowForm(false);
        setFormData({
          name: "",
          policy_type: "require_all",
          triggers: [],
          required_reviewers: [],
        });
        onRefresh();
      }
    } catch (err) {
      console.error("Error creating policy:", err);
    }
  };

  return (
    <div className="tab-content">
      <div className="tab-header">
        <h2>Approval Policies</h2>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ New Policy"}
        </button>
      </div>

      {showForm && (
        <form className="form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>
          <div className="form-group">
            <label>Policy Type</label>
            <select
              value={formData.policy_type}
              onChange={(e) => setFormData({ ...formData, policy_type: e.target.value })}
            >
              <option value="require_all">Require All Approvals</option>
              <option value="require_any_one">Require Any One Approval</option>
              <option value="auto_approve">Auto-Approve</option>
            </select>
          </div>
          <div className="form-group">
            <label>Required Reviewers (comma-separated)</label>
            <input
              type="text"
              value={formData.required_reviewers.join(", ")}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  required_reviewers: e.target.value.split(",").map((r) => r.trim()),
                })
              }
            />
          </div>
          <button type="submit" className="btn-primary">
            Create Policy
          </button>
        </form>
      )}

      <div className="items-grid">
        {policies.length === 0 ? (
          <p className="empty">No policies yet. Create one to manage approvals!</p>
        ) : (
          policies.map((policy) => (
            <div key={policy.id} className="item-card">
              <div className="item-header">
                <h3>{policy.name}</h3>
                <button
                  className="btn-delete"
                  onClick={() => onDelete(policy.id)}
                  title="Delete"
                >
                  🗑️
                </button>
              </div>
              <div className="item-meta">
                <span>📋 {policy.policy_type}</span>
                {policy.required_reviewers && policy.required_reviewers.length > 0 && (
                  <span>👥 {policy.required_reviewers.join(", ")}</span>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

const RunbooksTab = ({ runbooks, templates, policies, onDelete, onExecute, onRefresh }) => {
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    steps: [],
    tags: [],
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await fetch("http://localhost:8000/api/team/runbooks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      const data = await response.json();
      if (data.status === "ok") {
        setShowForm(false);
        setFormData({
          name: "",
          description: "",
          steps: [],
          tags: [],
        });
        onRefresh();
      }
    } catch (err) {
      console.error("Error creating runbook:", err);
    }
  };

  return (
    <div className="tab-content">
      <div className="tab-header">
        <h2>Runbooks</h2>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ New Runbook"}
        </button>
      </div>

      {showForm && (
        <form className="form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>
          <div className="form-group">
            <label>Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            />
          </div>
          <button type="submit" className="btn-primary">
            Create Runbook
          </button>
        </form>
      )}

      <div className="items-grid">
        {runbooks.length === 0 ? (
          <p className="empty">No runbooks yet. Create one to automate workflows!</p>
        ) : (
          runbooks.map((runbook) => (
            <div key={runbook.id} className="item-card">
              <div className="item-header">
                <h3>{runbook.name}</h3>
                <div className="item-actions">
                  <button
                    className="btn-execute"
                    onClick={() => onExecute(runbook.id)}
                    title="Execute"
                  >
                    ▶️
                  </button>
                  <button
                    className="btn-delete"
                    onClick={() => onDelete(runbook.id)}
                    title="Delete"
                  >
                    🗑️
                  </button>
                </div>
              </div>
              <p className="item-description">{runbook.description}</p>
              <div className="item-meta">
                <span>📚 {runbook.steps ? runbook.steps.length : 0} steps</span>
                <span>{runbook.enabled ? "✅ Enabled" : "⛔ Disabled"}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

const WorkflowExecutionPanel = ({ runbookId, executionId, totalSteps, dryRun, onComplete, onCancel }) => {
  const [execution, setExecution] = useState(null);
  const [currentStep, setCurrentStep] = useState(null);
  const [stepStatus, setStepStatus] = useState("pending"); // pending, running, approved, rejected, completed, failed
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [logs, setLogs] = useState([]);

  const apiBase = "http://localhost:8000/api/team";

  useEffect(() => {
    loadExecution();
    const interval = setInterval(loadExecution, 2000);
    return () => clearInterval(interval);
  }, [executionId]);

  useEffect(() => {
    if (execution && execution.status === "running") {
      getNextStep();
    }
  }, [execution]);

  const loadExecution = async () => {
    try {
      const response = await fetch(
        `${apiBase}/runbooks/${runbookId}/execute/${executionId}`
      );
      const data = await response.json();
      if (data.status === "ok") {
        setExecution(data.execution);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const getNextStep = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `${apiBase}/runbooks/${runbookId}/execute/${executionId}/next-step`,
        { method: "POST" }
      );
      const data = await response.json();
      if (data.status === "ok") {
        setCurrentStep(data);
        setStepStatus("running");
        addLog(`Step ${data.step_number}/${data.total_steps}: ${data.template.name}`);
      } else if (data.status === "complete") {
        addLog("Execution complete!");
        setTimeout(onComplete, 2000);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const approveStep = async () => {
    setLoading(true);
    try {
      const pendingApproval = execution.approvals_pending[0];
      const response = await fetch(
        `${apiBase}/runbooks/${runbookId}/execute/${executionId}/approve/${pendingApproval.id}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ approved_by: "user" }),
        }
      );
      const data = await response.json();
      if (data.status === "ok") {
        setStepStatus("approved");
        addLog("✅ Step approved!");
        setTimeout(() => completeStep(true), 1000);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const rejectStep = async () => {
    setStepStatus("rejected");
    addLog("❌ Step rejected!");
    setTimeout(() => completeStep(false), 1000);
  };

  const completeStep = async (success) => {
    setLoading(true);
    try {
      const response = await fetch(
        `${apiBase}/runbooks/${runbookId}/execute/${executionId}/step-result`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            success,
            result: { status: success ? "completed" : "failed" },
            error: success ? null : "Manual rejection",
          }),
        }
      );
      const data = await response.json();
      setStepStatus("completed");
      loadExecution();
      setTimeout(() => getNextStep(), 1000);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const addLog = (message) => {
    setLogs((prev) => [
      ...prev,
      {
        timestamp: new Date().toLocaleTimeString(),
        message,
      },
    ]);
  };

  const progressPercent = execution ? (execution.current_step / totalSteps) * 100 : 0;

  return (
    <div className="execution-panel">
      <div className="panel-header">
        <h2>🚀 Workflow Execution</h2>
        <div className="header-info">
          <span>{dryRun ? "🧪 Dry Run" : "Live Execution"}</span>
          <button className="btn-close" onClick={onCancel}>
            ×
          </button>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          ⚠️ {error}
          <button onClick={() => setError("")}>×</button>
        </div>
      )}

      <div className="progress-section">
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${progressPercent}%` }} />
        </div>
        <div className="progress-text">
          Step {execution ? execution.current_step : 0} of {totalSteps}
        </div>
      </div>

      {currentStep && (
        <div className="current-step">
          <h3>Current Step: {currentStep.template.name}</h3>
          <p>{currentStep.template.description}</p>

          {currentStep.requires_approval && execution?.approvals_pending.length > 0 && (
            <div className="approval-request">
              <h4>⚠️ Approval Required</h4>
              <p>Required reviewers: {execution.approvals_pending[0].required_reviewers.join(", ")}</p>
              <div className="approval-buttons">
                <button
                  className="btn-approve"
                  onClick={approveStep}
                  disabled={loading}
                >
                  ✅ Approve
                </button>
                <button
                  className="btn-reject"
                  onClick={rejectStep}
                  disabled={loading}
                >
                  ❌ Reject
                </button>
              </div>
            </div>
          )}

          {stepStatus === "running" && !currentStep.requires_approval && (
            <div className="step-running">
              <p>🔄 Executing step...</p>
              <button
                className="btn-complete"
                onClick={() => completeStep(true)}
                disabled={loading}
              >
                ✅ Mark Complete
              </button>
            </div>
          )}
        </div>
      )}

      <div className="logs-section">
        <h4>Execution Logs</h4>
        <div className="logs">
          {logs.map((log, idx) => (
            <div key={idx} className="log-entry">
              <span className="log-time">{log.timestamp}</span>
              <span className="log-message">{log.message}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default TeamWorkflowsPage;
