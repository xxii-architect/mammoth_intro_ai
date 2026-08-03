import { useState, useEffect } from 'react'
import { Bot, Play, Info, ChevronRight, Brain, CheckCircle, AlertTriangle, XCircle, Loader } from 'lucide-react'
import { api } from '../api/client'
import RunHistoryPanel from '../components/RunHistoryPanel'

const INTENTS = [
  'plant_seed', 'field_ops', 'market_intel', 'reflection', 'brand_voice',
  'research_curriculum', 'research_survival', 'research_plants', 'compare_gear', 'summarize',
]

const INTENT_TO_AGENT = {
  plant_seed:          'plant_the_seed_agent',
  field_ops:           'field_ops_agent',
  market_intel:        'market_intel_agent',
  reflection:          'reflection_agent',
  brand_voice:         'brand_voice_agent',
  research_curriculum: 'research_agent',
  research_survival:   'research_agent',
  research_plants:     'research_agent',
  compare_gear:        'research_agent',
  summarize:           'research_agent',
}

const AGENT_TO_INTENT = {
  plant_the_seed_agent: 'plant_seed',
  field_ops_agent:      'field_ops',
  market_intel_agent:   'market_intel',
  reflection_agent:     'reflection',
  brand_voice_agent:    'brand_voice',
  research_agent:       'research_curriculum',
  coding_agent:         'summarize',
  community_engine_agent: 'summarize',
  custodial_agent:      'summarize',
}

const SMOKE_TESTS = [
  { agent_id: 'plant_the_seed_agent', intent: 'plant_seed', prompt: 'Smoke test: confirm plant seed agent is online in one sentence.' },
  { agent_id: 'field_ops_agent', intent: 'field_ops', prompt: 'Smoke test: return a one-line field operation checklist.' },
  { agent_id: 'market_intel_agent', intent: 'market_intel', prompt: 'Smoke test: provide one market signal in one sentence.' },
  { agent_id: 'reflection_agent', intent: 'reflection', prompt: 'Smoke test: provide a one-sentence reflection prompt.' },
  { agent_id: 'brand_voice_agent', intent: 'brand_voice', prompt: 'Smoke test: provide one sentence in brand voice.' },
  { agent_id: 'research_agent', intent: 'research_curriculum', prompt: 'Smoke test: summarize one curriculum tip in one sentence.' },
  { agent_id: 'coding_agent', intent: 'summarize', prompt: 'Smoke test: respond with one sentence confirming coding agent availability.' },
]

