import { ChevronRight, Compass, LifeBuoy } from 'lucide-react'

const sectionLabel = {
  fontSize: '0.66rem',
  textTransform: 'uppercase',
  letterSpacing: '0.12em',
  color: 'var(--txt-mut)',
  fontWeight: 700,
  margin: '0 0 4px',
}

const listStyle = { margin: 0, paddingLeft: 16, fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.6 }

function ManifestList({ title, items, mono = false }) {
  if (!Array.isArray(items) || items.length === 0) return null
  return (
    <div style={{ minWidth: 0 }}>
      <p style={sectionLabel}>{title}</p>
      <ul style={listStyle}>
        {items.map(item => (
          <li key={item} style={mono ? { fontFamily: 'JetBrains Mono,monospace', fontSize: '0.74rem' } : undefined}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

/** Compact "what you need / done when" card built from the backend lesson manifest. */
export function LessonManifestCard({ manifest }) {
  if (!manifest) return null
  const sections = [
    manifest.prerequisites,
    manifest.sample_data,
    manifest.expected_output,
    manifest.success_criteria,
  ]
  if (!sections.some(items => Array.isArray(items) && items.length)) return null
  return (
    <div className="glass-card-solid" style={{ padding: 12, display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
      <ManifestList title="Before you start" items={manifest.prerequisites} />
      <ManifestList title="Sample input" items={manifest.sample_data} mono />
      <ManifestList title="Expected output" items={manifest.expected_output} mono />
      <ManifestList title="Done when" items={manifest.success_criteria} />
    </div>
  )
}

/** Shown when the learner looks stuck on the current step. */
export function StallNotice({ stall }) {
  if (!stall?.stalled) return null
  return (
    <div role="status" style={{ display: 'flex', gap: 10, alignItems: 'flex-start', padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(250,204,21,0.35)', background: 'rgba(250,204,21,0.08)' }}>
      <LifeBuoy size={15} style={{ color: '#facc15', flexShrink: 0, marginTop: 2 }} />
      <div style={{ fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.55 }}>
        <strong style={{ color: 'var(--txt-pri)' }}>Looks like this step is sticky.</strong>{' '}
        {stall.suggestion}
        {Array.isArray(stall.reasons) && stall.reasons.length > 0 && (
          <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', marginTop: 2 }}>{stall.reasons.join(' · ')}</div>
        )}
      </div>
    </div>
  )
}

/** Comprehension gate: the learner can keep practicing or explicitly move on. */
export function LessonGateNotice({ gate, onContinue, onDismiss, busy = false }) {
  if (!gate || gate.allowed) return null
  return (
    <div role="alertdialog" aria-label="Lesson not passed yet" style={{ display: 'grid', gap: 8, padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(var(--mm-color-system-rgb),0.35)', background: 'rgba(var(--mm-color-system-rgb),0.08)' }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <Compass size={15} style={{ color: 'var(--cyan, var(--mm-color-system-default))', flexShrink: 0, marginTop: 2 }} />
        <span style={{ fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.55 }}>{gate.message}</span>
      </div>
      <StallNotice stall={gate.stall} />
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button type="button" onClick={onDismiss} disabled={busy}
          style={{ padding: '5px 12px', borderRadius: 8, border: 'none', background: 'var(--mm-color-action-primary)', color: '#050608', fontWeight: 600, fontSize: '0.76rem', cursor: 'pointer' }}>
          Keep practicing
        </button>
        <button type="button" onClick={onContinue} disabled={busy}
          style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '5px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.76rem', cursor: 'pointer' }}>
          Continue anyway <ChevronRight size={12} />
        </button>
      </div>
    </div>
  )
}
