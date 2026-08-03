import { useState, useEffect } from 'react'
import { Copy, LayoutDashboard } from 'lucide-react'
import { api } from '../api/client'
import { useInterval } from '../hooks/useApi'

function Sparkline({ points, color, gradId }) {
  return (
    <svg width="60" height="20" viewBox="0 0 60 20">
      <polyline fill="none" stroke={color} strokeWidth="1.5" points={points} />
      {gradId && (
        <>
          <polyline fill={`url(#${gradId})`} stroke="none" points={`0,20 ${points} 60,20`} />
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity="0.3" />
              <stop offset="100%" stopColor={color} stopOpacity="0" />
            </linearGradient>
          </defs>
        </>
      )}
    </svg>
  )
}

const quickCmds = [
  'uvicorn api_server:app --reload',
  'npm run dev',
  'python -m cli.main status',
  'git status',
]

const bootSequence = [
  'BIOS: MammothOS kernel loaded',
  'ATLAS runtime: initialized',
  'LLM bridge: adapter routing online',
  'Telemetry buses: synchronized',
  'Command center: ready',
]

export default function HomePage() {
  const [status, setStatus] = useState(null)
  const [health, setHealth] = useState(null)
  const [buildlog, setBuildlog] = useState([])
  const [sales, setSales] = useState([])
  const [copied, setCopied] = useState(null)

  const fetchAll = async () => {
    try {
      const [s, h, b, sl] = await Promise.all([
        api('/status'),
        api('/health'),
        api('/buildlog'),
        api('/logsale'),
      ])
      setStatus(s)
      setHealth(h)
      setBuildlog(b)
      setSales(sl)
    } catch (_) {}
  }

  useEffect(() => { fetchAll() }, [])
  useInterval(fetchAll, 30000)

  const copy = (cmd) => {
    navigator.clipboard.writeText(cmd)
    setCopied(cmd)
    setTimeout(() => setCopied(null), 1200)
  }

  const stats = status ? [
    { label: 'Agent Sessions', value: String(status.agent_count || 0), color: 'var(--photon)', gradId: 'sg1', points: '0,15 8,12 16,8 24,14 32,6 40,10 48,4 56,7 60,3' },
    { label: 'CLI Commands Run', value: String(status.cli_commands_run || buildlog.length), color: 'var(--cyan)', gradId: 'sg2', points: '0,18 10,12 20,14 30,6 40,9 50,3 60,7' },
    { label: 'Active Models', value: String(status.active_models || 3), color: 'var(--violet)', gradId: null, points: '0,10 12,10 24,10 36,6 48,6 60,6' },
    { label: 'Uptime', value: status.uptime || '–', color: '#22c55e', gradId: 'sg4', points: '0,18 15,16 30,12 45,8 60,4' },
  ] : [
    { label: 'Agent Sessions', value: '–', color: 'var(--photon)', gradId: 'sg1', points: '0,15 60,15' },
    { label: 'CLI Commands Run', value: '–', color: 'var(--cyan)', gradId: 'sg2', points: '0,15 60,15' },
    { label: 'Active Models', value: '–', color: 'var(--violet)', gradId: null, points: '0,10 60,10' },
    { label: 'Uptime', value: '–', color: '#22c55e', gradId: 'sg4', points: '0,15 60,15' },
  ]

  const services = health?.services || []

  // combine recent activity from buildlog + sales
  const activity = [
    ...buildlog.slice(-3).reverse().map(e => ({
      dot: 'var(--photon)',
      msg: `Build: ${e.title || e.command || 'entry'}`,
      time: e.created_at ? new Date(e.created_at).toLocaleTimeString() : '',
    })),
    ...sales.slice(-3).reverse().map(e => ({
      dot: 'var(--cyan)',
      msg: `Sale: ${e.item} — $${e.amount}`,
      time: e.created_at ? new Date(e.created_at).toLocaleTimeString() : '',
    })),
  ].slice(0, 6)

  const fallbackActivity = [
    { dot: '#22c55e', msg: 'MammothOS Command Center started', time: 'now' },
  ]

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20 }}>
        Welcome back, Vernon
      </h1>

      {/* Stat cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: 12, marginBottom: 24 }}>
        {stats.map(s => (
          <div key={s.label} className="glass-card-solid" style={{ padding: 16 }}>
            <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)', marginBottom: 6 }}>{s.label}</p>
            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
              <span style={{ fontSize: '1.6rem', fontWeight: 700, fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{s.value}</span>
              <Sparkline points={s.points} color={s.color} gradId={s.gradId} />
            </div>
          </div>
        ))}
      </div>

      {/* Workspace status */}
      <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 12 }}>Workspace Status</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(170px,1fr))', gap: 12, marginBottom: 24 }}>
        {services.length > 0 ? services.map(s => (
          <div key={s.label} className="glass-card-solid" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: s.status === 'green' ? '#22c55e' : s.status === 'yellow' ? '#eab308' : '#ef4444' }} />
              <span style={{ fontSize: '0.78rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-pri)' }}>{s.label}</span>
            </div>
            <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>{s.detail}</p>
          </div>
        )) : (
          <div className="glass-card-solid" style={{ padding: 16, color: 'var(--txt-mut)', fontSize: '0.82rem' }}>
            Connecting to backend…
          </div>
        )}
      </div>

      {/* Quick commands */}
      <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 12 }}>Quick Commands</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 24 }}>
        {quickCmds.map(cmd => (
          <button key={cmd} onClick={() => copy(cmd)} className="glass-card-solid"
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 8, cursor: 'pointer', fontSize: '0.78rem', fontFamily: 'JetBrains Mono,monospace', color: copied === cmd ? 'var(--cyan)' : 'var(--photon)', background: 'var(--card)' }}>
            <Copy size={12} />
            {copied === cmd ? 'Copied!' : cmd}
          </button>
        ))}
      </div>

      {/* Recent activity */}
      <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 12 }}>Recent Activity</p>
      <div className="glass-card-solid" style={{ padding: '4px 16px' }}>
        {(activity.length ? activity : fallbackActivity).map((a, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: a.dot, flexShrink: 0 }} />
            <span style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', flex: 1 }}>{a.msg}</span>
            <span style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', whiteSpace: 'nowrap' }}>{a.time}</span>
          </div>
        ))}
      </div>

      <p style={{ fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', margin: '20px 0 12px' }}>
        Boot Sequence
      </p>
      <div className="glass-card-solid" style={{ padding: '10px 16px' }}>
        {bootSequence.map((line, i) => (
          <div key={line} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderTop: i ? '1px solid var(--border)' : 'none' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#22c55e', flexShrink: 0 }} />
            <span style={{ fontSize: '0.78rem', color: 'var(--txt-sec)', fontFamily: 'JetBrains Mono,monospace' }}>{line}</span>
          </div>
        ))}
      </div>

      <footer style={{ textAlign: 'center', padding: '32px 0 8px', color: 'var(--txt-mut)', fontSize: '0.7rem' }}>
        MammothOS Command Center 2036
      </footer>
    </div>
  )
}
