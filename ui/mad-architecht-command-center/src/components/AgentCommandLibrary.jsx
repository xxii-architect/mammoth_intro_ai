// AgentCommandLibrary.jsx
// Searchable command library for all MammothOS agents
import React, { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

const COMMANDS = [
  { agent: "OrchestratorAgent", cmd: "route", desc: "Route a task to the best agent for the job", example: '{ "task": "Build a login page" }' },
  { agent: "CodingAgent", cmd: "generate", desc: "Generate production-ready code from a prompt", example: '{ "prompt": "Create a React auth form" }' },
  { agent: "CodingAgent", cmd: "refactor", desc: "Refactor existing code for clarity and performance", example: '{ "code": "...", "goal": "simplify" }' },
  { agent: "PlannerAgent", cmd: "plan", desc: "Generate a structured step-by-step plan", example: '{ "goal": "Launch MVP in 2 weeks" }' },
  { agent: "PlannerAgent", cmd: "execute", desc: "Execute a plan autonomously step by step", example: '{ "plan_id": "plan_123" }' },
  { agent: "ATLASAgent", cmd: "lesson", desc: "Generate an adaptive lesson for a topic", example: '{ "topic": "React hooks", "level": "beginner" }' },
  { agent: "ATLASAgent", cmd: "quiz", desc: "Generate a quiz to test understanding", example: '{ "topic": "JavaScript closures" }' },
  { agent: "ReasoningAgent", cmd: "reflect", desc: "Run multi-step chain-of-thought reasoning", example: '{ "question": "Why is my API slow?" }' },
  { agent: "SearchAgent", cmd: "search", desc: "Search the workspace for files, code, or context", example: '{ "query": "auth middleware" }' },
  { agent: "SnapshotAgent", cmd: "snapshot", desc: "Capture the current registry and system state", example: '{}' },
  { agent: "SelfHealAgent", cmd: "diagnose", desc: "Diagnose failing agents and attempt recovery", example: '{ "agent": "CodingAgent" }' },
  { agent: "EvolutionAgent", cmd: "analyze", desc: "Analyze agent maturity and suggest upgrades", example: '{ "agent": "all" }' },
  { agent: "AuditEngine", cmd: "log", desc: "Query the structured audit trail", example: '{ "severity": "warning", "limit": 20 }' },
  { agent: "VectorStoreAgent", cmd: "store", desc: "Store an embedding in the user-scoped vector store", example: '{ "content": "...", "tags": ["lesson"] }' },
  { agent: "DeployAgent", cmd: "deploy", desc: "Deploy a project via Docker or systemd", example: '{ "project_path": "/opt/mammothos/app", "method": "systemd" }' },
];

export default function AgentCommandLibrary({ onClose }) {
  const [query, setQuery] = useState("");
  const [agentFilter, setAgentFilter] = useState("all");
  const dialogRef = useRef(null);

  const agents = useMemo(() => ["all", ...new Set(COMMANDS.map(c => c.agent))], []);

  const filtered = useMemo(() => {
    return COMMANDS.filter(c => {
      const matchesAgent = agentFilter === "all" || c.agent === agentFilter;
      const q = query.toLowerCase();
      const matchesQuery = !q || c.cmd.includes(q) || c.desc.toLowerCase().includes(q) || c.agent.toLowerCase().includes(q);
      return matchesAgent && matchesQuery;
    });
  }, [query, agentFilter]);

  useEffect(() => {
    const previousFocus = document.activeElement;
    dialogRef.current?.querySelector('input')?.focus();
    const onKeyDown = (event) => {
      if (event.key === "Escape" && onClose) {
        onClose();
      }
      if (event.key === "Tab") {
        const controls = [...(dialogRef.current?.querySelectorAll('button, input, select') || [])].filter(node => !node.disabled);
        const first = controls[0];
        const last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
    };
  }, [onClose]);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  const modal = (
    <div
      className="command-overlay"
      onClick={() => onClose && onClose()}
    >
      <div
        className="command-dialog"
        ref={dialogRef}
        role="dialog" aria-modal="true" aria-labelledby="command-library-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="command-header">
          <div>
            <h2 id="command-library-title">🦣 Command Library</h2>
            <p>Command examples, not a live availability check. Access and approvals are enforced by the backend.</p>
          </div>
          {onClose && (
            <button onClick={onClose} aria-label="Close command library">✕</button>
          )}
        </div>

        <div className="command-filters">
          <input
            aria-label="Search commands"
            placeholder="Search commands..."
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          <select
            aria-label="Filter commands by agent"
            value={agentFilter}
            onChange={e => setAgentFilter(e.target.value)}
          >
            {agents.map(a => <option key={a} value={a}>{a === "all" ? "All Agents" : a}</option>)}
          </select>
        </div>

        <div className="command-results">
          {filtered.length === 0 && (
            <p className="command-empty">No commands match your search.</p>
          )}
          {filtered.map((c, i) => (
            <div key={i} className="command-item">
              <header><strong>{c.agent}</strong><span>›</span><span>{c.cmd}</span></header>
              <p>{c.desc}</p>
              <code>{c.example}</code>
            </div>
          ))}
        </div>

        <div className="command-footer">
          {filtered.length} of {COMMANDS.length} commands
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
