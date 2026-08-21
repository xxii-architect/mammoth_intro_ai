import NotesPanel from '../notes/NotesPanel'

export default function NotesPage() {
  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 16 }}>Notes</h1>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: 16 }}>
        <NotesPanel />
      </div>
    </div>
  )
}
