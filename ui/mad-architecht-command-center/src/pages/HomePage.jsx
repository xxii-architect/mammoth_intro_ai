import { useState, useEffect } from 'react'
import { Copy, ShieldCheck, Sparkles } from 'lucide-react'
import { api } from '../api/client'
import { loadSelfAuditHistory, normalizeSelfAuditEntry, runSystemSelfAudit } from '../api/diagnostics'
import { useInterval } from '../hooks/useApi'
import OnboardingGuide from '../components/OnboardingGuide'
import OnboardingChecklist from '../components/OnboardingChecklist'
import WorkspaceMemoryPanel from '../components/WorkspaceMemoryPanel'
import AtlasMemoryBadge from '../components/AtlasMemoryBadge'
import { useAuth } from '../lib/authContext'

function Sparkline({ points, color, gradId }) {
  return (
    <svg width="60" height="20" viewBox="0 0 60 20">
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={points} />
      {gradId && (
        <>
          <polyline fill={`url(#${gradId})`} stroke="none" points={`0,20 ${points} 60,20`} />
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.3" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
        </>
      )}
    </svg>
  )
}

const quickCmds = [
  'uvicorn api_server:app --reload',
  'npm run dev',
  'python -m cli.main status',
  'git status',
]

const bootSequence = [
  'BIOS: MammothOS kernel loaded',
  'ATLAS runtime: initialized',
  'LLM bridge: adapter routing online',
  'Telemetry buses: synchronized',
  'Command center: ready',
]

