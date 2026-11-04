import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

export default function DocumentReviewPanel({ fileId, scope }) {
  const [review, setReview] = useState(null)
  const [goal, setGoal] = useState('')
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [budgetCeiling, setBudgetCeiling] = useState('')
  const generation = useRef(0)
  const synthesis = review?.synthesis
  const capStops = ['insufficient_call_allowance', 'reported_token_limit']
  const canExtend = review && review.status !== 'active' && review.inflight_section == null
    && (review.status !== 'blocked' || capStops.includes(review.stop_reason))
    && (synthesis?.status !== 'blocked' || capStops.includes(synthesis.stop_reason))
    && review.max_tokens < review.max_extended_tokens

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
      {review.review_complete && review.status === 'completed' && (!synthesis || synthesis.status === 'partial') && !error && <button disabled={busy} onClick={() => change(() => api(`/mammoth/document-reviews/${encodeURIComponent(review.id)}/synthesize`, { method: 'POST', body: { confirm_model_usage: true } }))}>
        Synthesize next batch (uses model credits)
      </button>}
      {synthesis && <section aria-label="Saved cross-section synthesis">
        <h5>Cross-section synthesis · {synthesis.status}</h5>
        <p>Combines saved assessments in bounded groups, not full-source rereads. Input traversal is not proof every claim is discussed or factually correct. Intermediate summaries can lose detail.</p>
        <p>A unit can include provider fallback attempts; failed-attempt charges may be unknown.</p>
        <p>Saved synthesis units: {(synthesis.levels || []).reduce((count, level) => count + level.length, 0) + (synthesis.nodes || []).length}</p>
        {synthesis.stop_reason && <p>Stop reason: {synthesis.stop_reason}</p>}
        {synthesis.status === 'completed' && synthesis.result && <>
          <p>{synthesis.result.summary}</p>
          <p>All {synthesis.result.section_indices.length} indexed assessments traversed. Citation links identify source sections, not verified entailment.</p>
          {synthesis.result.citations.map(index => {
            const source = review.assessments.find(item => item.chunk_index === index)
            return source && <details key={index}><summary>Source section {index + 1} · {source.location}</summary><blockquote>{source.quote}</blockquote></details>
          })}
        </>}
        {synthesis.status === 'blocked' && <p>Reload saved state. Only a known budget stop can be unlocked by an explicit extension; uncertain calls are never replayed.</p>}
      </section>}
      {canExtend && !error && <form onSubmit={event => {
        event.preventDefault()
        change(() => api(`/mammoth/document-reviews/${encodeURIComponent(review.id)}/budget`, {
          method: 'POST', body: { expected_max_tokens: review.max_tokens, max_tokens: Number(budgetCeiling), confirm_budget_extension: true },
        }))
      }}>
        <p>Raising the total ceiling permits more future model usage; it does not run models, reset usage, or unlock uncertain calls. Maximum: {review.max_extended_tokens} reported tokens. Each paid batch still needs its own click.</p>
        <label>New total token ceiling <input type="number" min={review.max_tokens + 1} max={review.max_extended_tokens} step="1" value={budgetCeiling} onChange={event => setBudgetCeiling(event.target.value)} required /></label>
        <button type="submit" disabled={busy || Number(budgetCeiling) <= review.max_tokens}>Confirm larger total ceiling (no model call)</button>
      </form>}
      {review.budget_extensions?.length > 0 && <details>
        <summary>Confirmed budget history</summary>
        <ul>{review.budget_extensions.map((item, index) => <li key={index}>
          {item.previous_max_tokens} → {item.max_tokens} total ceiling · {item.reported_tokens} reported tokens retained · {item.confirmed_at}
        </li>)}</ul>
      </details>}
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
      {review.status === 'blocked' && <p>This review is blocked. Saved assessments remain available. Only a known budget stop can be unlocked by an explicit ceiling extension; uncertain calls cannot.</p>}
      {review.assessments.map(item => <details key={item.chunk_index}>
        <summary>Section {item.chunk_index + 1} · {item.location}</summary>
        <p>{item.summary}</p><blockquote>{item.quote}</blockquote>
        <small>Model assessment; factual verification not performed.</small>
      </details>)}
    </>}
    {busy && <p role="status">Loading or reviewing bounded sections…</p>}
  </section>
}
