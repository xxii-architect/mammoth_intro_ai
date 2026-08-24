import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, WifiOff } from 'lucide-react'
import { api } from '../api/client'

const RUNTIME_STATUS_STORAGE_KEY = 'mammoth-runtime-status-expanded'

function statusTone(state) {
  if (state === 'ready') return '#22c55e'
  if (state === 'degraded') return '#f59e0b'
  return '#f87171'
}

export default function RuntimeStatusBanner({ title = 'Runtime status', compact = false }) {
  const [runtime, setRuntime] = useState(null)
  const [expanded, setExpanded] = useState(() => {
    if (typeof window === 'undefined') return false
    try {
      return window.localStorage.getItem(RUNTIME_STATUS_STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(RUNTIME_STATUS_STORAGE_KEY, String(expanded))
    } catch {
      // Ignore restricted browser storage errors.
    }
  }, [expanded])

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const data = await api('/runtime/status')
        if (alive) setRuntime(data)
      } catch {
        if (alive) setRuntime({ state: 'blocked', recommendation: 'Runtime status is unavailable.' })
      }
    }
    load()
    const timer = setInterval(load, 30000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [])

  const state = runtime?.state || 'blocked'
  const tone = statusTone(state)
  const providers = Array.isArray(runtime?.providers) ? runtime.providers : []
  const activeProvider = runtime?.active_provider || runtime?.used_provider || runtime?.effective_adapter || runtime?.active_adapter || 'auto'
  const issueText = runtime?.issue || runtime?.recommendation || 'Checking provider health…'
  const nextActionText = runtime?.next_action || runtime?.recommendation || 'Checking provider health…'
  const fallbackChain = Array.isArray(runtime?.fallback_chain) ? runtime.fallback_chain.join(' -> ') : ''
  const fallbackReason = runtime?.fallback_reason ? String(runtime.fallback_reason).replaceAll('_', ' ') : ''
  const statusLabel = state === 'ready' ? 'Healthy' : state === 'degraded' ? 'Degraded' : 'Blocked'

  return (
    <div className="glass-card-solid" style={{ padding: compact ? 12 : 14, borderLeft: `2px solid ${tone}`, marginBottom: compact ? 12 : 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          {state === 'ready' ? <CheckCircle2 size={16} color={tone} /> : state === 'degraded' ? <AlertTriangle size={16} color={tone} /> : <WifiOff size={16} color={tone} />}
          <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{title}</span>
          <span style={{ fontSize: '0.68rem', color: tone, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 700 }}>
            {statusLabel}
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {activeProvider} • {runtime?.active_model || 'unknown'}
          </span>
        </div>
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: '1px solid var(--border)', borderRadius: 999, background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', padding: '4px 10px', fontSize: '0.68rem', cursor: 'pointer' }}
        >
          {expanded ? 'Hide runtime' : 'Show runtime'}
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {expanded && (
        <>
          <div style={{ marginTop: 8 }}>
            <p style={{ margin: 0, color: 'var(--txt-sec)', fontSize: '0.78rem', lineHeight: 1.6 }}>
              {issueText}
            </p>
            {nextActionText && nextActionText !== issueText && (
              <p style={{ margin: '4px 0 0', color: 'var(--txt-mut)', fontSize: '0.72rem', lineHeight: 1.5 }}>
                Next action: {nextActionText}
              </p>
            )}
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginTop: 8, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
            <span>
              Active provider: <span style={{ color: 'var(--txt-pri)', fontWeight: 600 }}>{activeProvider}</span>
            </span>
            {runtime?.fallback_used && (
              <span>
                Fallback active{fallbackReason ? ` • ${fallbackReason}` : ''}
              </span>
            )}
            {fallbackChain && <span>Chain: {fallbackChain}</span>}
          </div>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
            {providers.map((provider) => {
              const providerTone = provider.status === 'ready' ? '#22c55e' : provider.status === 'offline' ? '#f87171' : '#f59e0b'
              return (
                <div
                  key={provider.provider}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '5px 8px',
                    borderRadius: 999,
                    border: '1px solid var(--border)',
                    background: 'rgba(255,255,255,0.03)',
                    fontSize: '0.7rem',
                    color: provider.active ? 'var(--txt-pri)' : 'var(--txt-sec)',
                    boxShadow: provider.active ? 'inset 0 0 0 1px rgba(77,166,255,0.25)' : 'none',
                  }}
                >
                  <Activity size={12} color={providerTone} />
                  <span>{provider.provider}</span>
                  {provider.active && <span style={{ color: 'var(--photon)', fontWeight: 700 }}>active</span>}
                  {provider.fallback_target && <span style={{ color: '#f59e0b', fontWeight: 700 }}>fallback</span>}
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