export default function HomePage({ setPage }) {
  const { user } = useAuth()
  const [status, setStatus] = useState(null)
  const [health, setHealth] = useState(null)
  const [buildlog, setBuildlog] = useState([])
  const [sales, setSales] = useState([])
  const [entitlements, setEntitlements] = useState(null)
  const [deploySnapshot, setDeploySnapshot] = useState(null)
  const [runtimeStatus, setRuntimeStatus] = useState(null)
  const [selfAudit, setSelfAudit] = useState(null)
  const [auditBusy, setAuditBusy] = useState(false)
  const [copied, setCopied] = useState(null)

  const fetchAll = async () => {
    try {
      const [s, h, b, sl, deploy, rt] = await Promise.all([
        api('/status'),
        api('/health'),
        api('/buildlog'),
        api('/logsale'),
        api('/runtime/deploy-snapshot'),
      ])
      setStatus(s)
      setHealth(h)
      setBuildlog(b)
      setSales(sl)
      setDeploySnapshot(deploy)
      const entitlementState = await api('/entitlements')
      setEntitlements(entitlementState)
    } catch (_) {}
  }

  useEffect(() => { fetchAll() }, [])
  useInterval(fetchAll, 30000)
  useEffect(() => {
    const history = loadSelfAuditHistory()
    if (history.length > 0) {
      setSelfAudit(history[0])
    }
  }, [])

  const copy = (cmd) => {
    navigator.clipboard.writeText(cmd)
    setCopied(cmd)
    setTimeout(() => setCopied(null), 1200)
  }

  const runSelfAudit = async () => {
    setAuditBusy(true)
    try {
      const { result } = await runSystemSelfAudit()
      setSelfAudit(result)
      setEntitlements(result.entitlements)
    } catch (error) {
      setSelfAudit(normalizeSelfAuditEntry({
        generatedAt: new Date().toLocaleString(),
        error: error.message,
        checks: [],
        recommendations: ['Fix the reported self-audit error before trusting the shell status.'],
      }))
    } finally {
      setAuditBusy(false)
    }
  }

  const auditChecks = Array.isArray(selfAudit?.checks) ? selfAudit.checks : []
  const auditRecommendations = Array.isArray(selfAudit?.recommendations) ? selfAudit.recommendations : []
  const auditObservability = selfAudit?.observability || null

  const stats = status ? [
    { label: 'Agent Sessions', value: String(status.agent_count || 0), color: 'var(--photon)', gradId: 'sg1', points: '0,15 8,12 16,8 24,14 32,6 40,10 48,4 56,7 60,3' },
    { label: 'CLI Commands Run', value: String(status.cli_commands_run || buildlog.length), color: 'var(--cyan)', gradId: 'sg2', points: '0,18 10,12 20,14 30,6 40,9 50,3 60,7' },
    { label: 'Active Models', value: String(status.active_models || 3), color: 'var(--violet)', gradId: null, points: '0,10 12,10 24,10 36,6 48,6 60,6' },
    { label: 'Uptime', value: status.uptime || '–', color: '#22c55e', gradId: 'sg4', points: '0,18 15,16 30,12 45,8 60,4' },
  ] : [
    { label: 'Agent Sessions', value: '–', color: 'var(--photon)', gradId: 'sg1', points: '0,15 60,15' },
    { label: 'CLI Commands Run', value: '–', color: 'var(--cyan)', gradId: 'sg2', points: '0,15 60,15' },
    { label: 'Active Models', value: '–', color: 'var(--violet)', gradId: null, points: '0,10 60,10' },
    { label: 'Uptime', value: '–', color: '#22c55e', gradId: 'sg4', points: '0,15 60,15' },
  ]

  const services = health?.services || []
  const missionCards = [
    {
      label: 'Current objective',
      value: services.some(s => s.status !== 'green') ? 'Restore stability' : 'Keep the loop tight',
      detail: services.some(s => s.status !== 'green') ? 'Fix the degraded runtime before broadening the next task.' : 'Stay on the healthy path and convert momentum into execution.',
    },
    {
      label: 'Best learning move',
      value: 'Finish one ATLAS loop',
      detail: 'Choose one skill track and close a concrete win before exploring wider modules.',
    },
    {
      label: 'Operator rhythm',
      value: `${Math.max(services.filter(s => s.status === 'green').length, 0)}/${Math.max(services.length, 1)} services green`,
      detail: 'Healthy runtime plus focused learning is the highest-leverage pattern right now.',
    },
  ]

  // combine recent activity from buildlog + sales
  const activity = [
    ...buildlog.slice(-3).reverse().map(e => ({
      dot: 'var(--photon)',
      msg: `Build: ${e.title || e.command || 'entry'}`,
      time: e.created_at ? new Date(e.created_at).toLocaleTimeString() : '',
    })),
    ...sales.slice(-3).reverse().map(e => ({
      dot: 'var(--cyan)',
      msg: `Sale: ${e.item} — $${e.amount}`,
      time: e.created_at ? new Date(e.created_at).toLocaleTimeString() : '',
    })),
  ].slice(0, 6)

  const fallbackActivity = [
    { dot: '#22c55e', msg: 'MammothOS Command Center started', time: 'now' },
  ]
  const displayName = String(user?.user_metadata?.display_name || user?.email?.split('@')?.[0] || 'Operator').trim() || 'Operator'
  const backendBase = (() => {
    try {
      return window.localStorage.getItem('mammoth_api_base_url') || window.location.origin
    } catch {
      return window.location.origin
    }
  })()
  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: '1.25rem', fontWeight: 800, marginBottom: 6, letterSpacing: '-0.01em' }}>
            {(() => {
              const h = new Date().getHours()
              if (h < 12) return `\u2600\ufe0f Good morning, ${displayName}`
              if (h < 17) return `\ud83c\udf24 Good afternoon, ${displayName}`
              if (h < 21) return `\ud83c\udf19 Good evening, ${displayName}`
              return `\ud83e\udda3 Late night build, ${displayName}?`
            })()}
          </h1>
          <p style={{ fontSize: '0.82rem', color: 'var(--txt-sec)', margin: 0, lineHeight: 1.6 }}>
            MammothOS is running. Your agents are ready.
          </p>
        </div>
        <AtlasMemoryBadge />
      </div>

      <div className="glass-card-solid" style={{ padding: 18, marginBottom: 20, position: 'relative', overflow: 'hidden' }}>
        <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(circle at top left, rgba(77,166,255,0.2), transparent 45%), radial-gradient(circle at bottom right, rgba(168,85,247,0.18), transparent 38%)' }} />
        <div style={{ position: 'relative', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 18, flexWrap: 'wrap' }}>
          <div style={{ maxWidth: 640 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, color: 'var(--photon)', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.16em', textTransform: 'uppercase' }}>
              <Sparkles size={12} /> Mammoth Stride
            </div>
            <h2 style={{ margin: '0 0 8px', fontSize: '1.25rem', lineHeight: 1.2, letterSpacing: '-0.02em' }}>Build momentum across the operator loop.</h2>
            <p style={{ margin: 0, color: 'var(--txt-sec)', lineHeight: 1.6, fontSize: '0.84rem' }}>
              Your best next move is to keep the system healthy, deepen the learning loop, and turn the latest ATLAS insights into a concrete action.
            </p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 10, minWidth: 320, flex: 1 }}>
            <div style={{ padding: '12px 14px', borderRadius: 12, border: '1px solid rgba(77,166,255,0.22)', background: 'rgba(77,166,255,0.07)' }}>
              <div style={{ fontSize: '0.62rem', letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--txt-mut)' }}>Focus</div>
              <div style={{ marginTop: 6, fontSize: '0.92rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Operator health</div>
              <div style={{ marginTop: 4, color: 'var(--txt-sec)', fontSize: '0.74rem' }}>{services.length ? `${services.filter(s => s.status === 'green').length}/${services.length} services green` : 'Checking runtime…'}</div>
            </div>
            <div style={{ padding: '12px 14px', borderRadius: 12, border: '1px solid rgba(0,245,212,0.22)', background: 'rgba(0,245,212,0.06)' }}>
              <div style={{ fontSize: '0.62rem', letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--txt-mut)' }}>Best next action</div>
              <div style={{ marginTop: 6, fontSize: '0.92rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Open lessons</div>
              <div style={{ marginTop: 4, color: 'var(--txt-sec)', fontSize: '0.74rem' }}>Keep the learning loop moving with a focused ATLAS module.</div>
            </div>
            <div style={{ padding: '12px 14px', borderRadius: 12, border: '1px solid rgba(168,85,247,0.22)', background: 'rgba(168,85,247,0.07)' }}>
              <div style={{ fontSize: '0.62rem', letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--txt-mut)' }}>Momentum</div>
              <div style={{ marginTop: 6, fontSize: '0.92rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{entitlements?.effective_tier || entitlements?.tier || 'explorer'}</div>
              <div style={{ marginTop: 4, color: 'var(--txt-sec)', fontSize: '0.74rem' }}>Tier is healthy and ready for the next upgrade slice.</div>
            </div>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12, marginBottom: 20 }}>
        {missionCards.map((card) => (
          <div key={card.label} className="glass-card-solid" style={{ padding: 16 }}>
            <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 8 }}>{card.label}</div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--txt-pri)', marginBottom: 6 }}>{card.value}</div>
            <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem', lineHeight: 1.5 }}>{card.detail}</div>
          </div>
        ))}
      </div>

      <OnboardingGuide currentPage="home" setPage={setPage} />
      <OnboardingChecklist setPage={setPage} />
      <div style={{ marginBottom: 24 }}>
        <WorkspaceMemoryPanel />
      </div>

      <div className="glass-card-solid" style={{ padding: 16, marginBottom: 24, borderLeft: '3px solid var(--violet)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 10 }}>
          <p style={{ margin: 0, fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700 }}>
            Live deploy verification
          </p>
          <button
            onClick={fetchAll}
            style={{ border: '1px solid var(--border)', borderRadius: 8, background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.72rem', padding: '6px 10px', cursor: 'pointer' }}
          >
            Refresh snapshot
          </button>
        </div>
        <div style={{ display: 'grid', gap: 6, color: 'var(--txt-sec)', fontSize: '0.76rem' }}>
          <div>Backend origin: <strong style={{ color: 'var(--photon)', fontFamily: 'JetBrains Mono,monospace' }}>{backendBase}</strong></div>
          <div>Repo root: <span style={{ fontFamily: 'JetBrains Mono,monospace' }}>{deploySnapshot?.repo_root || status?.repo_root || 'unknown'}</span></div>
          <div>Branch / commit: <span style={{ fontFamily: 'JetBrains Mono,monospace', color: 'var(--photon)' }}>{deploySnapshot?.git_branch || status?.git_branch || 'unknown'} @ {deploySnapshot?.git_commit || status?.git_commit || 'unknown'}</span></div>
          <div>Runtime: <strong style={{ color: deploySnapshot?.runtime_state === 'ready' ? '#22c55e' : '#f59e0b' }}>{deploySnapshot?.runtime_state || 'unknown'}</strong></div>
        </div>
      </div>

      {/* Runtime provider status strip */}
      {runtimeStatus && Array.isArray(runtimeStatus.providers) && (
        <div className="glass-card-solid" style={{ padding: '12px 16px', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              AI Provider Chain
            </span>
            <span style={{ fontSize: '0.7rem', fontFamily: 'JetBrains Mono,monospace', color: runtimeStatus.state === 'ready' ? '#22c55e' : '#f59e0b' }}>
              {runtimeStatus.active_model || runtimeStatus.active_adapter || 'unknown'} · {runtimeStatus.state}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {runtimeStatus.providers.map((p) => (
              <div key={p.provider} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 12px', borderRadius: 999,
                border: p.active ? '1px solid rgba(34,197,94,0.45)' : '1px solid rgba(255,255,255,0.08)',
                background: p.active ? 'rgba(34,197,94,0.08)' : 'rgba(255,255,255,0.03)',
              }}>
                <span style={{
                  width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
                  background: p.available ? (p.active ? '#22c55e' : '#94a3b8') : '#f87171',
                  boxShadow: p.active ? '0 0 8px rgba(34,197,94,0.6)' : 'none',
                }} />
                <span style={{ fontSize: '0.72rem', fontWeight: p.active ? 700 : 500, color: p.active ? '#22c55e' : 'var(--txt-sec)', textTransform: 'capitalize' }}>
                  {p.provider}
                </span>
                {p.active && (
                  <span style={{ fontSize: '0.6rem', padding: '1px 5px', borderRadius: 999, background: 'rgba(34,197,94,0.15)', color: '#22c55e', fontWeight: 700 }}>
                    ACTIVE
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: 12, marginBottom: 24 }}>
        {stats.map(s => (
          <div key={s.label} className="glass-card-solid" style={{ padding: 16 }}>
            <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 6 }}>{s.label}</p>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
              <span style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{s.value}</span>
              <Sparkline points={s.points} color={s.color} gradId={s.gradId} />
            </div>
          </div>
        ))}
      </div>

      <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 12 }}>
        Self Evaluation
      </p>
      <div className="glass-card-solid" style={{ padding: 18, marginBottom: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap', marginBottom: 16 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <ShieldCheck size={16} color="var(--cyan)" />
              <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>MammothOS self-audit</span>
            </div>
            <p style={{ fontSize: '0.82rem', color: 'var(--txt-sec)', lineHeight: 1.6, maxWidth: 620 }}>
              Run a shell-level audit across backend health, ATLAS evals, learner continuity, and monetization scaffolding without wiring billing yet.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <div style={{ padding: '8px 12px', borderRadius: 999, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', marginRight: 6 }}>Tier</span>
              <span style={{ fontSize: '0.76rem', color: 'var(--cyan)', fontWeight: 700, textTransform: 'capitalize' }}>{entitlements?.effective_tier || entitlements?.tier || 'explorer'}</span>
            </div>
            <button
              onClick={() => setPage?.('diagnostics')}
              style={{ padding: '9px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontWeight: 600, cursor: 'pointer' }}
            >
              Open diagnostics
            </button>
            <button
              onClick={runSelfAudit}
              disabled={auditBusy}
              style={{ padding: '9px 14px', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', fontWeight: 700, cursor: auditBusy ? 'not-allowed' : 'pointer', opacity: auditBusy ? 0.7 : 1 }}
            >
              {auditBusy ? 'Running audit…' : 'Run self-audit'}
            </button>
          </div>
        </div>

        {selfAudit ? (
          <div style={{ display: 'grid', gap: 16 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12 }}>
              <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                <div style={{ fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>Audit score</div>
                <div style={{ fontSize: '1.35rem', fontWeight: 800, color: 'var(--txt-pri)', fontFamily: 'JetBrains Mono,monospace' }}>{selfAudit.score || 'error'}</div>
              </div>
              <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                <div style={{ fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>Observed tier</div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--cyan)', textTransform: 'capitalize' }}>{selfAudit.tier || 'unknown'}</div>
              </div>
              <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                <div style={{ fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>CLI activity</div>
                <div style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--photon)' }}>{selfAudit.commandCount ?? '–'}</div>
              </div>
            </div>

            {selfAudit.error ? (
              <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid rgba(248,113,113,0.25)', background: 'rgba(248,113,113,0.06)', color: '#fca5a5', fontSize: '0.84rem' }}>
                Self-audit failed: {selfAudit.error}
              </div>
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>
                {auditChecks.map(check => (
                  <div key={check.label} style={{ padding: '12px 14px', borderRadius: 10, border: `1px solid ${check.passed ? 'rgba(34,197,94,0.25)' : 'rgba(248,113,113,0.25)'}`, background: check.passed ? 'rgba(34,197,94,0.06)' : 'rgba(248,113,113,0.06)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                      <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{check.label}</span>
                      <span style={{ fontSize: '0.68rem', fontWeight: 700, color: check.passed ? '#22c55e' : '#f87171' }}>
                        {check.passed ? 'PASS' : 'ATTN'}
                      </span>
                    </div>
                    <p style={{ fontSize: '0.76rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{check.detail}</p>
                  </div>
                ))}
              </div>
            )}

            {auditObservability ? (
              <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid rgba(77,166,255,0.2)', background: 'rgba(77,166,255,0.05)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <Sparkles size={15} color="var(--photon)" />
                  <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--txt-pri)' }}>ATLAS observability snapshot</span>
                </div>
                <p style={{ fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>
                  Learner pass rate {auditObservability.learner_pass_rate || 0}% • Eval pass rate {auditObservability.eval_pass_rate || 0}% • Plan runs {auditObservability.plan_runs || 0} • Guard rate {auditObservability.fab_guard_rate || 0}%
                </p>
              </div>
            ) : null}

            <div>
              <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 8 }}>
                Highest-value next UI upgrades
              </div>
              <div style={{ display: 'grid', gap: 8 }}>
                {auditRecommendations.map(item => (
                  <div key={item} style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', fontSize: '0.8rem', color: 'var(--txt-sec)' }}>
                    {item}
                  </div>
                ))}
              </div>
            </div>

            <p style={{ fontSize: '0.7rem', color: 'var(--txt-mut)' }}>
              Last run: {selfAudit.generatedAt}
            </p>
          </div>
        ) : (
          <p style={{ fontSize: '0.8rem', color: 'var(--txt-mut)' }}>
            No self-audit run yet. Launch one to see where the shell is strong and what to upgrade next.
          </p>
        )}
      </div>

      {/* Workspace status */}
      <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 12 }}>Workspace Status</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: 12, marginBottom: 24 }}>
        {services.length > 0 ? services.map(s => (
          <div key={s.label} className="glass-card-solid" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: s.status === 'green' ? '#22c55e' : s.status === 'yellow' ? '#eab308' : '#ef4444' }} />
              <span style={{ fontSize: '0.78rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{s.label}</span>
            </div>
            <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>{s.detail}</p>
          </div>
        )) : (
          <div className="glass-card-solid" style={{ padding: 16, color: 'var(--txt-mut)', fontSize: '0.82rem' }}>
            Connecting to backend…
          </div>
        )}
      </div>

      {/* Quick commands */}
      <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 12 }}>Quick Commands</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 24 }}>
        {quickCmds.map(cmd => (
          <button key={cmd} onClick={() => copy(cmd)} className="glass-card-solid"
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8, cursor: 'pointer', fontSize: '0.78rem', fontFamily: 'JetBrains Mono,monospace', color: copied === cmd ? 'var(--cyan)' : 'var(--photon)', background: 'var(--card)' }}>
            <Copy size={12} />
            {copied === cmd ? 'Copied!' : cmd}
          </button>
        ))}
      </div>

      {/* Recent activity */}
      <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 12 }}>Recent Activity</p>
      <div className="glass-card-solid" style={{ padding: '4px 16px' }}>
        {(activity.length ? activity : fallbackActivity).map((a, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: a.dot, flexShrink: 0 }} />
            <span style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', flex: 1 }}>{a.msg}</span>
            <span style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', whiteSpace: 'nowrap' }}>{a.time}</span>
          </div>
        ))}
      </div>

      <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', margin: '20px 0 12px' }}>
        Boot Sequence
      </p>
      <div className="glass-card-solid" style={{ padding: '10px 16px' }}>
        {bootSequence.map((line, i) => (
          <div key={line} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e', flexShrink: 0 }} />
            <span style={{ fontSize: '0.78rem', color: 'var(--txt-sec)', fontFamily: 'JetBrains Mono,monospace' }}>{line}</span>
          </div>
        ))}
      </div>

      <footer style={{ textAlign: 'center', padding: '32px 0 8px', color: 'var(--txt-mut)', fontSize: '0.7rem' }}>
        MammothOS Command Center 2036
      </footer>
    </div>
  )
}


