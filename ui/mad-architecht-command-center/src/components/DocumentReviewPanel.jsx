import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

export default function DocumentReviewPanel({ fileId, scope }) {
  const [review, setReview] = useState(null)
  const [goal, setGoal] = useState('')
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const generation = useRef(0)

  useEffect(() => {
    const request = ++generation.current
    api(`/mammoth/document-reviews?file_id=${encodeURIComponent(fileId)}&scope=${scope}`)
      .then(result => {
        if (!Array.isArray(result?.reviews)) throw new Error('Invalid saved reviews response.')
        if (request === generation.current) setReview(result.reviews[0] || null)
      })
      .catch(cause => { if (request === generation.current) setError(cause.message || 'Could not load saved review.') })
      .finally(() => { if (request === generation.current) setBusy(false) })
    return () => { generation.current += 1 }
  }, [fileId, scope])

  const change = async (action) => {
    const request = ++generation.current
    setBusy(true)
    setError('')
    try {
      const result = await action()
      if (!result?.review || !Array.isArray(result.review.assessments)) throw new Error('Invalid review response. Reload saved state before retrying.')
      if (request === generation.current) setReview(result.review)
    } catch (cause) {
      if (request === generation.current) setError(`${cause.message || 'Review request failed.'} Reload saved state before starting another batch.`)
    } finally {
      if (request === generation.current) setBusy(false)
    }
  }

  return <section aria-label="Indexed document review">
    <h4>Indexed document review</h4>
    <p>Explicit read-only assessment, not recursive critique. Each batch uses model credits for up to 3 sections. Opening saved progress is free of model calls. All indexed sections assessed does not mean the original file was fully extracted or facts verified.</p>
    {error && <p role="alert">{error}</p>}
    {!review && <form onSubmit={event => {
      event.preventDefault()
      change(() => api('/mammoth/document-reviews', { method: 'POST', body: { file_id: fileId, scope, goal } }))
    }}>
      <label>Review goal <input value={goal} onChange={event => setGoal(event.target.value)} maxLength={1000} required /></label>
      <button disabled={busy || !goal.trim()} type="submit">Create saved review (no model call)</button>
    </form>}
    {review && <>
      <p>{review.goal}</p>
      <p aria-label="Saved review coverage">{review.assessments.length}/{review.total_sections} indexed sections assessed · {review.status} · {review.usage?.tokens} reported tokens / {review.max_tokens} ceiling</p>
      {review.stop_reason && <p>Stop reason: {review.stop_reason}</p>}
      {review.warnings?.map(warning => <p key={warning}>{warning}</p>)}
      {['ready', 'partial'].includes(review.status) && !error && <button disabled={busy} onClick={() => change(() => api(`/mammoth/document-reviews/${encodeURIComponent(review.id)}/advance`, { method: 'POST', body: { confirm_model_usage: true } }))}>
        Review next batch (uses model credits)
      </button>}
      <button disabled={busy} onClick={() => change(() => api(`/mammoth/document-reviews/${encodeURIComponent(review.id)}`))}>Reload saved review (no model call)</button>
      <button disabled={busy} onClick={async () => {
        setBusy(true)
        const request = ++generation.current
        try {
          await api(`/mammoth/document-reviews/${encodeURIComponent(review.id)}`, { method: 'DELETE' })
          if (request === generation.current) { setReview(null); setError('') }
        } catch (cause) {
          if (request === generation.current) setError(cause.message || 'Could not delete review.')
        } finally { if (request === generation.current) setBusy(false) }
      }}>Delete saved review</button>
      {review.status === 'active' && <p>A batch is active or was interrupted. Reload to inspect progress; unknown provider calls are never automatically replayed.</p>}
      {review.status === 'blocked' && <p>This review cannot safely continue. Saved assessments remain available; the budget is not automatically extended.</p>}
      {review.assessments.map(item => <details key={item.chunk_index}>
        <summary>Section {item.chunk_index + 1} · {item.location}</summary>
        <p>{item.summary}</p><blockquote>{item.quote}</blockquote>
        <small>Model assessment; factual verification not performed.</small>
      </details>)}
    </>}
    {busy && <p role="status">Loading or reviewing bounded sections…</p>}
  </section>
}
