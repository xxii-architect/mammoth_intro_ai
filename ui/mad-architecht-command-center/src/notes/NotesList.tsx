import React, { useState } from 'react'
import { NoteRecord } from './types/NoteRecord'

const listStyle: React.CSSProperties = {
  listStyle: 'none',
  display: 'grid',
  gap: 12,
  padding: 0,
  margin: 0,
}

const noteCardStyle: React.CSSProperties = {
  borderRadius: 14,
  border: '1px solid rgba(255,255,255,0.08)',
  borderLeft: '3px solid var(--cyan)',
  background: 'linear-gradient(180deg, rgba(13,17,23,0.94), rgba(13,17,23,0.78))',
  padding: 14,
  boxShadow: '0 12px 26px rgba(0,0,0,0.22)',
}

const deleteButtonStyle: React.CSSProperties = {
  padding: '7px 12px',
  borderRadius: 999,
  border: '1px solid rgba(239,68,68,0.28)',
  background: 'rgba(239,68,68,0.08)',
  color: '#fca5a5',
  cursor: 'pointer',
  fontSize: '0.76rem',
  fontWeight: 600,
}

const previewText = (note: NoteRecord) => {
  const text = (note.content || note.body || '').trim()
  if (!text) return 'Empty note'
  return text.length > 160 ? `${text.slice(0, 157)}...` : text
}

const formatTimestamp = (note: NoteRecord) => {
  const raw = note.updated_at || note.created_at
  if (!raw) return 'No timestamp yet'
  const parsed = new Date(raw)
  return Number.isNaN(parsed.getTime()) ? 'No timestamp yet' : parsed.toLocaleString()
}

const NotesList: React.FC<{ notes: NoteRecord[]; onDelete: (id: string) => void; onUpdate: (note: NoteRecord, content: string) => Promise<void>; busy?: boolean }> = ({
  notes,
  onDelete,
  onUpdate,
  busy = false,
}) => {
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [editError, setEditError] = useState('')
  const [confirmId, setConfirmId] = useState<string | null>(null)

  const exportNote = (note: NoteRecord) => {
    const url = URL.createObjectURL(new Blob([note.content || note.body], { type: 'text/markdown;charset=utf-8' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `${note.title.replace(/[^a-z0-9_-]+/gi, '-').slice(0, 80) || 'note'}.md`
    link.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }

  if (notes.length === 0) {
    return (
      <div className="glass-card-solid" style={{ padding: 18, color: 'var(--txt-sec)', lineHeight: 1.7 }}>
        No notes yet. Create one above to start building your Command Center memory.
      </div>
    )
  }

  return (
    <ul style={listStyle}>
      {notes.map((note) => (
        <li key={note.id} style={noteCardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}>
            <button type="button"
              onClick={() => setExpandedId((current) => current === note.id ? null : note.id)}
              aria-expanded={expandedId === note.id}
              style={{ flex: 1, minWidth: 0, background: 'transparent', border: 0, textAlign: 'left', padding: 0, cursor: 'pointer' }}
            >
              <div className="eyebrow" style={{ marginBottom: 6 }}>
                {(note.source === 'agent' ? (note.agent_id || 'agent') : 'personal')} • {note.priority || 'normal'}
              </div>
              <div style={{ color: 'var(--txt-pri)', fontSize: '0.88rem', fontWeight: 700, marginBottom: 6 }}>
                {note.title || 'Untitled'}
              </div>
              <p style={{ color: 'var(--txt-pri)', fontSize: '0.9rem', lineHeight: 1.7, whiteSpace: 'pre-wrap', margin: 0 }}>
                {expandedId === note.id ? (note.content || note.body || 'Empty note') : previewText(note)}
              </p>
              <div style={{ marginTop: 10, color: 'var(--txt-mut)', fontSize: '0.72rem' }}>
                {note.subsystem || 'general'} • {formatTimestamp(note)} • {expandedId === note.id ? 'Click to collapse' : 'Click to expand'}
              </div>
            </button>
            <button onClick={() => setConfirmId(note.id)} style={deleteButtonStyle} disabled={busy}>
              Delete
            </button>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
            <button disabled={busy} onClick={() => { setEditingId(note.id); setDraft(note.content || note.body); setEditError('') }}>Edit note</button>
            <button onClick={() => exportNote(note)}>Export note</button>
          </div>
          {confirmId === note.id && <div role="group" aria-label="Confirm note deletion">
            <p>Delete this note? This cannot be undone.</p>
            <button disabled={busy} onClick={() => { onDelete(note.id); setConfirmId(null) }}>Confirm delete</button>
            <button disabled={busy} onClick={() => setConfirmId(null)}>Cancel deletion</button>
          </div>}
          {editingId === note.id && <div>
            <textarea aria-label="Edit note content" value={draft} onChange={event => setDraft(event.target.value)} disabled={busy}
              style={{ width: '100%', boxSizing: 'border-box', minHeight: 160 }} />
            {editError && <p role="alert">{editError}</p>}
            <button disabled={busy || !draft.trim()} onClick={async () => {
              try { await onUpdate(note, draft.trim()); setEditingId(null) }
              catch (cause) { setEditError(cause instanceof Error ? cause.message : 'Update failed. Your draft is retained.') }
            }}>Save changes</button>
            <button disabled={busy} onClick={() => setEditingId(null)}>Cancel edit</button>
          </div>}
        </li>
      ))}
    </ul>
  )
}

export { NotesList }
