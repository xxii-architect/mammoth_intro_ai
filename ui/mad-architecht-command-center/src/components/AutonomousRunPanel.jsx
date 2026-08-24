import React from 'react'

function formatLane(run) {
  const lane = run?.current_lane || {}
  if (!lane) return 'Idle'
  if (lane.status === 'pending_approval') return `${lane.title || lane.agent_id || 'Approval'} waiting for approval`
  if (lane.status === 'failed') return `${lane.title || lane.agent_id || 'Step'} failed`
  if (lane.status === 'completed') return `${lane.title || lane.agent_id || 'Step'} completed`
  return lane.title || lane.agent_id || 'Idle'
}

export default function AutonomousRunPanel({ summary, runs, onReplayRun }) {
  const list = Array.isArray(runs) ? runs : []
  const latest = list[0] || null
  const counts = summary || {}

  return (
    <div className="glass-card-solid" style={{ padding: 12, marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', margin: 0 }}>
          Autonomous Runs
        </p>
        <span style={{ fontSize: '0.66rem', color: 'var(--txt-mut)' }}>
          {counts.total_runs || 0} total • {counts.pending_approval || 0} pending • {counts.failed || 0} failed
        </span>
      </div>

      {latest ? (
        <div style={{ padding: '10px 0', borderTop: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
            <span style={{ color: 'var(--txt-pri)', fontSize: '0.76rem', fontWeight: 600 }}>
              Latest run
            </span>
            <span style={{
              fontSize: '0.64rem',
              textTransform: 'uppercase',
              color: latest.plan_status === 'completed' ? '#22c55e' : latest.plan_status === 'pending_approval' ? '#f59e0b' : latest.plan_status === 'failed' ? '#f87171' : 'var(--photon)',
              fontFamily: 'JetBrains Mono,monospace',
            }}>
              {latest.plan_status || 'unknown'}
            </span>
          </div>
          <div style={{ color: 'var(--txt-sec)', fontSize: '0.68rem', marginTop: 4 }}>
            {latest.objective || 'No objective recorded'}
          </div>
          <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4 }}>
            Lane: {formatLane(latest)} • Approvals: {latest.approvals_needed_count || 0}
          </div>
          <div style={{ color: 'var(--txt-mut)', fontSize: '0.64rem', marginTop: 4, fontFamily: 'JetBrains Mono,monospace' }}>
            {latest.run_id || 'run n/a'}{latest.created_at ? ` • ${new Date(latest.created_at).toLocaleString()}` : ''}
          </div>
          <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4, fontFamily: 'JetBrains Mono,monospace' }}>
            Replay: {(latest.replay?.execution_mode || 'plan')} / {(latest.replay?.plan_profile || 'balanced')} / {(latest.replay?.coding_intent || 'summarize')}
          </div>
        </div>
      ) : (
        <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem', padding: '8px 0' }}>No autonomous run data yet.</div>
      )}

      {!!list.length && (
        <div style={{ marginTop: 4 }}>
          {list.slice(0, 4).map(run => (
            <div key={`${run.run_id}-${run.source}`} style={{ padding: '10px 0', borderTop: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                <span style={{ color: 'var(--txt-pri)', fontSize: '0.72rem' }}>
                  {(run.objective || 'Autonomous run').slice(0, 40)}
                </span>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{
                    fontSize: '0.64rem',
                    textTransform: 'uppercase',
                    color: run.plan_status === 'completed' ? '#22c55e' : run.plan_status === 'pending_approval' ? '#f59e0b' : run.plan_status === 'failed' ? '#f87171' : 'var(--photon)',
                    fontFamily: 'JetBrains Mono,monospace',
                  }}>
                    {run.plan_status || 'unknown'}
                  </span>
                  <button
                    onClick={() => onReplayRun?.(run)}
                    style={{ background: 'var(--photon)', color: '#050608', border: 'none', borderRadius: 6, padding: '4px 8px', fontSize: '0.68rem', cursor: 'pointer', fontWeight: 700 }}
                  >
                    Replay
                  </button>
                </div>
              </div>
              <div style={{ color: 'var(--txt-sec)', fontSize: '0.66rem', marginTop: 4 }}>
                {run.source} • {run.plan_profile || 'balanced'} • {run.progress?.completed || 0}/{run.progress?.total || 0}
              </div>
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.64rem', marginTop: 4, fontFamily: 'JetBrains Mono,monospace' }}>
                {run.run_id || 'run n/a'}{run.updated_at ? ` • ${new Date(run.updated_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : ''}
              </div>
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4 }}>
                {formatLane(run)} • {run.approvals_needed_count || 0} approvals needed
              </div>
              {Array.isArray(run.approvals_needed) && run.approvals_needed.length > 0 && (
                <div style={{ color: 'var(--txt-mut)', fontSize: '0.64rem', marginTop: 4 }}>
                  {run.approvals_needed.slice(0, 2).map(approval => approval.title || approval.operation || approval.step_id).filter(Boolean).join(' • ')}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
