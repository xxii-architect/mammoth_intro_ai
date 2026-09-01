import { useState } from 'react'
import { CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronRight, Eye, EyeOff, Cpu } from 'lucide-react'
import MammothEmpty from './MammothEmpty'

const STATUS_CONFIG = {
  ok:               { color: '#22c55e', bg: 'rgba(34,197,94,0.08)',   icon: CheckCircle,   label: 'Success' },
  success:          { color: '#22c55e', bg: 'rgba(34,197,94,0.08)',   icon: CheckCircle,   label: 'Success' },
  error:            { color: '#f87171', bg: 'rgba(248,113,113,0.08)', icon: XCircle,       label: 'Error' },
  needs_context:    { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)',  icon: AlertTriangle, label: 'Needs Context' },
  degraded:         { color: '#f59e0b', bg: 'rgba(245,158,11,0.08)',  icon: AlertTriangle, label: 'Degraded' },
}

function statusCfg(status) {
  return STATUS_CONFIG[status] || { color: '#94a3b8', bg: 'rgba(148,163,184,0.06)', icon: Cpu, label: status || 'Done' }
}

/**
 * Renders any agent response in a structured, readable way.
 * Falls back gracefully for unknown shapes.
 */
function renderValue(val, depth = 0) {
  if (val === null || val === undefined) return <span style={{ color: 'var(--txt-mut)', fontStyle: 'italic' }}>none</span>
  if (typeof val === 'boolean') return <span style={{ color: val ? '#22c55e' : '#f87171', fontFamily: 'JetBrains Mono,monospace' }}>{String(val)}</span>
  if (typeof val === 'number') return <span style={{ color: '#22d3ee', fontFamily: 'JetBrains Mono,monospace' }}>{val}</span>
  if (typeof val === 'string') {
    if (val.length > 400) {
      return <ReadMoreText text={val} />
    }
    return <span style={{ color: 'var(--txt-sec)' }}>{val}</span>
  }
  if (Array.isArray(val)) {
    if (!val.length) return <span style={{ color: 'var(--txt-mut)', fontStyle: 'italic' }}>empty list</span>
    return (
      <div style={{ paddingLeft: depth > 0 ? 12 : 0 }}>
        {val.slice(0, 20).map((item, i) => (
          <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 3 }}>
            <span style={{ color: 'var(--txt-mut)', fontSize: '0.68rem', minWidth: 18, fontFamily: 'JetBrains Mono,monospace' }}>{i + 1}.</span>
            <div>{renderValue(item, depth + 1)}</div>
          </div>
        ))}
        {val.length > 20 && <div style={{ color: 'var(--txt-mut)', fontSize: '0.72rem' }}>…and {val.length - 20} more</div>}
      </div>
    )
  }
  if (typeof val === 'object') {
    const entries = Object.entries(val)
    if (!entries.length) return <span style={{ color: 'var(--txt-mut)', fontStyle: 'italic' }}>{ '{}' }</span>
    return (
      <div style={{ paddingLeft: depth > 0 ? 12 : 0 }}>
        {entries.slice(0, 30).map(([k, v]) => (
          <div key={k} style={{ display: 'flex', gap: 8, marginBottom: 4, alignItems: 'flex-start' }}>
            <span style={{ color: 'var(--txt-mut)', fontSize: '0.72rem', minWidth: 80, flexShrink: 0, fontFamily: 'JetBrains Mono,monospace', paddingTop: 2 }}>
              {k.replace(/_/g, ' ')}
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>{renderValue(v, depth + 1)}</div>
          </div>
        ))}
      </div>
    )
  }
  return <span style={{ color: 'var(--txt-sec)' }}>{String(val)}</span>
}

function ReadMoreText({ text }) {
  const [expanded, setExpanded] = useState(false)
  const display = expanded ? text : text.slice(0, 400)
  return (
    <span>
      <span style={{ color: 'var(--txt-sec)', lineHeight: 1.65 }}>{display}</span>
      {text.length > 400 && (
        <>
          {!expanded && '…'}
          <button
            onClick={() => setExpanded(e => !e)}
            style={{ fontSize: '0.7rem', color: 'var(--photon)', background: 'none', border: 'none', cursor: 'pointer', padding: '0 4px' }}
          >
            {expanded ? 'show less' : 'show more'}
          </button>
        </>
      )}
    </span>
  )
}

// Keys that are surfaced prominently; skip for the detail section
const PROMINENT_KEYS = new Set(['status', 'agent', 'summary', 'quality_flags'])

