import { useState, useEffect } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { api } from '../api/client'

export default function NotesPage() {
  const [notes, setNotes]   = useState([])
  const [active, setActive] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api('/notes').then(data => {
      setNotes(data)
      if (data.length) setActive(data[0].id)
    }).catch(() => {})
  }, [])

  const current = notes.find(n => n.id === active)

  const addNote = async () => {
    const n = { title: 'New Note', body: '' }
    try {
      const created = await api('/notes', { method: 'POST', body: n })
      setNotes(prev => [...prev, created])
      setActive(created.id)
    } catch (e) {
      // fallback local
      const local = { ...n, id: String(Date.now()), updated_at: new Date().toISOString() }
      setNotes(prev => [...prev, local])
      setActive(local.id)
    }
  }

  const updateField = (field, value) => {
    setNotes(prev => prev.map(n => n.id === active ? { ...n, [field]: value } : n))
  }

  const saveNote = async () => {
    if (!current) return
    setSaving(true)
    try {
      await api('/notes', { method: 'POST', body: current })
    } catch (_) {}
    setSaving(false)
  }

  const deleteNote = async (id) => {
    try {
      await api(`/notes/${id}`, { method: 'DELETE' })
    } catch (_) {}
    setNotes(prev => prev.filter(n => n.id !== id))
    if (active === id) {
      const remaining = notes.filter(n => n.id !== id)
      setActive(remaining.length ? remaining[0].id : null)
    }
  }

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 16 }}>Notes</h1>
      <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 200px)' }}>
        {/* Sidebar */}
        <div style={{ width: 220, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button onClick={addNote}
            style={{ width: '100%', padding: '10px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.08)', color: 'var(--photon)', fontSize: '0.85rem', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
            <Plus size={16} /> New Note
          </button>
          <div style={{ overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {notes.map(n => (
              <div key={n.id} onClick={() => setActive(n.id)}
                style={{ padding: '10px 12px', borderRadius: 8, border: `1px solid ${active === n.id ? 'rgba(77,166,255,0.4)' : 'var(--border)'}`, background: active === n.id ? 'rgba(77,166,255,0.08)' : 'var(--card)', cursor: 'pointer', fontSize: '0.82rem', color: active === n.id ? 'var(--photon)' : 'var(--txt-pri)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{n.title || 'Untitled'}</span>
                <button onClick={e => { e.stopPropagation(); deleteNote(n.id) }}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', padding: 2, flexShrink: 0 }}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))}
            {notes.length === 0 && <div style={{ color: 'var(--txt-mut)', fontSize: '0.82rem', padding: 8 }}>No notes yet.</div>}
          </div>
        </div>

        {/* Editor */}
        <div className="glass-card-solid" style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column' }}>
          {current ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <input value={current.title}
                  onChange={e => updateField('title', e.target.value)}
                  onBlur={saveNote}
                  style={{ background: 'none', border: 'none', fontSize: '1rem', fontWeight: 600, color: 'var(--txt-pri)', outline: 'none', flex: 1 }} />
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {saving && <span style={{ fontSize: '0.7rem', color: 'var(--txt-mut)' }}>Saving…</span>}
                  <span style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
                    {current.updated_at ? new Date(current.updated_at).toLocaleString() : ''}
                  </span>
                </div>
              </div>
              <textarea value={current.body}
                onChange={e => updateField('body', e.target.value)}
                onBlur={saveNote}
                placeholder="Start typing…"
                style={{ flex: 1, background: 'none', border: 'none', color: 'var(--txt-sec)', fontSize: '0.88rem', resize: 'none', outline: 'none', lineHeight: 1.7, whiteSpace: 'pre-wrap' }} />
            </>
          ) : (
            <div style={{ color: 'var(--txt-mut)', fontSize: '0.9rem' }}>Select or create a note.</div>
          )}
        </div>
      </div>
    </div>
  )
}
