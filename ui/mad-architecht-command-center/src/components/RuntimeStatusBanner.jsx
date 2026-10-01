import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, CheckCircle2, ChevronDown, ChevronUp, WifiOff } from 'lucide-react'
import { api } from '../api/client'

const RUNTIME_STATUS_STORAGE_KEY = 'mammoth-runtime-status-expanded'

function statusTone(state) {
  if (state === 'ready') return '#22c55e'
  if (state === 'degraded') return '#f59e0b'
  return '#f87171'
}

export default function RuntimeStatusBanner({ title = 'Runtime status', compact = false, header = false, mobile = false }) {
  const [runtime, setRuntime] = useState(null)
  const [expanded, setExpanded] = useState(() => {
    if (header) return false
    if (typeof window === 'undefined') return false
    try {
      return window.localStorage.getItem(RUNTIME_STATUS_STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })

  useEffect(() => {
    if (header) return
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
  const StatusIcon = state === 'ready' ? CheckCircle2 : state === 'degraded' ? AlertTriangle : WifiOff

  if (header) {
    return (
      <div style={{ position: 'relative', display: 'inline-flex' }}>
        <button
          type="button"
          onClick={() => setExpanded(value => !value)}
          aria-expanded={expanded}
          aria-haspopup="dialog"
          title={`Runtime ${statusLabel.toLowerCase()}${activeProvider ? ` · ${activeProvider}` : ''}`}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 6, height: 30,
            padding: '0 10px', borderRadius: 999,
            border: `1px solid ${tone}66`, background: `${tone}12`,
            color: tone, fontSize: '0.69rem', fontWeight: 700,
            cursor: 'pointer', whiteSpace: 'nowrap',
          }}
        >
          <StatusIcon size={13} />
          {!mobile && <span>Runtime</span>}
          <span style={{ textTransform: 'uppercase', letterSpacing: '0.06em' }}>{statusLabel}</span>
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
        {expanded && (
          <div
            role="dialog"
            aria-label={title}
            style={{
              position: 'fixed', top: 56, right: 12, zIndex: 9001,
              width: 'min(360px, calc(100vw - 24px))', maxHeight: 'min(70vh, 520px)',
              overflowY: 'auto', padding: 14, borderRadius: 14,
              border: `1px solid ${tone}55`, borderTop: `2px solid ${tone}`,
              background: 'var(--card)', backdropFilter: 'blur(20px)',
              boxShadow: '0 12px 44px rgba(0,0,0,0.5)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <StatusIcon size={15} color={tone} />
              <strong style={{ color: 'var(--txt-pri)', fontSize: '0.8rem' }}>{title}</strong>
              <span style={{ color: tone, fontSize: '0.66rem', fontWeight: 700, textTransform: 'uppercase', marginLeft: 'auto' }}>{statusLabel}</span>
            </div>
            <p style={{ margin: 0, color: 'var(--txt-sec)', fontSize: '0.76rem', lineHeight: 1.55 }}>{issueText}</p>
            {nextActionText && nextActionText !== issueText && (
              <p style={{ margin: '5px 0 0', color: 'var(--txt-mut)', fontSize: '0.7rem', lineHeight: 1.5 }}>Next action: {nextActionText}</p>
            )}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10, fontSize: '0.7rem', color: 'var(--txt-mut)' }}>
              <span>Active provider: <strong style={{ color: 'var(--txt-pri)' }}>{activeProvider}</strong></span>
              {runtime?.active_model && <span>Model: <strong style={{ color: 'var(--txt-pri)' }}>{runtime.active_model}</strong></span>}
              {runtime?.fallback_used && <span>Fallback active{fallbackReason ? ` · ${fallbackReason}` : ''}</span>}
              {fallbackChain && <span>Chain: {fallbackChain}</span>}
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
              {providers.map(provider => {
                const providerTone = provider.status === 'ready' ? '#22c55e' : provider.status === 'offline' ? '#f87171' : '#f59e0b'
                return (
                  <span key={provider.provider} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5,
                    padding: '5px 8px', borderRadius: 999,
                    border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)',
                    fontSize: '0.68rem', color: provider.active ? 'var(--txt-pri)' : 'var(--txt-sec)',
                  }}>
                    <Activity size={11} color={providerTone} />
                    {provider.provider}
                    {provider.active && <strong style={{ color: 'var(--photon)' }}>active</strong>}
                    {provider.fallback_target && <strong style={{ color: '#f59e0b' }}>fallback</strong>}
                  </span>
                )
              })}
            </div>
          </div>
        )}
      </div>
    )
  }

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