// Keys that are skipped in detail (noisy internal/metadata)
const SKIP_KEYS = new Set(['status', 'agent', 'quality_flags', 'thought_steps', 'trace_id', 'task_id'])

function QualityFlags({ flags }) {
  if (!Array.isArray(flags) || !flags.length) return null
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 10 }}>
      {flags.map(f => (
        <span key={f} style={{ fontSize: '0.63rem', background: 'rgba(77,166,255,0.12)', color: 'var(--photon)', borderRadius: 10, padding: '2px 8px' }}>
          {f.replace(/_/g, ' ')}
        </span>
      ))}
    </div>
  )
}

function DetailSection({ result }) {
  const [open, setOpen] = useState(false)
  const entries = Object.entries(result).filter(([k]) => !SKIP_KEYS.has(k) && !PROMINENT_KEYS.has(k))
  if (!entries.length) return null

  return (
    <div style={{ marginTop: 12 }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 6,
          fontSize: '0.7rem', color: 'var(--txt-mut)',
          background: 'none', border: 'none', cursor: 'pointer', padding: 0,
        }}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        {open ? 'Hide details' : `Show ${entries.length} field${entries.length > 1 ? 's' : ''}`}
      </button>
      {open && (
        <div style={{
          marginTop: 10, padding: '10px 14px',
          background: 'rgba(255,255,255,0.03)',
          border: '1px solid var(--border)', borderRadius: 8,
        }}>
          {entries.map(([k, v]) => (
            <div key={k} style={{ display: 'flex', gap: 10, marginBottom: 8, alignItems: 'flex-start' }}>
              <span style={{
                color: 'var(--txt-mut)', fontSize: '0.69rem',
                fontFamily: 'JetBrains Mono,monospace',
                minWidth: 100, flexShrink: 0, paddingTop: 2,
              }}>
                {k.replace(/_/g, '_')}
              </span>
              <div style={{ flex: 1, minWidth: 0, fontSize: '0.78rem' }}>
                {renderValue(v)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AgentResultPanel({ result, rawJson, agentId }) {
  const [showRaw, setShowRaw] = useState(false)

  if (!result || typeof result !== 'object') {
    if (rawJson) {
      return (
        <pre style={{ fontSize: '0.8rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
          {rawJson}
        </pre>
      )
    }
    return null
  }

  const sc = statusCfg(result.status)
  const StatusIcon = sc.icon
  const agentLabel = (result.agent || agentId || '').replace(/_agent$/, '').replace(/_/g, ' ')
  const summary = result.summary

  return (
    <div>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusIcon size={15} color={sc.color} />
          {agentLabel && (
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--txt-pri)', textTransform: 'capitalize' }}>
              {agentLabel}
            </span>
          )}
          <span style={{
            fontSize: '0.64rem', textTransform: 'uppercase',
            background: sc.bg, color: sc.color, borderRadius: 12,
            padding: '2px 9px', fontFamily: 'JetBrains Mono,monospace',
          }}>
            {sc.label}
          </span>
        </div>
        <button
          onClick={() => setShowRaw(r => !r)}
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            fontSize: '0.7rem', color: 'var(--txt-mut)',
            background: 'none', border: '1px solid var(--border)',
            borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
          }}
        >
          {showRaw ? <Eye size={11} /> : <EyeOff size={11} />}
          {showRaw ? 'Human view' : 'Raw JSON'}
        </button>
      </div>

      {showRaw ? (
        <pre style={{ fontSize: '0.76rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', whiteSpace: 'pre-wrap', lineHeight: 1.6, maxHeight: 360, overflowY: 'auto' }}>
          {rawJson || JSON.stringify(result, null, 2)}
        </pre>
      ) : (
        <>
          {/* Summary */}
          {summary ? (
            <div style={{
              background: sc.bg,
              border: `1px solid ${sc.color}22`,
              borderRadius: 8, padding: '10px 14px', marginBottom: 12,
            }}>
              <p style={{ fontSize: '0.85rem', color: 'var(--txt-pri)', lineHeight: 1.65, margin: 0 }}>
                {summary}
              </p>
            </div>
          ) : (
            <MammothEmpty context="agent_silent" />
          )}

          {/* Quality flags */}
          <QualityFlags flags={result.quality_flags} />

          {/* Details collapsible */}
          <DetailSection result={result} />
        </>
      )}
    </div>
  )
}
