import { useState } from 'react'
import { HeartPulse, RefreshCw } from 'lucide-react'
import { api } from '../api/client'
import { useInterval } from '../hooks/useApi'

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

  useState(() => { fetch() }, [])
  useInterval(fetch, 10000)

  const dotClass = (s) => s === 'green' ? 'green' : s === 'yellow' ? 'yellow' : s === 'red' ? 'red' : 'gray'
  const statusText = (s) => s === 'green' ? '● UP' : s === 'yellow' ? '● WARN' : s === 'red' ? '● DOWN' : '○ UNKNOWN'

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

      <style>{`@keyframes spin { from { transform: rotate(0deg) } to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
