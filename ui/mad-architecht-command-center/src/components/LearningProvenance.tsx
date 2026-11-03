function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

export default function LearningProvenance({ context }: { context?: unknown }) {
  if (!isRecord(context) || context.contract !== 'mammoth.learning-selection.v1') return null
  const text = (key: string) => typeof context[key] === 'string' ? context[key] : ''
  const links = Array.isArray(context.source_urls) ? context.source_urls.filter((value): value is string =>
    typeof value === 'string' && /^https?:\/\//i.test(value)) : []
  return <details style={{ marginTop: 10, fontSize: '.76rem', color: 'var(--txt-sec)', overflowWrap: 'anywhere' }}>
    <summary style={{ minHeight: 44, paddingTop: 8, boxSizing: 'border-box', cursor: 'pointer' }}>Lesson provenance (not fact verification)</summary>
    <p>{text('lesson_title')} · {text('source')}{text('section') ? ` · ${text('section')}` : ''}</p>
    <p>Authorship: {text('authorship') || 'Unspecified'} · Lesson: {text('lesson_id')}</p>
    <blockquote style={{ margin: '8px 0', whiteSpace: 'pre-wrap' }}>{text('quote')}</blockquote>
    {links.length > 0 && <ul aria-label="Recorded lesson source links">{links.map(url =>
      <li key={url}><a href={url} target="_blank" rel="noopener noreferrer">{url}</a></li>)}</ul>}
  </details>
}
