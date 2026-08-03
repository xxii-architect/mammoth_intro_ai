import { useState, useEffect } from 'react'
import { ClipboardList, Plus, ChevronDown, ChevronRight, Tag } from 'lucide-react'
import { api } from '../api/client'

export default function BuildLogPage() {
  const [entries, setEntries]   = useState([])
  const [open, setOpen]         = useState({})
  const [showForm, setShowForm] = useState(false)
  const [filter, setFilter]     = useState('')
  const [form, setForm]         = useState({ title: '', description: '', command: '', tags: '' })
  const [saving, setSaving]     = useState(false)

  useEffect(() => {
    api('/buildlog').then(setEntries).catch(() => {})
  }, [])

  const toggleEntry = (id) => setOpen(prev => ({ ...prev, [id]: !prev[id] }))

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    const tags = form.tags.split(',').map(t => t.trim()).filter(Boolean)
    try {
      const entry = await api('/buildlog', {
        method: 'POST',
        body: { title: form.title, description: form.description, command: form.command, tags },
      })
      setEntries(prev => [...prev, entry])
      setForm({ title: '', description: '', command: '', tags: '' })
      setShowForm(false)
    } catch (e) {
      alert('Failed: ' + e.message)
    }
    setSaving(false)
  }

  const allTags = [...new Set(entries.flatMap(e => e.tags || []))]

  const filtered = filter
    ? entries.filter(e => (e.tags || []).includes(filter))
    : entries

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <ClipboardList size={20} color="var(--photon)" /> Build Log
        </h1>
        <button onClick={() => setShowForm(f => !f)}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.08)', color: 'var(--photon)', fontSize: '0.85rem', cursor: 'pointer' }}>
          <Plus size={16} /> New Entry
        </button>
      </div>

      {/* Tag filters */}
      {allTags.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 16 }}>
          <span onClick={() => setFilter('')}
            style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', padding: '4px 10px', borderRadius: 20, border: `1px solid ${!filter ? 'var(--photon)' : 'var(--border)'}`, background: !filter ? 'rgba(77,166,255,0.1)' : 'rgba(255,255,255,0.04)', color: !filter ? 'var(--photon)' : 'var(--txt-sec)', cursor: 'pointer' }}>
            all
          </span>
          {allTags.map(tag => (
            <span key={tag} onClick={() => setFilter(tag)}
              style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', padding: '4px 10px', borderRadius: 20, border: `1px solid ${filter === tag ? 'var(--cyan)' : 'var(--border)'}`, background: filter === tag ? 'rgba(0,245,212,0.08)' : 'rgba(255,255,255,0.04)', color: filter === tag ? 'var(--cyan)' : 'var(--txt-sec)', cursor: 'pointer' }}>
              #{tag}
            </span>
          ))}
        </div>
      )}

      {/* New entry form */}
      {showForm && (
        <form onSubmit={submit} className="glass-card-solid" style={{ padding: 20, marginBottom: 20 }}>
          <h3 style={{ marginBottom: 16 }}>New Build Log Entry</h3>
          <div style={{ display: 'grid', gap: 12 }}>
            {[
              { key: 'title', label: 'Title', placeholder: 'e.g. Refactored CortexRouter' },
              { key: 'command', label: 'Command', placeholder: 'e.g. python -m cli.main health' },
              { key: 'tags', label: 'Tags (comma-sep)', placeholder: 'e.g. refactor, backend' },
            ].map(({ key, label, placeholder }) => (
              <div key={key}>
                <label style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', display: 'block', marginBottom: 4 }}>{label}</label>
                <input value={form[key]} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
                  placeholder={placeholder}
                  style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box' }} />
              </div>
            ))}
            <div>
              <label style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', display: 'block', marginBottom: 4 }}>Description</label>
              <textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                rows={3} placeholder="What did you do?"
                style={{ width: '100%', padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.85rem', resize: 'vertical', outline: 'none', boxSizing: 'border-box' }} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" disabled={saving}
                style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: 'var(--photon)', color: '#050608', fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer' }}>
                {saving ? 'Saving…' : 'Save'}
              </button>
              <button type="button" onClick={() => setShowForm(false)}
                style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid var(--border)', background: 'none', color: 'var(--txt-sec)', fontSize: '0.85rem', cursor: 'pointer' }}>
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {/* Entries list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {filtered.length === 0 && <div style={{ color: 'var(--txt-mut)', fontSize: '0.9rem', padding: 16 }}>No entries yet.</div>}
        {[...filtered].reverse().map(e => (
          <div key={e.id} className="glass-card-solid" style={{ borderRadius: 10, overflow: 'hidden' }}>
            <div onClick={() => toggleEntry(e.id)}
              style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', cursor: 'pointer' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {open[e.id] ? <ChevronDown size={16} color="var(--txt-mut)" /> : <ChevronRight size={16} color="var(--txt-mut)" />}
                <div>
                  <p style={{ fontSize: '0.88rem', fontWeight: 600, color: 'var(--txt-pri)' }}>{e.title || 'Untitled'}</p>
                  {e.command && <p style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--photon)', marginTop: 2 }}>{e.command}</p>}
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
                <span style={{ fontSize: '0.68rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)' }}>
                  {e.created_at ? new Date(e.created_at).toLocaleDateString() : ''}
                </span>
                <div style={{ display: 'flex', gap: 4 }}>
                  {(e.tags || []).map(t => (
                    <span key={t} style={{ fontSize: '0.62rem', fontFamily: 'JetBrains Mono,monospace', padding: '2px 6px', borderRadius: 10, background: 'rgba(0,245,212,0.08)', color: 'var(--cyan)', border: '1px solid rgba(0,245,212,0.2)' }}>#{t}</span>
                  ))}
                </div>
              </div>
            </div>
            {open[e.id] && e.description && (
              <div style={{ padding: '0 16px 16px 44px', fontSize: '0.82rem', color: 'var(--txt-sec)', lineHeight: 1.6, borderTop: '1px solid var(--border)' }}>
                <p style={{ paddingTop: 12 }}>{e.description}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
