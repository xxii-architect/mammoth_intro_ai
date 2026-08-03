import { useState, useEffect } from 'react'
import { Settings, Eye, EyeOff, RotateCcw } from 'lucide-react'
import { api } from '../api/client'

export default function SettingsPage() {
  const [status, setStatus]   = useState(null)
  const [health, setHealth]   = useState(null)
  const [masked, setMasked]   = useState(true)
  const [resetting, setResetting] = useState(false)
  const [resetMsg, setResetMsg]   = useState('')

  useEffect(() => {
    Promise.all([api('/status'), api('/health')]).then(([s, h]) => {
      setStatus(s)
      setHealth(h)
    }).catch(() => {})
  }, [])

  const resetAtlas = async () => {
    setResetting(true)
    try {
      await api('/atlas/reset', { method: 'POST', body: {} })
      setResetMsg('ATLAS session reset successfully.')
    } catch (e) {
      setResetMsg('Reset failed: ' + e.message)
    }
    setResetting(false)
    setTimeout(() => setResetMsg(''), 3000)
  }

  const envKeys = health?.env_keys || []

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
        <Settings size={20} color="var(--txt-sec)" /> Settings
      </h1>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(320px,1fr))', gap: 20 }}>
        {/* System Info */}
        <div className="glass-card-solid" style={{ padding: 20 }}>
          <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', marginBottom: 12, fontWeight: 600 }}>System Info</p>
          <div style={{ display: 'grid', gap: 0 }}>
            {[
              { label: 'Python Version', value: status?.python_version?.split(' ')[0] || '–' },
              { label: 'API Uptime',     value: status?.uptime || '–' },
              { label: 'Engine Count',  value: String(status?.engine_count ?? '–') },
              { label: 'Agent Count',   value: String(status?.agent_count ?? '–') },
              { label: 'UI Project',    value: 'mad-architecht-command-center' },
              { label: 'Port',          value: ':8000 / :5173' },
            ].map(({ label, value }, i) => (
              <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--txt-mut)' }}>{label}</span>
                <span style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Environment */}
        <div className="glass-card-solid" style={{ padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 600 }}>.env Variables</p>
            <button onClick={() => setMasked(m => !m)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)', display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.75rem' }}>
              {masked ? <Eye size={14} /> : <EyeOff size={14} />}
              {masked ? 'Show keys' : 'Hide keys'}
            </button>
          </div>
          {envKeys.length > 0 ? envKeys.map((k, i) => (
            <div key={k} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
              <span style={{ fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{masked ? k : k}</span>
              <span style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)' }}>
                {masked ? '••••••••' : '(set)'}
              </span>
            </div>
          )) : (
            <p style={{ color: 'var(--txt-mut)', fontSize: '0.85rem' }}>
              {health ? 'No .env keys found.' : 'Connecting to backend…'}
            </p>
          )}
        </div>

        {/* ATLAS */}
        <div className="glass-card-solid" style={{ padding: 20 }}>
          <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', marginBottom: 12, fontWeight: 600 }}>ATLAS Session</p>
          <p style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', marginBottom: 16, lineHeight: 1.5 }}>
            Resets the current ATLAS learning session stored in <code style={{ fontFamily: 'JetBrains Mono,monospace', fontSize: '0.8rem', color: 'var(--photon)' }}>.mammoth/atlas_cli_session.json</code>.
          </p>
          <button onClick={resetAtlas} disabled={resetting}
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', borderRadius: 8, border: '1px solid rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)', color: '#f87171', fontSize: '0.85rem', cursor: 'pointer', opacity: resetting ? 0.7 : 1 }}>
            <RotateCcw size={14} /> {resetting ? 'Resetting…' : 'Reset ATLAS Session'}
          </button>
          {resetMsg && (
            <p style={{ marginTop: 10, fontSize: '0.78rem', color: resetMsg.includes('success') ? '#22c55e' : '#f87171' }}>{resetMsg}</p>
          )}
        </div>

        {/* Theme */}
        <div className="glass-card-solid" style={{ padding: 20 }}>
          <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', marginBottom: 12, fontWeight: 600 }}>Theme</p>
          <div style={{ display: 'flex', gap: 12 }}>
            {[{ label: 'Dark', color: '#0d1117' }, { label: 'Darker', color: '#050608' }].map(t => (
              <div key={t.label} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px', borderRadius: 8, border: '1px solid var(--border)', background: t.color, cursor: 'pointer' }}>
                <div style={{ width: 16, height: 16, borderRadius: '50%', background: t.color, border: '2px solid rgba(255,255,255,0.2)' }} />
                <span style={{ fontSize: '0.82rem', color: 'var(--txt-pri)' }}>{t.label}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
