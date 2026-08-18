import React from 'react'
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

const NotesList: React.FC<{ notes: NoteRecord[]; onDelete: (id: string) => void; busy?: boolean }> = ({
  notes,
  onDelete,
  busy = false,
}) => {
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
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="eyebrow" style={{ marginBottom: 6 }}>
                {note.type || 'note'} {note.priority ? `• ${note.priority}` : ''}
              </div>
              <p style={{ color: 'var(--txt-pri)', fontSize: '0.9rem', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{note.content}</p>
              <div style={{ marginTop: 10, color: 'var(--txt-mut)', fontSize: '0.72rem' }}>
                {note.subsystem || 'general'} • {new Date(note.created_at).toLocaleString()}
              </div>
            </div>
            <button onClick={() => onDelete(note.id)} style={deleteButtonStyle} disabled={busy}>
              Delete
            </button>
          </div>
        </li>
      ))}
    </ul>
  )
}

export { NotesList }
