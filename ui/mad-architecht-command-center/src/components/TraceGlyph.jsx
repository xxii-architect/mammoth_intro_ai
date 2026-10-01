import { TRACE_KINDS, TONE_VARS } from '../design/traceVocabulary'

/**
 * A single trace glyph: icon + text label, never colour alone.
 * Use `compact` to show the icon only (the label stays available to assistive tech and as a tooltip).
 */
export default function TraceGlyph({ kind = 'tool', label, compact = false, size = 12 }) {
  const entry = TRACE_KINDS[kind] || TRACE_KINDS.tool
  const tone = TONE_VARS[entry.tone] || TONE_VARS.info
  const text = label || entry.label
  const { Icon } = entry
  return (
    <span
      className="mm-trace-glyph"
      data-kind={kind}
      title={text}
      aria-label={compact ? text : undefined}
      role={compact ? 'img' : undefined}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        padding: compact ? 3 : '2px 8px',
        borderRadius: 'var(--mm-radius-pill)',
        background: tone.bg, color: tone.fg,
        fontSize: '0.68rem', fontWeight: 600, letterSpacing: '0.02em', lineHeight: 1.3,
        whiteSpace: 'nowrap',
      }}
    >
      <Icon size={size} aria-hidden="true" />
      {!compact && <span>{text}</span>}
    </span>
  )
}
