import { useState, useEffect } from 'react'
import { Package, RefreshCw } from 'lucide-react'
import { api } from '../api/client'

const statusColor = {
  active: '#22c55e',
  ready: '#60a5fa',
  loading: '#eab308',
  error: '#ef4444',
  disabled: '#4a5568',
  idle: '#60a5fa',
}

export default function ModulesPage() {
  const [modules, setModules]   = useState([])
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const loadModules = async ({ background = false } = {}) => {
    if (!background) setLoading(true)
    setRefreshing(background)
    try {
      const data = await api('/modules')
      setModules(data)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadModules()
  }, [])

  const filtered = modules.filter(m =>
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    (m.description || '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Package size={20} color="var(--photon)" /> Modules Registry
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search modules…"
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)', fontSize: '0.85rem', outline: 'none', width: 200 }} />
          <button
            onClick={() => loadModules({ background: true })}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', padding: '7px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer' }}
          >
            <RefreshCw size={14} style={{ opacity: refreshing ? 0.6 : 1 }} />
            {refreshing ? 'Refreshing' : 'Refresh'}
          </button>
        </div>
      </div>

      {loading ? (
        <div style={{ color: 'var(--txt-mut)', fontSize: '0.9rem' }}>Loading modules…</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 12 }}>
          {filtered.map(m => {
            const st = m.status
            return (
              <div key={m.id} className="glass-card-solid" style={{ padding: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                  <div>
                    <p style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--txt-pri)' }}>{m.name}</p>
                    <p style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', marginTop: 2 }}>{m.version}</p>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 20, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)' }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: statusColor[st] || '#4a5568' }} />
                    <span style={{ fontSize: '0.68rem', fontFamily: 'JetBrains Mono,monospace', color: statusColor[st] || '#4a5568' }}>{st}</span>
                  </div>
                </div>
                <p style={{ fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.5, marginBottom: 8 }}>{m.description}</p>
                {m.workflow_ready !== undefined && (
                  <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 10 }}>
                    Workflow: {m.workflow_path === 'atlas_lesson' ? 'wired into ATLAS lesson flow' : m.workflow_stage === 'routed' ? 'wired into plan/execute' : m.workflow_stage === 'autonomous' ? 'wired into autonomous flow' : 'registered only'}
                  </p>
                )}
                {m.capabilities?.length > 0 && (
                  <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 8 }}>
                    Capabilities: {m.capabilities.join(', ')}
                  </p>
                )}
                {m.quality_tier && (
                  <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 8 }}>
                    Quality: {m.quality_tier} ({m.quality_score}/100){m.interface_mode ? ` • ${m.interface_mode}` : ''}
                  </p>
                )}
                {(m.last_activity_at || m.last_heartbeat_at) && (
                  <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 8 }}>
                    Runtime: {m.observed_active ? 'active signal observed' : 'no recent active signal'}
                    {m.last_activity_at ? ` • activity ${new Date(m.last_activity_at).toLocaleString()}` : ''}
                    {m.last_heartbeat_at ? ` • heartbeat ${new Date(m.last_heartbeat_at).toLocaleString()}` : ''}
                  </p>
                )}
                {m.quality_findings?.length > 0 && (
                  <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)' }}>
                    Notes: {m.quality_findings.join(' ')}
                  </p>
                )}
              </div>
            )
          })}
          {filtered.length === 0 && <div style={{ color: 'var(--txt-mut)', fontSize: '0.9rem' }}>No modules match.</div>}
        </div>
      )}
    </div>
  )
}
