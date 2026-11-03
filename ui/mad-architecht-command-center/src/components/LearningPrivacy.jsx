import { useState } from 'react'
import { api } from '../api/client'
import { downloadOutput } from './OutputActions'

export default function LearningPrivacy({ setPage, onDeleted, onAdaptationDeleted }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [controls, setControls] = useState(null)
  const [limit, setLimit] = useState('')
  const [preview, setPreview] = useState(null)
  const [confirmation, setConfirmation] = useState('')
  const [adaptationReview, setAdaptationReview] = useState(null)
  const [adaptationPreview, setAdaptationPreview] = useState(null)
  const [adaptationConfirmation, setAdaptationConfirmation] = useState('')

  const action = async handler => {
    if (busy) return
    setBusy(true)
    setError('')
    setNotice('')
    try { await handler() }
    catch (cause) { setError(cause.message || 'Learning controls failed. No automatic retry was made.') }
    finally { setBusy(false) }
  }

  const loadControls = async () => {
    const result = await api('/atlas/controls')
    if (result?.contract !== 'mammoth.learning-controls.v1' || !Array.isArray(result.operations)) {
      throw new Error('The server did not confirm learning controls.')
    }
    setControls(result)
    setLimit(result.daily_request_limit === null ? '' : String(result.daily_request_limit))
  }

  const exportLearning = async () => {
    if (busy) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      const result = await api('/atlas/export', { method: 'POST' })
      if (result?.contract !== 'mammoth.learning-export.v1' || !result.saved_learning || !result.workspace_recovery) {
        throw new Error('The server did not confirm a learning export.')
      }
      downloadOutput(result, 'mammoth-learning-export', 'json')
      setNotice('Export prepared; check your browser downloads. The file contains private learning content.')
    } catch (cause) {
      setError(cause.message || 'Learning export failed. No automatic retry was made.')
    } finally { setBusy(false) }
  }

  return <details className="atlas-learning-privacy">
    <summary>Learning privacy &amp; costs</summary>
    <div>
      <p>Export the active account's saved lessons, exercises, tutor/assistant conversations, study cards, linked notes, confirmed recovery draft and saved private learner adaptation (onboarding, mastery/confidence, error patterns and memory graph). Missing adaptation is marked not saved, not invented. Unsaved tab edits, uploads, other accounts, unverified legacy models, unknown learner extension fields, telemetry, Artifacts and Mammoth Mind threads are not included. This is not a full account archive or an atomic snapshot of concurrent edits.</p>
      <button type="button" disabled={busy} onClick={exportLearning}>{busy ? 'Preparing learning export...' : 'Export saved learning JSON'}</button>
      {error && <p role="alert">{error} No automatic retry was made.</p>}
      {notice && <p role="status">{notice}</p>}
      <p>Current retained windows: 80 lesson-history records, 120 study-aid records, 60 messages per tutor/assistant history, and one current recovery draft. These are count limits, not automatic age-based deletion. Previously trimmed records cannot be recovered by export.</p>
      <p>New learner adaptation is stored separately for each signed-in user and learning account. Legacy shared models are left untouched and are not automatically imported. Saved-learning export includes the current private model's supported fields without generating or trimming saved history. Standalone adaptation is still outside saved-learning deletion; exporting it does not erase it.</p>
      <button type="button" disabled={busy} onClick={() => action(async () => {
        setAdaptationReview(null)
        const result = await api('/atlas/learner/privacy-review')
        if (result?.contract !== 'mammoth.learner-privacy-review.v1' || result.review_only !== true ||
            result.deletion_available !== false || !Array.isArray(result.saved_fields) ||
            !Array.isArray(result.retained_outside_scope) ||
            typeof result.account_id !== 'string' || !result.account_id ||
            [...result.saved_fields, ...result.retained_outside_scope].some(field => typeof field !== 'string') ||
            !['saved', 'not_saved'].includes(result.model_status)) {
          throw new Error('The server did not confirm a read-only adaptation review.')
        }
        const counts = result.saved_record_counts
        if ((result.model_status === 'not_saved' && (counts !== null || result.saved_fields.length !== 0)) ||
            (result.model_status === 'saved' && (!counts || [
          'mastery_concepts', 'confidence_concepts', 'error_patterns',
          'retained_outcomes', 'memory_nodes', 'memory_edges',
        ].some(key => !Number.isInteger(counts[key]) || counts[key] < 0)))) {
          throw new Error('The server did not confirm saved adaptation counts.')
        }
        setAdaptationReview(result)
      })}>Review private adaptation deletion scope</button>
      {adaptationReview && <section aria-label="Private adaptation scope review">
        <p>Account: {adaptationReview.account_id}. {adaptationReview.model_status === 'saved' ? 'A private adaptation record is saved.' : 'No private adaptation record is saved; no default was created.'}</p>
        {adaptationReview.pending_deletion && <p role="status">Private adaptation deletion is incomplete. This is a read-only review of the remaining saved record, not a deletion receipt.</p>}
        {adaptationReview.model_status === 'saved' && <>
          <p>Saved fields: {adaptationReview.saved_fields.map(field => field.replaceAll('_', ' ')).join(', ')}.</p>
          <p>{adaptationReview.saved_record_counts.mastery_concepts} mastery concepts; {adaptationReview.saved_record_counts.confidence_concepts} confidence concepts; {adaptationReview.saved_record_counts.error_patterns} error patterns; {adaptationReview.saved_record_counts.retained_outcomes} retained outcomes; {adaptationReview.saved_record_counts.memory_nodes} memory nodes; {adaptationReview.saved_record_counts.memory_edges} memory edges. Counts describe saved records, not verified understanding.</p>
        </>}
        <p>Review only. No data was deleted and no deletion receipt was issued. Deletion requires the separate preview and exact confirmation below. Use Export saved learning JSON to keep a copy.</p>
        <p>Outside this review: {adaptationReview.retained_outside_scope.map(field => field.replaceAll('_', ' ')).join(', ')}. This list is not a future erasure promise. Legacy ownership is unverified; no legacy model was imported. This is not a full account inventory or an atomic snapshot of concurrent edits.</p>
      </section>}
      <button type="button" disabled={busy} onClick={() => action(async () => {
        setAdaptationPreview(null)
        setAdaptationConfirmation('')
        const result = await api('/atlas/learner/deletion-preview')
        if (result?.contract !== 'mammoth.learner-erasure.v1' ||
            result.scope !== 'active_account_private_model_and_adaptation_caches' ||
            typeof result.account_id !== 'string' || !result.account_id ||
            typeof result.preview_token !== 'string' || !/^[a-f0-9]{64}$/.test(result.preview_token) ||
            typeof result.deletion_available !== 'boolean' || !Array.isArray(result.excludes) ||
            result.excludes.some(field => typeof field !== 'string')) {
          throw new Error('The server did not confirm a private adaptation deletion preview.')
        }
        setAdaptationPreview(result)
      })}>Preview private adaptation deletion</button>
      {adaptationPreview && <section aria-label="Private adaptation deletion">
        <p>Delete account {adaptationPreview.account_id}'s saved private model (onboarding preferences/goals, mastery/confidence, errors, outcomes and memory graph) and its learner model/context/profile/storage caches. Lessons, conversations and exercise drafts are preserved, including previously generated content that may reflect old adaptation.</p>
        <p>NOT deleted: {adaptationPreview.excludes.map(field => field.replaceAll('_', ' ')).join(', ')}. Cancellation is requested for tracked Learning requests in this account; already-sent provider work may finish and bill. Older hosted model/state writes are rejected, but other tabs and downloads cannot be erased. Reload other tabs. New deliberate activity can create fresh adaptation.</p>
        {adaptationPreview.pending_deletion && <p role="status">A previous deletion is incomplete. Adaptation hydration and writes are blocked until deletion succeeds; read-only export and review remain available. Review this scope before retrying.</p>}
        {!adaptationPreview.deletion_available ? <p role="alert">Unknown model extensions require review. Deletion is unavailable; no data was removed.</p> : <>
          <label>Type DELETE PRIVATE ADAPTATION to confirm
            <input value={adaptationConfirmation} disabled={busy} autoComplete="off" onChange={event => setAdaptationConfirmation(event.target.value)} />
          </label>
          <button type="button" disabled={busy || adaptationConfirmation !== 'DELETE PRIVATE ADAPTATION'} onClick={() => action(async () => {
            const reviewed = adaptationPreview
            setAdaptationPreview(null)
            setAdaptationConfirmation('')
            const result = await api('/atlas/learner/adaptation', { method: 'DELETE', body: {
              confirmation: adaptationConfirmation, preview_token: reviewed.preview_token,
            } })
            if (result?.contract !== 'mammoth.learner-erasure.v1' ||
                result.scope !== reviewed.scope || result.account_id !== reviewed.account_id ||
                result.status !== 'deleted_from_active_storage' ||
                typeof result.receipt_id !== 'string' || !/^[a-f0-9]{32}$/.test(result.receipt_id)) {
              throw new Error('The server did not confirm private adaptation deletion. Reload the preview before retrying.')
            }
            setAdaptationReview(null)
            setControls(null)
            setPreview(null)
            setConfirmation('')
            await onAdaptationDeleted?.(result)
          })}>Delete private adaptation</button>
        </>}
      </section>}
      <p>Model costs vary with provider, tokens, tools and retries; a reliable per-request price estimate is unavailable. Reading, restoring, exporting, and source-derived card previews make no model calls. Ask tutor, lesson/course generation and agent runs can use credits. A failed or interrupted request may already have incurred charges; do not retry automatically.</p>
      <button type="button" disabled={busy} onClick={() => action(loadControls)}>Refresh learning request controls</button>
      {controls && <section aria-label="Learning request controls">
        <p>{controls.admitted_requests} admitted requests on {controls.day_utc} (UTC). These count HTTP requests, not model calls, tokens or dollars. Failed, guarded, gated and cancelled requests count too; changing the limit does not reset usage.</p>
        <label>Daily ATLAS request cap (blank means uncapped)
          <input type="number" min="0" max="100000" step="1" value={limit} disabled={busy} onChange={event => setLimit(event.target.value)} />
        </label>
        <button type="button" disabled={busy} onClick={() => action(async () => {
          const value = limit === '' ? null : Number(limit)
          if (value !== null && (!Number.isInteger(value) || value < 0 || value > 100000)) throw new Error('Choose a whole number from 0 to 100000, or leave blank.')
          const result = await api('/atlas/controls', { method: 'PUT', body: { daily_request_limit: value } })
          if (result?.contract !== 'mammoth.learning-controls.v1') throw new Error('The server did not confirm the cap.')
          setControls(result)
          setNotice('Learning request cap saved. Existing requests are not cancelled.')
        })}>Save learning request cap</button>
        <p>The opt-in cap covers lesson creation, submissions, next exercises, saved-course activation, regeneration, tutor/assistant chat, ATLAS plans, the direct ATLAS agent route and non-streaming Learning-panel agent requests. General workspace runs, repository/tool-loop runs, SDK/local calls and Mammoth Mind are outside this cap. This is not a platform-wide spending limit. Zero pauses covered routes; blank preserves uncapped behavior.</p>
        <p>Cancellation is cooperative: it stops at the next checked model/save boundary, not necessarily immediately. Already-sent provider work may finish and be billed; completed side effects are not undone. A running record after a server interruption is not proof the provider is still running. Refresh to check the latest recorded state.</p>
        <ul>{controls.operations.map(operation => <li key={operation.id}>
          {operation.route} · {operation.account_id} · {operation.status}
          {operation.status === 'running' && <button type="button" disabled={busy} onClick={() => action(async () => {
            const result = await api(`/atlas/operations/${encodeURIComponent(operation.id)}/cancel`, { method: 'POST' })
            if (!result?.status) throw new Error('The server did not confirm the cancellation request.')
            setNotice(`Request state: ${result.status}. Provider work may continue until a safe boundary.`)
            await loadControls()
          })}>Request cancellation {operation.id.slice(0, 8)}</button>}
        </li>)}</ul>
      </section>}
      {onDeleted && <section aria-label="Delete saved lesson session">
        <p>Delete only this active account's saved lesson session: lessons/exercises, tutor and assistant chats, lesson history, study cards and recovery draft. This is separate from resetting progress. Export first if needed.</p>
        <button type="button" disabled={busy} onClick={() => action(async () => {
          setPreview(null)
          setConfirmation('')
          const result = await api('/atlas/history/preview')
          if (result?.contract !== 'mammoth.learning-erasure.v1' || !result.preview_token || !Array.isArray(result.excludes)) throw new Error('The server did not confirm a deletion preview.')
          setPreview(result)
        })}>Preview saved learning deletion</button>
        {preview && <div>
          <p>Account: {preview.account_id}. NOT deleted: {preview.excludes.join(', ')}. Cancellation is requested for this account's tracked requests. Other tabs and downloaded copies must be cleared separately.</p>
          <label>Type DELETE SAVED LEARNING to confirm<input value={confirmation} disabled={busy} autoComplete="off" onChange={event => setConfirmation(event.target.value)} /></label>
          <button className="atlas-learning-delete" type="button" disabled={busy || confirmation !== 'DELETE SAVED LEARNING'} onClick={() => action(async () => {
            const result = await api('/atlas/history', { method: 'DELETE', body: { confirmation, preview_token: preview.preview_token } })
            if (result?.status !== 'deleted_from_active_storage' || !result.receipt_id) throw new Error('Deletion was not confirmed. Reload the preview before retrying.')
            onDeleted(result)
          })}>Delete saved lesson session</button>
        </div>}
      </section>}
      <p>Delete individual notes in Notes, remove uploads in the materials manager, and manage account-deletion requests in Account. Resetting progress is not a privacy wipe. A deletion request is not confirmation that all records, provider copies or backups have been erased. Downloaded exports must be managed on your device.</p>
      {setPage && <div>
        <button type="button" onClick={() => setPage('notes')}>Open Notes controls</button>
        <button type="button" onClick={() => setPage('account')}>Open Account controls</button>
      </div>}
    </div>
  </details>
}
