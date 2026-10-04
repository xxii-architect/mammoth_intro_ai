import { useState } from 'react'
import { ThumbsUp, ThumbsDown } from 'lucide-react'

export const FEEDBACK_REASONS = [
  ['incorrect', 'Incorrect'],
  ['incomplete', 'Incomplete'],
  ['off_topic', 'Off topic'],
  ['unsafe', 'Unsafe'],
  ['formatting', 'Formatting'],
  ['too_long', 'Too long'],
  ['other', 'Other'],
]

// Mirrors mammoth_os.message_feedback.message_key on the server.
export function messageFeedbackKey(entry) {
  const runId = entry?.run_id || entry?.run?.id
  if (runId) return `run:${runId}`
  if (entry?.created_at) return `ts:${entry.created_at}`
  return ''
}

export function isRateable(entry) {
  return Boolean(
    entry
    && entry.role !== 'user'
    && !entry.stream
    && entry.adapter !== 'mammoth-ui'
    && String(entry.message || '').trim()
    && messageFeedbackKey(entry),
  )
}

const chipStyle = (active, tone) => ({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 4,
  padding: '4px 7px',
  borderRadius: 8,
  border: `1px solid ${active ? tone : 'rgba(255,255,255,0.08)'}`,
  background: active ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.03)',
  color: active ? tone : 'var(--txt-mut)',
  fontSize: '0.66rem',
  cursor: 'pointer',
})

/**
 * Thumbs up/down for one assistant reply. A second click on the active thumb clears it.
 * Thumbs-down opens an optional reason + comment so the rating becomes a usable regression case.
 */
export default function MessageRating({ rating, onRate }) {
  const direction = rating?.direction || 'none'
  const [pending, setPending] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [reason, setReason] = useState(rating?.reason || '')
  const [comment, setComment] = useState(rating?.comment || '')
  const [error, setError] = useState('')
  const [sent, setSent] = useState(false)

  const submit = async (next, extra = {}) => {
    if (pending) return false
    setPending(true)
    setError('')
    try {
      await onRate(next, extra)
      return true
    } catch (err) {
      setError(err?.message || 'Could not save rating.')
      return false
    } finally {
      setPending(false)
    }
  }

  const clickThumb = async (next) => {
    const target = direction === next ? 'none' : next
    setSent(false)
    const ok = await submit(target)
    if (!ok) return
    setDetailOpen(target === 'down')
    if (target !== 'down') {
      setReason('')
      setComment('')
    }
  }

  const sendDetail = async () => {
    const ok = await submit('down', { reason, comment: comment.trim() })
    if (ok) {
      setSent(true)
      setDetailOpen(false)
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Good reply"
        aria-pressed={direction === 'up'}
        title="Good reply"
        disabled={pending}
        onClick={() => clickThumb('up')}
        style={chipStyle(direction === 'up', '#22c55e')}
      >
        <ThumbsUp size={11} fill={direction === 'up' ? 'currentColor' : 'none'} />
      </button>
      <button
        type="button"
        aria-label="Bad reply"
        aria-pressed={direction === 'down'}
        title="Bad reply"
        disabled={pending}
        onClick={() => clickThumb('down')}
        style={chipStyle(direction === 'down', '#f87171')}
      >
        <ThumbsDown size={11} fill={direction === 'down' ? 'currentColor' : 'none'} />
      </button>
      {direction === 'down' && !detailOpen && (
        <button
          type="button"
          onClick={() => {
            setReason(rating?.reason || '')
            setComment(rating?.comment || '')
            setDetailOpen(true)
          }}
          style={{ ...chipStyle(false), border: 'none', background: 'none', padding: '4px 2px' }}
        >
          {sent || rating?.reason ? 'Thanks · edit' : 'Add detail'}
        </button>
      )}
      {error && <span role="alert" title={error} style={{ fontSize: '0.66rem', color: '#f87171' }}>Couldn't save rating</span>}
      {detailOpen && direction === 'down' && (
        <div style={{ flexBasis: '100%', marginTop: 4, padding: '8px 10px', borderRadius: 10, border: '1px solid rgba(248,113,113,0.25)', background: 'rgba(248,113,113,0.05)', display: 'grid', gap: 7 }}>
          <div style={{ fontSize: '0.66rem', color: 'var(--txt-mut)' }}>What went wrong? (optional)</div>
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
            {FEEDBACK_REASONS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                aria-pressed={reason === value}
                onClick={() => setReason(reason === value ? '' : value)}
                style={chipStyle(reason === value, '#f87171')}
              >
                {label}
              </button>
            ))}
          </div>
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value.slice(0, 500))}
            placeholder="What would a better answer have done?"
            rows={2}
            style={{ width: '100%', resize: 'vertical', boxSizing: 'border-box', padding: '6px 8px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: 'var(--txt-pri)', fontSize: '0.78rem', fontFamily: 'inherit' }}
          />
          <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
            <button type="button" onClick={() => setDetailOpen(false)} style={chipStyle(false)}>Skip</button>
            <button type="button" disabled={pending} onClick={sendDetail} style={chipStyle(true, '#f87171')}>
              {pending ? 'Saving…' : 'Send'}
            </button>
          </div>
        </div>
      )}
    </>
  )
}
