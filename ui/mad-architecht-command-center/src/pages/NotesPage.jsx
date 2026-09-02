import NotesPanel from '../notes/NotesPanel'

export default function NotesPage() {
  return (
    <div className="page-enter" style={{ padding: '24px 24px 32px', maxWidth: 1280, margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap', marginBottom: 18 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Working memory</div>
          <h1 style={{ margin: 0, fontSize: '1.35rem', fontWeight: 800, color: 'var(--txt-pri)' }}>Notes</h1>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: 12, minWidth: 'min(100%, 360px)', flex: 1 }}>
          <div className="glass-card-solid" style={{ padding: 12 }}>
            <div style={{ fontSize: '0.68rem', letterSpacing: '0.12em', color: 'var(--txt-mut)', textTransform: 'uppercase' }}>Capture mode</div>
            <div style={{ marginTop: 6, fontSize: '1.05rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Focused</div>
          </div>
          <div className="glass-card-solid" style={{ padding: 12 }}>
            <div style={{ fontSize: '0.68rem', letterSpacing: '0.12em', color: 'var(--txt-mut)', textTransform: 'uppercase' }}>Flow</div>
            <div style={{ marginTop: 6, fontSize: '1.05rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Dense, readable</div>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        <NotesPanel />
      </div>
    </div>
  )
}
