import React from 'react'
import { FileText, RefreshCw } from 'lucide-react'
import { useAgentNotes } from './hooks/useAgentNotes'
import { useCreateNote } from './hooks/useCreateNote'
import { useDeleteNote } from './hooks/useDeleteNote'
import { NotesList } from './NotesList'
import { NotesComposer } from './NotesComposer'
import { api } from '../api/client'
import { NoteRecord } from './types/NoteRecord'

const NotesPanel: React.FC = () => {
  const { notes, setNotes, loading, error, reload } = useAgentNotes()
  const { createNote, loading: creating, error: createError } = useCreateNote()
  const { deleteNote, loading: deleting, error: deleteError } = useDeleteNote()

  const [query, setQuery] = React.useState('')
  const [editing, setEditing] = React.useState(false)
  const [actionError, setActionError] = React.useState('')
  const busy = creating || deleting || editing
  const statusMessage = actionError || error || createError || deleteError
  const filtered = notes.filter(note => [note.title, note.content, note.body, note.subsystem, note.agent_id]
    .join(' ').toLowerCase().includes(query.trim().toLowerCase()))
  const personalNotes = filtered.filter((note) => note.source !== 'agent')
  const agentNotes = filtered.filter((note) => note.source === 'agent')

  const handleCreate = async (content: string) => {
    const created = await createNote(content)
    if (created) {
      setNotes((prev) => [created, ...prev])
    } else {
      await reload()
    }
  }

  const handleDelete = async (id: string) => {
    setActionError('')
    try {
      await deleteNote(id)
      setNotes((prev) => prev.filter((note) => note.id !== id))
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : 'Note could not be deleted.')
    }
  }

  const handleUpdate = async (note: NoteRecord, content: string) => {
    setEditing(true)
    setActionError('')
    try {
      const saved = await api('/notes', { method: 'POST', body: {
        ...note, body: content, content, title: content.split(/\r?\n/, 1)[0].trim().slice(0, 72) || 'Untitled',
      } })
      if (saved?.id !== note.id) throw new Error('The server did not confirm the note update. Your draft is retained.')
      setNotes(previous => previous.map(item => item.id === saved.id ? saved : item))
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : 'Note could not be updated.')
      throw cause
    } finally { setEditing(false) }
  }

  return (
    <section className="glass-card-solid" style={{ padding: 20, borderLeft: '2px solid var(--cyan)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <div className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileText size={14} color="var(--cyan)" />
            Command Center notes
          </div>
          <h2 style={{ fontSize: '1rem', marginBottom: 6 }}>Your saved working notes</h2>
          <p style={{ color: 'var(--txt-sec)', fontSize: '0.84rem', lineHeight: 1.7, maxWidth: 640 }}>
            Personal and agent-authored notes are private to your account. Search, expand, edit or export the full note.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="glass-card" style={{ padding: '8px 12px', minWidth: 118 }}>
            <div style={{ color: 'var(--txt-mut)', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.16em' }}>Notes loaded</div>
            <div style={{ color: 'var(--txt-pri)', fontFamily: 'JetBrains Mono, monospace', fontSize: '1.1rem', marginTop: 4 }}>{notes.length}</div>
          </div>
          <button className="ghost-btn" onClick={() => void reload()} disabled={loading || busy} style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
            <RefreshCw size={14} />
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 12, marginBottom: 16 }}>
        <div className="glass-card" style={{ padding: '8px 12px' }}>
          <div style={{ color: 'var(--txt-mut)', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.16em' }}>Personal notes</div>
          <div style={{ color: 'var(--txt-pri)', fontFamily: 'JetBrains Mono, monospace', fontSize: '1.05rem', marginTop: 4 }}>{personalNotes.length}</div>
        </div>
        <div className="glass-card" style={{ padding: '8px 12px' }}>
          <div style={{ color: 'var(--txt-mut)', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.16em' }}>Agent notes</div>
          <div style={{ color: 'var(--txt-pri)', fontFamily: 'JetBrains Mono, monospace', fontSize: '1.05rem', marginTop: 4 }}>{agentNotes.length}</div>
        </div>
      </div>

      {statusMessage ? (
        <div role="alert" style={{ marginBottom: 16, padding: 12, borderRadius: 12, border: '1px solid rgba(239,68,68,0.24)', background: 'rgba(127,29,29,0.18)', color: '#fecaca', fontSize: '0.8rem' }}>
          {statusMessage}
        </div>
      ) : null}

      <label>Search notes <input aria-label="Search notes" value={query} onChange={event => setQuery(event.target.value)} /></label>
      <p role="status">{filtered.length} of {notes.length} notes shown</p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))', gap: 16 }}>
        <NotesComposer onCreate={handleCreate} busy={busy} />
        <div className="glass-card" style={{ padding: 16 }}>
          {loading ? (
            <div style={{ color: 'var(--txt-sec)', fontSize: '0.84rem' }}>Loading notes…</div>
          ) : (
            <div style={{ display: 'grid', gap: 18 }}>
              <NotesList notes={personalNotes} onDelete={handleDelete} onUpdate={handleUpdate} busy={busy} />
              <NotesList notes={agentNotes} onDelete={handleDelete} onUpdate={handleUpdate} busy={busy} />
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

export default NotesPanel
