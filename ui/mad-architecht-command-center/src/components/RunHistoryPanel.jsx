import React from 'react'

export default function RunHistoryPanel({ entries, onReplay, onClear }) {
  const list = Array.isArray(entries) ? entries : []

  return (
    <div className="glass-card-solid" style={{ padding: 12, marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)' }}>
          Run History
        </p>
        <button
          onClick={onClear}
          style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--txt-pri)', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 8px', fontSize: '0.68rem', cursor: 'pointer' }}
        >
          Clear
        </button>
      </div>

      {list.length ? (
        list.slice().reverse().map(entry => (
          <div key={entry.id} style={{ padding: '8px 0', borderTop: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
              <span style={{ color: 'var(--txt-pri)', fontSize: '0.74rem' }}>
                {entry.agent_id || 'unknown'} • {entry.intent || 'unknown'}
              </span>
              <button
                onClick={() => onReplay(entry)}
                style={{ background: 'var(--photon)', color: '#050608', border: 'none', borderRadius: 6, padding: '4px 8px', fontSize: '0.68rem', cursor: 'pointer' }}
              >
                Replay
              </button>
            </div>
            <div style={{ color: 'var(--txt-sec)', fontSize: '0.7rem', marginTop: 4 }}>
              {(entry.prompt || '').slice(0, 80) || '(no prompt)'}
            </div>
            <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4 }}>
              {entry.status || 'unknown'} • {entry.created_at ? new Date(entry.created_at).toLocaleTimeString() : ''}
            </div>
            {entry.coding_intent && (
              <div style={{ color: 'var(--photon)', fontSize: '0.64rem', marginTop: 4 }}>
                coding intent: {entry.coding_intent}
              </div>
            )}
            {entry.replay && (
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.64rem', marginTop: 4, fontFamily: 'JetBrains Mono,monospace' }}>
                replay: {entry.replay.execution_mode || 'single'} • {entry.replay.plan_profile || entry.replay.intent || entry.replay.coding_intent || 'n/a'}
              </div>
            )}
          </div>
        ))
      ) : (
        <div style={{ color: 'var(--txt-sec)', fontSize: '0.75rem' }}>No run history yet.</div>
      )}
    </div>
  )
}