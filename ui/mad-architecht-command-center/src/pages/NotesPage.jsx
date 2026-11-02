import NotesPanel from '../notes/NotesPanel'
import { useAuth } from '../lib/authContext'

export default function NotesPage() {
  const { user, loading } = useAuth()
  if (loading) return <p role="status">Loading your account…</p>
  if (!user) return <p role="status">Sign in to access your private notes.</p>
  return (
    <div className="page-enter" style={{ padding: '24px 24px 32px', maxWidth: 1280, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap', marginBottom: 18 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Working memory</div>
          <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 800, color: 'var(--txt-pri)' }}>Notes</h1>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <NotesPanel key={user.id} />
      </div>
    </div>
  )
}
