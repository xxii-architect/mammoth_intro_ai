// AgentCommandLibrary.jsx
// Searchable command library for all MammothOS agents
import React, { useEffect, useMemo, useState } from "react";
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
    const onKeyDown = (event) => {
      if (event.key === "Escape" && onClose) {
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const modal = (
    <div
      className="fixed inset-0 bg-black/70 z-[1200] flex items-start sm:items-center justify-center p-3 sm:p-4 overflow-y-auto"
      onClick={() => onClose && onClose()}
    >
      <div
        className="bg-[#1a1a2e] border border-[#3d3d5c] rounded-2xl w-full max-w-3xl max-h-[calc(100vh-1.5rem)] sm:max-h-[88vh] overflow-hidden flex flex-col my-2 sm:my-0"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between p-5 border-b border-[#3d3d5c]">
          <div>
            <h2 className="text-white text-xl font-bold">🦣 Command Library</h2>
            <p className="text-[#8888aa] text-sm mt-0.5">All MammothOS agent capabilities</p>
          </div>
          {onClose && (
            <button onClick={onClose} className="text-[#8888aa] hover:text-white text-xl">✕</button>
          )}
        </div>

        <div className="flex gap-3 p-4 border-b border-[#3d3d5c]">
          <input
            className="flex-1 bg-[#0d0d1a] border border-[#3d3d5c] rounded-lg px-3 py-2 text-white text-sm placeholder-[#555577] focus:outline-none focus:border-[#6655cc]"
            placeholder="Search commands..."
            value={query}
            onChange={e => setQuery(e.target.value)}
            autoFocus
          />
          <select
            className="bg-[#0d0d1a] border border-[#3d3d5c] rounded-lg px-3 py-2 text-white text-sm focus:outline-none min-w-[140px]"
            value={agentFilter}
            onChange={e => setAgentFilter(e.target.value)}
          >
            {agents.map(a => <option key={a} value={a}>{a === "all" ? "All Agents" : a}</option>)}
          </select>
        </div>

        <div className="overflow-y-auto flex-1 p-4 space-y-2">
          {filtered.length === 0 && (
            <p className="text-[#555577] text-sm text-center py-8">No commands match your search.</p>
          )}
          {filtered.map((c, i) => (
            <div key={i} className="bg-[#0d0d1a] border border-[#2a2a45] rounded-xl p-4 hover:border-[#6655cc] transition-colors">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[#6655cc] font-mono text-sm font-bold">{c.agent}</span>
                <span className="text-[#555577]">›</span>
                <span className="text-white font-mono text-sm">{c.cmd}</span>
              </div>
              <p className="text-[#aaaacc] text-sm mb-2">{c.desc}</p>
              <code className="text-[#555577] text-xs font-mono block">{c.example}</code>
            </div>
          ))}
        </div>

        <div className="p-3 border-t border-[#3d3d5c] text-center text-[#555577] text-xs">
          {filtered.length} of {COMMANDS.length} commands
        </div>
      </div>
    </div>
  );

  return createPortal(modal, document.body);
}