export default function AgentPage() {
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelected] = useState('')
  const [intent, setIntent] = useState('plant_seed')
  const [prompt, setPrompt] = useState('')
  const [temperature, setTemp] = useState(0.7)
  const [output, setOutput] = useState(null)
  const [running, setRunning] = useState(false)
  const [archOpen, setArchOpen] = useState(false)
  const [activity, setActivity] = useState([])
  const [tasks, setTasks] = useState([])
  const [approvals, setApprovals] = useState([])
  const [snapshots, setSnapshots] = useState([])
  const [agentPinned, setAgentPinned] = useState(false)
  const [approvalMode, setApprovalMode] = useState(true)
  const [thoughtSteps, setThoughtSteps] = useState([])
  const [traceOpen, setTraceOpen] = useState(true)
  const [runHistory, setRunHistory] = useState(() => {
    try {
      const raw = localStorage.getItem('mammoth_run_history')
      return raw ? JSON.parse(raw) : []
    } catch { return [] }
  })
  const [smokeRunning, setSmokeRunning] = useState(false)
  const [smokeResults, setSmokeResults] = useState([])
  const [executionMode, setExecutionMode] = useState('single')
  const [planRun, setPlanRun] = useState(null)

  const refreshAgents = async () => {
    try {
      const a = await api('/agents')
      setAgents(a)
      if ((!selectedAgent || !a.some(x => x.id === selectedAgent)) && a.length) {
        const mapped = INTENT_TO_AGENT[intent]
        const match = mapped ? a.find(x => x.id === mapped) : null
        setSelected(match ? match.id : a[0].id)
      }
    } catch (_) {}
  }

  const refreshTimeline = async () => {
    try {
      const [feed, taskList] = await Promise.all([api('/activity'), api('/tasks')])
      setActivity((feed || []).slice(-8).reverse())
      setTasks((taskList || []).slice(-8).reverse())
    } catch (_) {}
  }

  const refreshApprovals = async () => {
    try {
      const list = await api('/approvals')
      setApprovals(list || [])
    } catch (_) {}
  }

  const refreshSnapshots = async () => {
    try {
      const list = await api('/snapshots')
      setSnapshots(list || [])
    } catch (_) {}
  }

  const approveApproval = async (approvalId) => {
    try {
      await api(`/approvals/${approvalId}/approve`, { method: 'POST' })
      await refreshApprovals()
      await refreshTimeline()
      await refreshSnapshots()
    } catch (_) {}
  }

  const restoreSnapshot = async (snapshotId) => {
    try {
      await api(`/snapshots/${snapshotId}/restore`, { method: 'POST' })
      await Promise.all([refreshSnapshots(), refreshTimeline()])
    } catch (_) {}
  }

  useEffect(() => {
    refreshAgents()
    refreshTimeline()
    refreshApprovals()
    refreshSnapshots()
    const t = setInterval(() => {
      refreshAgents()
      refreshTimeline()
      refreshApprovals()
      refreshSnapshots()
    }, 2200)
    return () => clearInterval(t)
  }, [selectedAgent, intent, agentPinned])

  const chooseIntent = (i) => {
    setIntent(i)
    setAgentPinned(false)
    const mapped = INTENT_TO_AGENT[i]
    if (mapped) setSelected(mapped)
  }

  const chooseAgent = (agentId) => {
    setAgentPinned(true)
    setSelected(agentId)
    const mappedIntent = AGENT_TO_INTENT[agentId]
    if (mappedIntent) setIntent(mappedIntent)
  }

  const loadCodingTemplate = (template) => {
    setSelected('coding_agent')
    setIntent('summarize')
    setAgentPinned(true)
    setApprovalMode(true)
    setPrompt(template)
  }

  const persistRunHistory = (entries) => {
    setRunHistory(entries)
    localStorage.setItem('mammoth_run_history', JSON.stringify(entries))
  }

  const addRunHistoryEntry = (res, currentPrompt, currentAgent, currentIntent) => {
    const entry = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      created_at: new Date().toISOString(),
      agent_id: currentAgent,
      intent: currentIntent,
      prompt: currentPrompt,
      status: res?.status || 'unknown',
      task_id: res?.task_id || null,
    }
    setRunHistory(prev => {
      const next = [...prev, entry].slice(-20)
      localStorage.setItem('mammoth_run_history', JSON.stringify(next))
      return next
    })
  }

  const replayHistoryEntry = (entry) => {
    if (!entry) return
    if (entry.agent_id) chooseAgent(entry.agent_id)
    if (entry.intent) chooseIntent(entry.intent)
    setPrompt(entry.prompt || '')
  }

  const clearRunHistory = () => persistRunHistory([])

  const run = async () => {
    if (!prompt.trim() && !intent) return
    setRunning(true)
    setOutput(null)
    await refreshAgents()
    try {
      const res = await api('/run', {
        method: 'POST',
        body: { intent, payload: { prompt }, temperature, agent_id: selectedAgent, approval_mode: approvalMode },
      })
      if (res.thought_steps && res.thought_steps.length) setThoughtSteps(res.thought_steps)
      addRunHistoryEntry(res, prompt, selectedAgent, intent)
      setOutput(JSON.stringify(res, null, 2))
    } catch (e) {
      setThoughtSteps([{ ts: new Date().toISOString(), label: 'Request failed', detail: e.message, status: 'error' }])
      setOutput(`Error: ${e.message}`)
    } finally {
      setRunning(false)
      await Promise.all([refreshAgents(), refreshTimeline(), refreshApprovals(), refreshSnapshots()])
    }
  }

  const runPlanExecute = async () => {
    if (!prompt.trim()) return
    setRunning(true)
    setOutput(null)
    setPlanRun({
      status: 'ok',
      objective: prompt,
      plan_status: 'running',
      progress: { total: 0, executed: 0, completed: 0, pending_approval: 0, failed: 0 },
      plan_steps: [],
    })

    try {
      const res = await api('/plan-execute', {
        method: 'POST',
        body: { objective: prompt, temperature, approval_mode: approvalMode, stop_on_failure: true },
      })
      setPlanRun(res)
      addRunHistoryEntry(res, prompt, 'orchestrator', 'plan_execute')
      setOutput(JSON.stringify(res, null, 2))
      const summarizedThoughts = (res.plan_steps || []).map((step, idx) => ({
        ts: step.finished_at || new Date().toISOString(),
        label: `Plan step ${idx + 1}: ${step.title}`,
        detail: `${step.agent_id} • ${step.status} • ${step.duration_ms || 0}ms`,
        status: step.status === 'completed' ? 'success' : step.status === 'pending_approval' ? 'warning' : 'error',
      }))
      setThoughtSteps(summarizedThoughts)
    } catch (e) {
      setPlanRun({
        status: 'error',
        objective: prompt,
        plan_status: 'failed',
        progress: { total: 0, executed: 0, completed: 0, pending_approval: 0, failed: 1 },
        plan_steps: [],
        error: e.message,
      })
      setThoughtSteps([{ ts: new Date().toISOString(), label: 'Plan run failed', detail: e.message, status: 'error' }])
      setOutput(`Error: ${e.message}`)
    } finally {
      setRunning(false)
      await Promise.all([refreshAgents(), refreshTimeline(), refreshApprovals(), refreshSnapshots()])
    }
  }

  const runSmokeTests = async () => {
    if (smokeRunning || running) return
    setSmokeRunning(true)
    setSmokeResults([])
    const collected = []

    for (const spec of SMOKE_TESTS) {
      const startedAt = performance.now()
      try {
        const res = await api('/run', {
          method: 'POST',
          body: {
            intent: spec.intent,
            payload: { prompt: spec.prompt },
            temperature: 0.2,
            agent_id: spec.agent_id,
            approval_mode: false,
          },
        })
        const elapsedMs = Math.round(performance.now() - startedAt)
        const nestedStatus = res?.result?.status || ''
        const pass = res?.status === 'ok' && nestedStatus !== 'error'
        const rawPreview = res?.result?.output ?? res?.result?.preview ?? res?.error ?? ''
        const preview = typeof rawPreview === 'string' ? rawPreview : JSON.stringify(rawPreview)
        const item = {
          id: `${spec.agent_id}-${Date.now()}`,
          agent_id: spec.agent_id,
          intent: spec.intent,
          status: pass ? 'pass' : 'fail',
          runtime_status: nestedStatus || res?.status || 'unknown',
          duration_ms: elapsedMs,
          preview: preview.slice(0, 140),
        }
        collected.push(item)
        setSmokeResults([...collected])
      } catch (e) {
        const elapsedMs = Math.round(performance.now() - startedAt)
        const item = {
          id: `${spec.agent_id}-${Date.now()}`,
          agent_id: spec.agent_id,
          intent: spec.intent,
          status: 'fail',
          runtime_status: 'request_error',
          duration_ms: elapsedMs,
          preview: (e?.message || 'Request failed').slice(0, 140),
        }
        collected.push(item)
        setSmokeResults([...collected])
      }
    }

    setSmokeRunning(false)
    await Promise.all([refreshAgents(), refreshTimeline()])
  }

  const runPrimary = () => executionMode === 'plan' ? runPlanExecute() : run()

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Bot size={20} color="var(--violet)" /> Agent Console
      </h1>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
        <div style={{ flex: '1 1 420px', minWidth: 0 }}>
          <div className="glass-card-solid" style={{ padding: 16, marginBottom: 16 }}>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 12, alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Agent</label>
                <select className="filter-select" value={selectedAgent} onChange={e => chooseAgent(e.target.value)} style={{ padding: '6px 10px', fontSize: '0.82rem' }}>
                  {agents.length ? agents.map(a => (
                    <option key={a.id} value={a.id}>{a.name} ({(running && a.id === selectedAgent) || a.status === 'ACTIVE' ? 'ACTIVE' : a.status})</option>
                  )) : <option>Loading agents…</option>}
                </select>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Temp</label>
                <input type="range" min="0" max="1" step="0.1" value={temperature}
                  onChange={e => setTemp(parseFloat(e.target.value))}
                  style={{ width: 80, accentColor: 'var(--photon)' }} />
                <span style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--photon)' }}>{temperature.toFixed(1)}</span>
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.72rem', color: 'var(--txt-sec)' }}>
                <input type="checkbox" checked={approvalMode} onChange={e => setApprovalMode(e.target.checked)} />
                Preview first
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <label style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Mode</label>
                <select className="filter-select" value={executionMode} onChange={e => setExecutionMode(e.target.value)} style={{ padding: '6px 10px', fontSize: '0.78rem' }}>
                  <option value="single">Single Agent</option>
                  <option value="plan">Plan + Execute</option>
                </select>
              </div>
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
              {INTENTS.map(i => (
                <span key={i} onClick={() => chooseIntent(i)}
                  style={{
                    fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace',
                    padding: '4px 10px', borderRadius: 20, cursor: 'pointer',
                    border: `1px solid ${intent === i ? 'var(--photon)' : 'var(--border)'}`,
                    background: intent === i ? 'rgba(77,166,255,0.12)' : 'rgba(255,255,255,0.04)',
                    color: intent === i ? 'var(--photon)' : 'var(--txt-sec)',
                  }}>
                  {i}
                </span>
              ))}
            </div>

            <textarea value={prompt} onChange={e => setPrompt(e.target.value)}
              placeholder="Optional: additional prompt payload…"
              style={{ width: '100%', background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, fontSize: '0.85rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)', resize: 'none', height: 80, boxSizing: 'border-box', marginBottom: 12 }}
            />

            {selectedAgent === 'coding_agent' && (
              <div className="glass-card-solid" style={{ padding: 12, marginBottom: 12, borderLeft: '2px solid var(--cyan)' }}>
                <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Coding Shortcuts</p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  <button onClick={() => loadCodingTemplate('/create src/demo.txt\nHello from MammothOS')}
                    style={{ fontSize: '0.72rem', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', cursor: 'pointer' }}>
                    Create
                  </button>
                  <button onClick={() => loadCodingTemplate('/write src/demo.txt\nReplace this content')}
                    style={{ fontSize: '0.72rem', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', cursor: 'pointer' }}>
                    Write
                  </button>
                  <button onClick={() => loadCodingTemplate('/patch src/demo.txt\nUpdated content here')}
                    style={{ fontSize: '0.72rem', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', cursor: 'pointer' }}>
                    Patch
                  </button>
                  <button onClick={() => loadCodingTemplate('/insert src/demo.txt\nanchor text\n---\nInserted content')}
                    style={{ fontSize: '0.72rem', padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', cursor: 'pointer' }}>
                    Insert
                  </button>
                </div>
              </div>
            )}

            <button onClick={() => setArchOpen(o => !o)}
              style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', background: 'none', border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
              <ChevronRight size={12} style={{ transform: archOpen ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
              CLI Architecture Reference
            </button>
            {archOpen && (
              <div className="glass-card-solid" style={{ padding: 12, fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', borderLeft: '2px solid var(--cyan)', lineHeight: 1.7, marginBottom: 12 }}>
                <span style={{ color: 'var(--cyan)' }}>CLI Flow:</span> mammoth &lt;intent&gt; →{' '}
                <span style={{ color: 'var(--photon)' }}>api_server.py</span> (FastAPI :8000) →{' '}
                <span style={{ color: 'var(--violet)' }}>CortexRouter</span> → AutonomousEngine →{' '}
                CodingAgent / FieldOpsAgent / ResearchAgent
              </div>
            )}

            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={runPrimary} disabled={running || smokeRunning}
              style={{ background: executionMode === 'plan' ? 'var(--violet)' : 'var(--photon)', color: '#050608', fontWeight: 700, fontSize: '0.85rem', padding: '8px 20px', borderRadius: 8, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, opacity: (running || smokeRunning) ? 0.7 : 1 }}>
              <Play size={14} /> {running ? (executionMode === 'plan' ? 'Planning + Executing…' : 'Running…') : (executionMode === 'plan' ? 'Plan + Execute' : 'Run Agent')}
            </button>
            <button onClick={runSmokeTests} disabled={smokeRunning || running}
              style={{ background: 'rgba(255,255,255,0.08)', color: 'var(--txt-pri)', fontWeight: 600, fontSize: '0.78rem', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, opacity: (running || smokeRunning) ? 0.7 : 1 }}>
              {smokeRunning ? <Loader size={13} style={{ animation: 'spin 1s linear infinite' }} /> : <CheckCircle size={13} />}
              {smokeRunning ? `Smoke Test ${smokeResults.length}/${SMOKE_TESTS.length}` : `Run Smoke Test (${SMOKE_TESTS.length})`}
            </button>
            </div>
          </div>

          <div className="glass-card-solid" style={{ padding: 16, minHeight: 160, maxHeight: 400, overflowY: 'auto' }}>
            {output ? (
              <pre style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>{output}</pre>
            ) : (
              <div style={{ color: 'var(--txt-sec)', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                <Info size={16} /> Output will appear here when you run the agent.
              </div>
            )}
          </div>
        </div>

        <div style={{ width: 300, flexShrink: 0 }}>
          <div className="glass-card-solid" style={{ padding: 16 }}>
            <button onClick={() => setTraceOpen(o => !o)} style={{ background: 'none', border: 'none', cursor: 'pointer', width: '100%', padding: 0, marginBottom: traceOpen ? 12 : 0 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '0.9rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--txt-pri)' }}>
                  <Brain size={15} color="var(--violet)" /> Reasoning Trace
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {running && <Loader size={12} color="var(--photon)" style={{ animation: 'spin 1s linear infinite' }} />}
                  <span style={{
                    fontSize: '0.68rem', fontFamily: 'JetBrains Mono,monospace',
                    textTransform: 'uppercase', letterSpacing: '0.12em',
                    padding: '2px 8px', borderRadius: 20,
                    background: running ? 'rgba(77,166,255,0.15)' : 'rgba(255,255,255,0.05)',
                    color: running ? 'var(--photon)' : 'var(--txt-mut)',
                  }}>
                    {running ? 'THINKING' : thoughtSteps.length ? `${thoughtSteps.length} steps` : 'IDLE'}
                  </span>
                  <ChevronRight size={12} color="var(--txt-mut)" style={{ transform: traceOpen ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }} />
                </div>
              </div>
            </button>

            {traceOpen && (
              <div>
                {thoughtSteps.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 14 }}>
                    {thoughtSteps.map((step, i) => {
                      const icon = step.status === 'success' ? <CheckCircle size={12} color="#22c55e" />
                        : step.status === 'warning' ? <AlertTriangle size={12} color="#f59e0b" />
                        : step.status === 'error' ? <XCircle size={12} color="#f87171" />
                        : <ChevronRight size={12} color="var(--photon)" />
                      const borderCol = step.status === 'success' ? '#22c55e33'
                        : step.status === 'warning' ? '#f59e0b33'
                        : step.status === 'error' ? '#f8717133'
                        : 'rgba(77,166,255,0.15)'
                      return (
                        <div key={i} style={{ background: 'rgba(255,255,255,0.025)', border: `1px solid ${borderCol}`, borderRadius: 6, padding: '7px 10px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: step.detail ? 3 : 0 }}>
                            {icon}
                            <span style={{ fontSize: '0.76rem', color: 'var(--txt-pri)', fontWeight: 500 }}>{step.label}</span>
                            <span style={{ fontSize: '0.6rem', color: 'var(--txt-mut)', marginLeft: 'auto', fontFamily: 'JetBrains Mono,monospace' }}>{new Date(step.ts).toLocaleTimeString()}</span>
                          </div>
                          {step.detail && <div style={{ fontSize: '0.69rem', color: 'var(--txt-sec)', fontFamily: 'JetBrains Mono,monospace', lineHeight: 1.5, wordBreak: 'break-all' }}>{step.detail}</div>}
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem', marginBottom: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Brain size={13} color="var(--txt-mut)" /> Run the agent to see its reasoning steps here.
                  </div>
                )}

                {agents.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Registered Agents</p>
                    {agents.slice(0, 10).map(a => (
                      <div key={a.id} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderTop: '1px solid var(--border)', fontSize: '0.78rem' }}>
                        <span style={{ color: 'var(--txt-pri)' }}>{a.name}</span>
                        <span style={{ color: ((running && a.id === selectedAgent) || a.status === 'ACTIVE') ? '#22c55e' : 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.7rem' }}>
                          {(running && a.id === selectedAgent) || a.status === 'ACTIVE' ? 'ACTIVE' : a.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

              </div>
            )}

            <RunHistoryPanel
              entries={runHistory}
              onReplay={replayHistoryEntry}
              onClear={clearRunHistory}
            />

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Agent Smoke Test</p>
              {smokeResults.length ? smokeResults.map(item => (
                <div key={item.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.73rem' }}>{item.agent_id}</span>
                    <span style={{ fontSize: '0.66rem', textTransform: 'uppercase', color: item.status === 'pass' ? '#22c55e' : '#f87171', fontFamily: 'JetBrains Mono,monospace' }}>
                      {item.status}
                    </span>
                  </div>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.69rem', marginTop: 4 }}>
                    {item.intent} • {item.runtime_status} • {item.duration_ms}ms
                  </div>
                  <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4, fontFamily: 'JetBrains Mono,monospace' }}>
                    {item.preview}
                  </div>
                </div>
              )) : <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem' }}>No smoke test run yet.</div>}
            </div>

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Plan + Execute</p>
              {planRun ? (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.74rem' }}>{planRun.objective?.slice(0, 44) || 'Plan objective'}</span>
                    <span style={{ fontSize: '0.66rem', textTransform: 'uppercase', color: planRun.plan_status === 'completed' ? '#22c55e' : planRun.plan_status === 'pending_approval' ? '#f59e0b' : planRun.plan_status === 'running' ? 'var(--photon)' : '#f87171', fontFamily: 'JetBrains Mono,monospace' }}>
                      {planRun.plan_status || 'unknown'}
                    </span>
                  </div>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.68rem', marginBottom: 6 }}>
                    {(planRun.progress?.executed || 0)}/{(planRun.progress?.total || 0)} steps • completed {(planRun.progress?.completed || 0)} • pending {(planRun.progress?.pending_approval || 0)} • failed {(planRun.progress?.failed || 0)}
                  </div>
                  {(planRun.plan_steps || []).map((step, idx) => (
                    <div key={`${step.id || idx}-${idx}`} style={{ padding: '7px 0', borderTop: '1px solid var(--border)' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                        <span style={{ color: 'var(--txt-pri)', fontSize: '0.72rem' }}>{idx + 1}. {step.title}</span>
                        <span style={{ fontSize: '0.64rem', textTransform: 'uppercase', color: step.status === 'completed' ? '#22c55e' : step.status === 'pending_approval' ? '#f59e0b' : '#f87171', fontFamily: 'JetBrains Mono,monospace' }}>{step.status}</span>
                      </div>
                      <div style={{ color: 'var(--txt-sec)', fontSize: '0.67rem', marginTop: 3 }}>
                        {step.agent_id} • {step.intent} • {step.duration_ms || 0}ms
                      </div>
                    </div>
                  ))}
                </div>
              ) : <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem' }}>Switch Mode to Plan + Execute and run an objective to orchestrate multiple agents.</div>}
            </div>

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Task Queue</p>
              {tasks.length ? tasks.map(task => (
                <div key={task.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.76rem' }}>{task.title}</span>
                    <span style={{ fontSize: '0.67rem', textTransform: 'uppercase', color: task.status === 'completed' ? '#22c55e' : task.status === 'failed' ? '#f87171' : 'var(--photon)', fontFamily: 'JetBrains Mono,monospace' }}>{task.status}</span>
                  </div>
                  {task.description ? <div style={{ color: 'var(--txt-sec)', fontSize: '0.7rem', marginTop: 4 }}>{task.description}</div> : null}
                </div>
              )) : <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem' }}>No tasks yet.</div>}
            </div>

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Pending Approvals</p>
              {approvals.filter(a => a.status === 'pending').length ? approvals.filter(a => a.status === 'pending').map(approval => (
                <div key={approval.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.74rem' }}>{approval.operation}</span>
                    <button onClick={() => approveApproval(approval.id)} style={{ background: 'var(--photon)', color: '#050608', border: 'none', borderRadius: 6, padding: '4px 8px', fontSize: '0.68rem', cursor: 'pointer' }}>Approve</button>
                  </div>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.7rem', marginTop: 4 }}>{approval.target}</div>
                </div>
              )) : <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem' }}>No pending approvals.</div>}
            </div>

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Rollback Snapshots</p>
              {snapshots.length ? snapshots.slice().reverse().slice(0, 8).map(snapshot => (
                <div key={snapshot.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.74rem' }}>{snapshot.operation}</span>
                    <button onClick={() => restoreSnapshot(snapshot.id)} style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--txt-pri)', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 8px', fontSize: '0.68rem', cursor: 'pointer' }}>Restore</button>
                  </div>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.7rem', marginTop: 4 }}>{snapshot.file_path}</div>
                  <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4 }}>
                    {snapshot.existed_before ? 'Previous file captured' : 'New file snapshot'} • {new Date(snapshot.created_at).toLocaleTimeString()}
                  </div>
                </div>
              )) : <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem' }}>No snapshots yet.</div>}
            </div>

            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Live Activity</p>
              {activity.length ? activity.map(entry => (
                <div key={entry.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                  <div style={{ color: 'var(--txt-pri)', fontSize: '0.74rem', lineHeight: 1.5 }}>{entry.message}</div>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.66rem', marginTop: 4, fontFamily: 'JetBrains Mono,monospace' }}>{entry.agent_id || 'system'} • {new Date(entry.created_at).toLocaleTimeString()}</div>
                </div>
              )) : <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem' }}>No activity yet.</div>}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
