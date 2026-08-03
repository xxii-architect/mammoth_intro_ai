import { useState, useEffect } from 'react'
import { Bot, Play, Info, ChevronRight } from 'lucide-react'
import { api } from '../api/client'

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
  const [agentPinned, setAgentPinned] = useState(false)
  const [approvalMode, setApprovalMode] = useState(true)

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

  const approveApproval = async (approvalId) => {
    try {
      await api(`/approvals/${approvalId}/approve`, { method: 'POST' })
      await refreshApprovals()
      await refreshTimeline()
    } catch (_) {}
  }

  useEffect(() => {
    refreshAgents()
    refreshTimeline()
    refreshApprovals()
    const t = setInterval(() => {
      refreshAgents()
      refreshTimeline()
      refreshApprovals()
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
      setOutput(JSON.stringify(res, null, 2))
    } catch (e) {
      setOutput(`Error: ${e.message}`)
    } finally {
      setRunning(false)
      await Promise.all([refreshAgents(), refreshTimeline()])
    }
  }

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

            <button onClick={run} disabled={running}
              style={{ background: 'var(--photon)', color: '#050608', fontWeight: 700, fontSize: '0.85rem', padding: '8px 20px', borderRadius: 8, border: 'none', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8, opacity: running ? 0.7 : 1 }}>
              <Play size={14} /> {running ? 'Running…' : 'Run Agent'}
            </button>
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
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ fontSize: '0.9rem', fontWeight: 600 }}>Thought Stream</h3>
              <span style={{
                fontSize: '0.68rem', fontFamily: 'JetBrains Mono,monospace',
                textTransform: 'uppercase', letterSpacing: '0.12em',
                padding: '2px 8px', borderRadius: 20,
                background: running ? 'rgba(77,166,255,0.15)' : 'rgba(255,255,255,0.05)',
                color: running ? 'var(--photon)' : 'var(--txt-mut)',
              }}>
                {running ? 'RUNNING' : 'IDLE'}
              </span>
            </div>

            {agents.length > 0 && (
              <div style={{ marginTop: 8 }}>
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
