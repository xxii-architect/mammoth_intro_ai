import { useState, useEffect } from 'react'
import { Package } from 'lucide-react'
import { api } from '../api/client'

const statusColor = { active: '#22c55e', idle: '#eab308', disabled: '#4a5568' }

export default function ModulesPage() {
  const [modules, setModules]   = useState([])
  const [search, setSearch]     = useState('')
  const [states, setStates]     = useState({})
  const [loading, setLoading]   = useState(true)

  useEffect(() => {
    api('/modules').then(data => {
      setModules(data)
      const init = {}
      data.forEach(m => { init[m.id] = m.status })
      setStates(init)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  const toggle = (id) => {
    setStates(prev => ({
      ...prev,
      [id]: prev[id] === 'active' ? 'idle' : 'active',
    }))
  }

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
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search modules…"
          style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)', fontSize: '0.85rem', outline: 'none', width: 200 }} />
      </div>

      {loading ? (
        <div style={{ color: 'var(--txt-mut)', fontSize: '0.9rem' }}>Loading modules…</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 12 }}>
          {filtered.map(m => {
            const st = states[m.id] || m.status
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
                <p style={{ fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.5, marginBottom: 12 }}>{m.description}</p>
                <button onClick={() => toggle(m.id)}
                  style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', padding: '4px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer' }}>
                  {st === 'active' ? 'Deactivate' : 'Activate'}
                </button>
              </div>
            )
          })}
          {filtered.length === 0 && <div style={{ color: 'var(--txt-mut)', fontSize: '0.9rem' }}>No modules match.</div>}
        </div>
      )}
    </div>
  )
}
