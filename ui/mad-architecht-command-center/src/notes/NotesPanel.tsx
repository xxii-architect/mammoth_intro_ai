import React from 'react'
import { FileText, RefreshCw } from 'lucide-react'
import { useAgentNotes } from './hooks/useAgentNotes'
import { useCreateNote } from './hooks/useCreateNote'
import { useDeleteNote } from './hooks/useDeleteNote'
import { NotesList } from './NotesList'
import { NotesComposer } from './NotesComposer'

const NotesPanel: React.FC = () => {
  const { notes, setNotes, loading, error, reload } = useAgentNotes()
  const { createNote, loading: creating, error: createError } = useCreateNote()
  const { deleteNote, loading: deleting, error: deleteError } = useDeleteNote()

  const busy = creating || deleting
  const statusMessage = error || createError || deleteError
  const personalNotes = notes.filter((note) => note.source !== 'agent')
  const agentNotes = notes.filter((note) => note.source === 'agent')

  const handleCreate = async (content: string) => {
    const created = await createNote(content)
    if (created) {
      setNotes((prev) => [created, ...prev])
    } else {
      await reload()
    }
  }

  const handleDelete = async (id: string) => {
    await deleteNote(id)
    setNotes((prev) => prev.filter((note) => note.id !== id))
  }

  return (
    <section className="glass-card-solid" style={{ padding: 20, borderLeft: '2px solid var(--cyan)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <div className="eyebrow" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <FileText size={14} color="var(--cyan)" />
            Command Center notes
          </div>
          <h2 style={{ fontSize: '1rem', marginBottom: 6 }}>Layered capture panel</h2>
          <p style={{ color: 'var(--txt-sec)', fontSize: '0.84rem', lineHeight: 1.7, maxWidth: 640 }}>
            Personal notes and agent-authored notes both live in the shared notes store. This panel now shows the saved note title,
            a readable preview, and click-to-expand reading instead of just raw rows.
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
        <div style={{ marginBottom: 16, padding: 12, borderRadius: 12, border: '1px solid rgba(239,68,68,0.24)', background: 'rgba(127,29,29,0.18)', color: '#fecaca', fontSize: '0.8rem' }}>
          {statusMessage}
        </div>
      ) : null}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 340px) minmax(0, 1fr)', gap: 16 }}>
        <NotesComposer onCreate={handleCreate} busy={busy} />
        <div className="glass-card" style={{ padding: 16 }}>
          {loading ? (
            <div style={{ color: 'var(--txt-sec)', fontSize: '0.84rem' }}>Loading notes…</div>
          ) : (
            <div style={{ display: 'grid', gap: 18 }}>
              <NotesList notes={personalNotes} onDelete={handleDelete} busy={busy} />
              <NotesList notes={agentNotes} onDelete={handleDelete} busy={busy} />
            </div>
          )}
        </div>
      </div>
    </section>
  )
}

export default NotesPanel
