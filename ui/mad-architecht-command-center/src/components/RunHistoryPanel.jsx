import React from 'react'
import { Clock, RotateCcw, CheckCircle2, XCircle, Loader2 } from 'lucide-react'

function StatusDot({ status }) {
  const tone = status === 'ok' || status === 'pass' || status === 'completed'
    ? '#22c55e'
    : status === 'error' || status === 'fail' || status === 'failed'
      ? '#f87171'
      : 'var(--photon)'
  return (
    <span style={{ width: 7, height: 7, borderRadius: '50%', background: tone, boxShadow: `0 0 6px ${tone}`, flexShrink: 0, display: 'inline-block', marginTop: 2 }} />
  )
}

export default function RunHistoryPanel({ entries, onReplay, onClear }) {
  const list = Array.isArray(entries) ? entries : []

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <Clock size={13} color="var(--txt-mut)" />
          <span style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
            Run History
          </span>
          <span style={{ fontSize: '0.62rem', color: 'var(--txt-mut)', background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', borderRadius: 999, padding: '2px 7px' }}>
            {list.length}
          </span>
        </div>
        {list.length > 0 && (
          <button
            type="button"
            onClick={onClear}
            style={{ background: 'none', color: 'var(--txt-mut)', border: 'none', fontSize: '0.66rem', cursor: 'pointer', padding: '3px 6px' }}
          >
            Clear
          </button>
        )}
      </div>

      {list.length === 0 ? (
        <div style={{ color: 'var(--txt-mut)', fontSize: '0.73rem', padding: '10px 0' }}>No runs yet.</div>
      ) : (
        <div style={{ display: 'grid', gap: 7 }}>
          {list.slice().reverse().map((entry) => (
            <div
              key={entry.id}
              style={{
                padding: '10px 12px',
                borderRadius: 10,
                border: '1px solid var(--border)',
                background: 'rgba(255,255,255,0.025)',
                display: 'grid',
                gap: 5,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 7, minWidth: 0 }}>
                  <StatusDot status={entry.status} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: '0.76rem', color: 'var(--txt-pri)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {entry.agent_id || 'agent'}
                    </div>
                    <div style={{ fontSize: '0.66rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', marginTop: 1 }}>
                      {entry.intent || 'run'}{entry.execution_mode === 'plan' ? ' • plan' : ''}
                    </div>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => onReplay(entry)}
                  title="Replay this run"
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    padding: '4px 8px', borderRadius: 7,
                    border: '1px solid var(--border)',
                    background: 'rgba(77,166,255,0.08)',
                    color: 'var(--photon)',
                    fontSize: '0.66rem', cursor: 'pointer', flexShrink: 0,
                  }}
                >
                  <RotateCcw size={11} /> Replay
                </button>
              </div>

              {entry.prompt && (
                <div style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', lineHeight: 1.5, overflowWrap: 'anywhere' }}>
                  {entry.prompt.slice(0, 90)}{entry.prompt.length > 90 ? '…' : ''}
                </div>
              )}

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                <span style={{ fontSize: '0.62rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
                  {entry.created_at ? new Date(entry.created_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : ''}
                </span>
                {entry.task_id && (
                  <span style={{ fontSize: '0.6rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 120 }}>
                    {entry.task_id}
                  </span>
                )}
                {entry.runtime_adapter && (
                  <span style={{ fontSize: '0.62rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
                    {entry.runtime_adapter}{entry.runtime_model ? `/${entry.runtime_model}` : ''}
                  </span>
                )}
              </div>

              {entry.coding_artifact?.summary && (
                <div style={{ fontSize: '0.68rem', color: 'var(--txt-sec)', lineHeight: 1.4, borderTop: '1px dashed rgba(255,255,255,0.06)', paddingTop: 5 }}>
                  {entry.coding_artifact.summary}
                  {entry.coding_artifact.applied && (
                    <span style={{ marginLeft: 8, color: '#22c55e', fontFamily: 'JetBrains Mono,monospace' }}>✓ applied</span>
                  )}
                </div>
              )}
              {entry.research_artifact?.summary && (
                <div style={{ fontSize: '0.68rem', color: 'var(--txt-sec)', lineHeight: 1.4, borderTop: '1px dashed rgba(255,255,255,0.06)', paddingTop: 5 }}>
                  research: {entry.research_artifact.summary}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}