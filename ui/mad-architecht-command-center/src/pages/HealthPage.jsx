import { useEffect, useState } from 'react'
import { HeartPulse, RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import { useInterval } from '../hooks/useApi'
import PersonalHealth from './PersonalHealth';

export default function HealthPage() {
  const [health, setHealth]     = useState(null)
  const [loading, setLoading]   = useState(true)
  const [lastCheck, setLastCheck] = useState(null)

  const fetch = async () => {
    setLoading(true)
    try {
      const data = await api('/health')
      setHealth(data)
      setLastCheck(new Date())
    } catch (_) {}
    setLoading(false)
  }

  useEffect(() => { fetch() }, [])
  useInterval(fetch, 10000)

  const dotClass = (s) => s === 'green' ? 'green' : s === 'yellow' ? 'yellow' : s === 'red' ? 'red' : 'gray'
  const statusText = (s) => s === 'green' ? '● UP' : s === 'yellow' ? '● WARN' : s === 'red' ? '● DOWN' : '○ UNKNOWN'
  const runtime = health?.runtime || null
  const providerColor = (status) => status === 'ready' ? '#22c55e' : status === 'offline' ? '#f87171' : '#eab308'

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <HeartPulse size={20} color="var(--cyan)" /> System Health
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {lastCheck && (
            <span style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
              Last: {lastCheck.toLocaleTimeString()}
            </span>
          )}
          <button onClick={fetch} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.82rem' }}>
            <RefreshCw size={14} style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} /> Refresh
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 16 }}>
        <div className="glass-card-solid" style={{ borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', fontSize: '0.8rem', fontWeight: 600, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
            Services
          </div>
          {health?.services?.length ? health.services.map((h, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 20px', borderTop: i ? '1px solid var(--border)' : 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div className={`health-dot ${dotClass(h.status)}`} />
                <div>
                  <p style={{ fontSize: '0.85rem', color: 'var(--txt-pri)' }}>{h.label}</p>
                  <p style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', marginTop: 2 }}>{h.detail}</p>
                </div>
              </div>
              <span style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: h.status === 'green' ? '#22c55e' : h.status === 'yellow' ? '#eab308' : '#ef4444' }}>
                {statusText(h.status)}
              </span>
            </div>
          )) : (
            <div style={{ padding: 20, color: 'var(--txt-mut)', fontSize: '0.85rem' }}>
              {loading ? 'Checking services…' : 'Could not reach backend.'}
            </div>
          )}
        </div>

        <div className="glass-card-solid" style={{ borderRadius: 12, overflow: 'hidden' }}>
          <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', fontSize: '0.8rem', fontWeight: 600, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
            Runtime providers
          </div>
          {runtime ? (
            <div style={{ padding: 20, display: 'grid', gap: 14 }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 12 }}>
                <div>
                  <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 4 }}>Runtime state</p>
                  <p style={{ fontSize: '0.92rem', color: runtime.state === 'ready' ? '#22c55e' : '#eab308', fontWeight: 700, textTransform: 'capitalize' }}>{runtime.state}</p>
                </div>
                <div>
                  <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 4 }}>Active adapter</p>
                  <p style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', fontFamily: 'JetBrains Mono,monospace' }}>{runtime.active_adapter || 'unknown'}</p>
                </div>
                <div>
                  <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 4 }}>Active model</p>
                  <p style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', fontFamily: 'JetBrains Mono,monospace' }}>{runtime.active_model || 'unknown'}</p>
                </div>
              </div>
              <div style={{ display: 'grid', gap: 8 }}>
                {(runtime.providers || []).map((provider) => (
                  <div key={provider.provider} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                    <div>
                      <div style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', textTransform: 'capitalize' }}>{provider.provider}</div>
                      <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>{provider.detail}</div>
                    </div>
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: providerColor(provider.status), textTransform: 'uppercase' }}>{provider.status}</span>
                  </div>
                ))}
              </div>
              <p style={{ margin: 0, fontSize: '0.76rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>
                {runtime.recommendation}
              </p>
            </div>
          ) : (
            <div style={{ padding: 20, color: 'var(--txt-mut)', fontSize: '0.85rem' }}>
              {loading ? 'Inspecting runtime…' : 'Runtime snapshot unavailable.'}
            </div>
          )}
        </div>

        {health?.env_keys?.length > 0 && (
          <div className="glass-card-solid" style={{ borderRadius: 12, overflow: 'hidden' }}>
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', fontSize: '0.8rem', fontWeight: 600, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
              .env Keys
            </div>
            {health.env_keys.map((k, i) => (
              <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 20px', borderTop: i ? '1px solid var(--border)' : 'none' }}>
                <div className="health-dot green" />
                <span style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{k}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <PersonalHealth />

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}