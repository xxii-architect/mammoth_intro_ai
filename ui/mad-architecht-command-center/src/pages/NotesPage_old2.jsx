import { useState, useEffect } from 'react'
import { Plus, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import NotesPanel from '../notes/NotesPanel';
import AgentNotesPanel from '../notes/AgentNotesPanel';

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
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: 16 }}>
        <h2 style={{ color: 'var(--txt-pri)' }}>Your Notes</h2>
        <NotesPanel />
        <h2 style={{ color: 'var(--txt-pri)' }}>Agent Notes</h2>
        <AgentNotesPanel />
      </div>
    </div>
  )
}