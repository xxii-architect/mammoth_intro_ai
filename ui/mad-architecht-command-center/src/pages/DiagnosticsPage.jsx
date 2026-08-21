import { useEffect, useState } from 'react'
import { Activity, RefreshCw, ShieldCheck, Trash2, Cpu, HeartPulse, Download } from 'lucide-react'
import { api, authorizedFetch } from '../api/client'
import { clearSelfAuditHistory, loadSelfAuditHistory, runSystemSelfAudit } from '../api/diagnostics'

export default function DiagnosticsPage() {
  const [history, setHistory] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [health, setHealth] = useState(null)
  const [releaseReadiness, setReleaseReadiness] = useState(null)
  const [busy, setBusy] = useState(false)
  const [exportBusy, setExportBusy] = useState(false)
  const [jsonExportBusy, setJsonExportBusy] = useState(false)
  const [auditEvents, setAuditEvents] = useState([])
  const [activityStream, setActivityStream] = useState([])
  const [taskStream, setTaskStream] = useState([])
  const [approvalStream, setApprovalStream] = useState([])

  const loadHealth = async () => {
    try {
      const data = await api('/health')
      setHealth(data)
    } catch (_) {}
  }

  const loadAuditEvents = async () => {
    try {
      const data = await api('/audit')
      setAuditEvents(Array.isArray(data?.entries) ? data.entries : [])
    } catch (_) {}
  }

  const loadReleaseReadiness = async () => {
    try {
      const data = await api('/release-readiness')
      setReleaseReadiness(data)
    } catch (_) {}
  }

  const loadStreams = async () => {
    try {
      const [activity, tasks, approvals] = await Promise.all([
        api('/activity'),
        api('/tasks'),
        api('/approvals'),
      ])
      setActivityStream(Array.isArray(activity) ? activity : [])
      setTaskStream(Array.isArray(tasks) ? tasks : [])
      setApprovalStream(Array.isArray(approvals) ? approvals : [])
    } catch (_) {}
  }

  useEffect(() => {
    const stored = loadSelfAuditHistory()
    setHistory(stored)
    setSelectedId(stored[0]?.id || null)
    loadHealth()
    loadReleaseReadiness()
    loadAuditEvents()
    loadStreams()
  }, [])

  const runAudit = async () => {
    setBusy(true)
    try {
      const { result, history: nextHistory } = await runSystemSelfAudit()
      setHistory(nextHistory)
      setSelectedId(result.id)
      setHealth(prev => prev || null)
      await loadHealth()
      await loadReleaseReadiness()
      await loadAuditEvents()
      await loadStreams()
    } finally {
      setBusy(false)
    }
  }

  const clearHistory = () => {
    clearSelfAuditHistory()
    setHistory([])
    setSelectedId(null)
  }

  const exportAuditCsv = async () => {
    setExportBusy(true)
    try {
      const response = await authorizedFetch('/audit/export')
      if (!response.ok) {
        throw new Error('Export request failed')
      }
      const blob = await response.blob()
      const href = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = href
      link.download = `mammoth-audit-${new Date().toISOString().replace(/[:.]/g, '-')}.csv`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(href)
    } finally {
      setExportBusy(false)
    }
  }

  const exportDiagnosticsJson = async () => {
    setJsonExportBusy(true)
    try {
      const response = await authorizedFetch('/diagnostics/export')
      if (!response.ok) {
        throw new Error('Diagnostics export request failed')
      }
      const blob = await response.blob()
      const href = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = href
      link.download = `mammoth-diagnostics-${new Date().toISOString().replace(/[:.]/g, '-')}.json`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(href)
    } finally {
      setJsonExportBusy(false)
    }
  }

  const selectedAudit = history.find(item => item.id === selectedId) || history[0] || null
  const services = Array.isArray(health?.services) ? health.services : []
  const selectedChecks = Array.isArray(selectedAudit?.checks) ? selectedAudit.checks : []
  const selectedRecommendations = Array.isArray(selectedAudit?.recommendations) ? selectedAudit.recommendations : []
  const selectedObservability = selectedAudit?.observability || null

  return (
    <div className="page-enter" style={{ padding: '28px 24px 80px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
        <div>
          <h1 style={{ fontSize: '1.3rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <Activity size={20} color="var(--cyan)" /> Diagnostics
          </h1>
          <p style={{ fontSize: '0.84rem', color: 'var(--txt-sec)', maxWidth: 720, lineHeight: 1.6 }}>
            MammothOS can now self-evaluate. This page keeps a history of shell audits, ATLAS eval health, model routing visibility, and current platform diagnostics.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button
            onClick={runAudit}
            disabled={busy}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 14px', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', fontWeight: 700, cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.7 : 1 }}
          >
            <RefreshCw size={14} style={{ animation: busy ? 'spin 1s linear infinite' : 'none' }} />
            {busy ? 'Running audit…' : 'Run audit now'}
          </button>
          <button
            onClick={clearHistory}
            disabled={history.length === 0}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: history.length === 0 ? 'not-allowed' : 'pointer', opacity: history.length === 0 ? 0.5 : 1 }}
          >
            <Trash2 size={14} /> Clear history
          </button>
          <button
            onClick={exportAuditCsv}
            disabled={exportBusy || auditEvents.length === 0}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 14px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.35)', background: 'rgba(77,166,255,0.08)', color: 'var(--cyan)', cursor: exportBusy || auditEvents.length === 0 ? 'not-allowed' : 'pointer', opacity: exportBusy || auditEvents.length === 0 ? 0.6 : 1 }}
          >
            <Download size={14} /> {exportBusy ? 'Exporting…' : 'Export CSV'}
          </button>
          <button
            onClick={exportDiagnosticsJson}
            disabled={jsonExportBusy}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '9px 14px', borderRadius: 8, border: '1px solid rgba(0,245,212,0.28)', background: 'rgba(0,245,212,0.08)', color: 'var(--photon)', cursor: jsonExportBusy ? 'not-allowed' : 'pointer', opacity: jsonExportBusy ? 0.6 : 1 }}
          >
            <Download size={14} /> {jsonExportBusy ? 'Bundling snapshot…' : 'Export JSON snapshot'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px minmax(0, 1fr)', gap: 16, alignItems: 'start' }}>
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Audit history
            </span>
            <span style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>{history.length} run{history.length === 1 ? '' : 's'}</span>
          </div>
          <div style={{ display: 'grid', gap: 8 }}>
            {history.length > 0 ? history.map(item => {
              const active = item.id === selectedId
              return (
                <button
                  key={item.id}
                  onClick={() => setSelectedId(item.id)}
                  style={{
                    textAlign: 'left',
                    padding: '12px 12px',
                    borderRadius: 10,
                    border: `1px solid ${active ? 'rgba(77,166,255,0.35)' : 'var(--border)'}`,
                    background: active ? 'rgba(77,166,255,0.08)' : 'rgba(255,255,255,0.03)',
                    cursor: 'pointer',
                    color: 'var(--txt-pri)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 5 }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: 700 }}>Audit {item.score}</span>
                    <span style={{ fontSize: '0.68rem', color: 'var(--cyan)', textTransform: 'capitalize' }}>{item.tier}</span>
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', marginBottom: 4 }}>{item.generatedAt}</div>
                  <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)' }}>{item.checks?.filter(check => check.passed).length || 0}/{item.checks?.length || 0} checks passing</div>
                </button>
              )
            }) : (
              <div style={{ padding: '10px 4px', fontSize: '0.8rem', color: 'var(--txt-mut)' }}>
                No audit history yet. Run the first self-audit to seed diagnostics memory.
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'grid', gap: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12 }}>
            <div className="glass-card-solid" style={{ padding: 16 }}>
              <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>Current shell health</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>
                {services.filter(service => service.status === 'green').length}/{services.length || 0}
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)' }}>healthy services</div>
            </div>
            <div className="glass-card-solid" style={{ padding: 16 }}>
              <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>Latest audit score</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>
                {selectedAudit?.score || '–'}
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)' }}>last recorded self-evaluation</div>
            </div>
            <div className="glass-card-solid" style={{ padding: 16 }}>
              <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>Observed tier</div>
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--cyan)', textTransform: 'capitalize' }}>
                {selectedAudit?.tier || 'explorer'}
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)' }}>entitlement snapshot</div>
            </div>
            <div className="glass-card-solid" style={{ padding: 16 }}>
              <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>Release readiness</div>
              <div style={{ fontSize: '1.3rem', fontWeight: 800, fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>
                {releaseReadiness?.score || '–'}
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)', textTransform: 'capitalize' }}>{releaseReadiness?.tier || 'snapshot pending'}</div>
            </div>
          </div>

          {releaseReadiness && (
            <div className="glass-card-solid" style={{ padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 12, flexWrap: 'wrap' }}>
                <div>
                  <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Release-readiness scorecard</div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--txt-mut)' }}>
                    Runtime {releaseReadiness.scores?.runtime || '–'} • Modules {releaseReadiness.scores?.modules || '–'} • Observability {releaseReadiness.scores?.observability || '–'}
                  </div>
                </div>
                <div style={{ fontSize: '0.74rem', color: 'var(--cyan)' }}>
                  {releaseReadiness.summary?.cloud_providers_ready || 0} cloud provider{releaseReadiness.summary?.cloud_providers_ready === 1 ? '' : 's'} ready
                </div>
              </div>
              <div style={{ padding: '12px 14px', borderRadius: 12, border: '1px solid rgba(77,166,255,0.24)', background: 'rgba(77,166,255,0.06)', marginBottom: 12 }}>
                <div style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>Recommended next action</div>
                <div style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', lineHeight: 1.6 }}>
                  {releaseReadiness.recommended_next_action || releaseReadiness['recommendedNextAction'] || 'Continue incremental upgrade work on the next lowest-rated lane.'}
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 12 }}>
                <div style={{ display: 'grid', gap: 8 }}>
                  <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>Top blockers</div>
                  {(releaseReadiness.blockers || []).map((blocker) => (
                    <div key={blocker.title} style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(248,113,113,0.22)', background: 'rgba(248,113,113,0.06)' }}>
                      <div style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', fontWeight: 700, marginBottom: 4 }}>{blocker.title}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{blocker.detail}</div>
                    </div>
                  ))}
                </div>
                <div style={{ display: 'grid', gap: 8 }}>
                  <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>Lowest-rated lanes</div>
                  {(releaseReadiness.lowest_rated || []).slice(0, 4).map((item) => (
                    <div key={item.id} style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
                        <div style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', fontWeight: 700 }}>{item.name}</div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace' }}>{item.score_10}/10</div>
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{item.finding || 'No finding recorded yet.'}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 12 }}>
            <div className="glass-card-solid" style={{ padding: 16 }}>
              <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 8 }}>Recent activity</div>
              <div style={{ display: 'grid', gap: 8 }}>
                {activityStream.length > 0 ? activityStream.slice(0, 5).map(item => (
                  <div key={item.id} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                    <div style={{ fontSize: '0.76rem', color: 'var(--txt-pri)', marginBottom: 4 }}>{item.message}</div>
                    <div style={{ fontSize: '0.66rem', color: 'var(--txt-mut)' }}>{item.kind} • {item.agent_id || 'system'} • {item.created_at ? new Date(item.created_at).toLocaleString() : 'unknown'}</div>
                  </div>
                )) : <div style={{ fontSize: '0.78rem', color: 'var(--txt-mut)' }}>No recent activity yet.</div>}
              </div>
            </div>

            <div className="glass-card-solid" style={{ padding: 16 }}>
              <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 8 }}>Task stream</div>
              <div style={{ display: 'grid', gap: 8 }}>
                {taskStream.length > 0 ? taskStream.slice(0, 5).map(task => (
                  <div key={task.id} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                    <div style={{ fontSize: '0.76rem', color: 'var(--txt-pri)', marginBottom: 4 }}>{task.title}</div>
                    <div style={{ fontSize: '0.66rem', color: 'var(--txt-mut)' }}>{task.status} • {task.agent_id || 'unassigned'}</div>
                  </div>
                )) : <div style={{ fontSize: '0.78rem', color: 'var(--txt-mut)' }}>No tasks recorded yet.</div>}
              </div>
            </div>

            <div className="glass-card-solid" style={{ padding: 16 }}>
              <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 8 }}>Approval queue</div>
              <div style={{ display: 'grid', gap: 8 }}>
                {approvalStream.length > 0 ? approvalStream.slice(0, 5).map(item => (
                  <div key={item.id} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                    <div style={{ fontSize: '0.76rem', color: 'var(--txt-pri)', marginBottom: 4 }}>{item.operation} • {item.target}</div>
                    <div style={{ fontSize: '0.66rem', color: 'var(--txt-mut)' }}>{item.status} • {item.agent_id || 'system'} • {item.created_at ? new Date(item.created_at).toLocaleString() : 'unknown'}</div>
                  </div>
                )) : <div style={{ fontSize: '0.78rem', color: 'var(--txt-mut)' }}>No approvals waiting.</div>}
              </div>
            </div>
          </div>

          <div className="glass-card-solid" style={{ padding: 18 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <ShieldCheck size={16} color="var(--cyan)" />
              <span style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--txt-pri)' }}>
                Audit detail
              </span>
            </div>
            {selectedAudit ? (
              <div style={{ display: 'grid', gap: 14 }}>
                <div style={{ fontSize: '0.76rem', color: 'var(--txt-mut)' }}>Generated {selectedAudit.generatedAt}</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 12 }}>
                  {selectedChecks.map(check => (
                    <div
                      key={check.label}
                      style={{
                        padding: '12px 14px',
                        borderRadius: 10,
                        border: `1px solid ${check.passed ? 'rgba(34,197,94,0.25)' : 'rgba(248,113,113,0.25)'}`,
                        background: check.passed ? 'rgba(34,197,94,0.06)' : 'rgba(248,113,113,0.06)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
                        <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{check.label}</span>
                        <span style={{ fontSize: '0.68rem', fontWeight: 700, color: check.passed ? '#22c55e' : '#f87171' }}>
                          {check.passed ? 'PASS' : 'ATTN'}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{check.detail}</div>
                    </div>
                  ))}
                </div>
                {selectedObservability ? (
                  <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid rgba(77,166,255,0.2)', background: 'rgba(77,166,255,0.05)' }}>
                    <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--txt-pri)', marginBottom: 6 }}>ATLAS observability</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>
                      Learner pass rate {selectedObservability.learner_pass_rate || 0}% • Eval pass rate {selectedObservability.eval_pass_rate || 0}% • Plan runs {selectedObservability.plan_runs || 0} • Eval runs {selectedObservability.eval_runs || 0} • Guard rate {selectedObservability.fab_guard_rate || 0}%
                    </div>
                  </div>
                ) : null}
                <div>
                  <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 8 }}>
                    Suggested next upgrades
                  </div>
                  <div style={{ display: 'grid', gap: 8 }}>
                    {selectedRecommendations.map(item => (
                      <div key={item} style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', fontSize: '0.8rem', color: 'var(--txt-sec)' }}>
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
                <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid rgba(77,166,255,0.2)', background: 'rgba(77,166,255,0.05)' }}>
                  <div style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--txt-pri)', marginBottom: 8 }}>Backend audit stream</div>
                  {auditEvents.length > 0 ? (
                    <div style={{ display: 'grid', gap: 8 }}>
                      {auditEvents.slice(0, 6).map(entry => (
                        <div key={entry.id} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                          <div style={{ fontSize: '0.74rem', color: 'var(--txt-pri)', marginBottom: 4 }}>{entry.message}</div>
                          <div style={{ fontSize: '0.68rem', color: 'var(--txt-sec)' }}>{entry.kind} • {entry.tier || 'explorer'} • {entry.created_at ? new Date(entry.created_at).toLocaleString() : 'unknown'}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)' }}>No backend audit entries yet.</div>
                  )}
                </div>
              </div>
            ) : (
              <div style={{ fontSize: '0.82rem', color: 'var(--txt-mut)' }}>
                Run an audit to populate this panel.
              </div>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 16 }}>
            <div className="glass-card-solid" style={{ padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <HeartPulse size={16} color="var(--cyan)" />
                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Live services</span>
              </div>
              <div style={{ display: 'grid', gap: 8 }}>
                {services.length > 0 ? services.map(service => (
                  <div key={service.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '8px 0', borderTop: '1px solid var(--border)' }}>
                    <div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--txt-pri)' }}>{service.label}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>{service.detail}</div>
                    </div>
                    <span style={{ fontSize: '0.68rem', fontWeight: 700, color: service.status === 'green' ? '#22c55e' : service.status === 'yellow' ? '#eab308' : '#f87171' }}>
                      {service.status?.toUpperCase()}
                    </span>
                  </div>
                )) : (
                  <div style={{ fontSize: '0.8rem', color: 'var(--txt-mut)' }}>Waiting on backend health snapshot…</div>
                )}
              </div>
            </div>

            <div className="glass-card-solid" style={{ padding: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <Cpu size={16} color="var(--photon)" />
                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Model + CLI snapshot</span>
              </div>
              {selectedAudit ? (
                <div style={{ display: 'grid', gap: 10 }}>
                  <div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Active model</div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--txt-sec)' }}>{selectedAudit.models?.active_model || 'No model reported'}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>CLI command count</div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--txt-sec)' }}>{selectedAudit.commandCount}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Latest ATLAS activity</div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>
                      {selectedAudit.latestActivity?.event || 'No recent activity captured'}
                    </div>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: '0.8rem', color: 'var(--txt-mut)' }}>No audit snapshot selected.</div>
              )}
            </div>
          </div>
        </div>
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
