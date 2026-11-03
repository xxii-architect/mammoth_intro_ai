import { useState } from 'react'
import { api } from '../api/client'
import { downloadOutput } from './OutputActions'

export default function LearningPrivacy({ setPage }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

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
      <p>Export the active account's saved lessons, exercises, tutor/assistant conversations, study cards, linked notes and confirmed recovery draft. Unsaved tab edits, uploads, other accounts, standalone learner-model data, telemetry, Artifacts and Mammoth Mind threads are not included. This is not a full account archive or an atomic snapshot of concurrent edits.</p>
      <button type="button" disabled={busy} onClick={exportLearning}>{busy ? 'Preparing learning export...' : 'Export saved learning JSON'}</button>
      {error && <p role="alert">{error} No automatic retry was made.</p>}
      {notice && <p role="status">{notice}</p>}
      <p>Current retained windows: 80 lesson-history records, 120 study-aid records, 60 messages per tutor/assistant history, and one current recovery draft. These are count limits, not automatic age-based deletion. Previously trimmed records cannot be recovered by export.</p>
      <p>Model costs vary with provider, tokens, tools and retries; a reliable per-request price estimate is unavailable. Reading, restoring, exporting, and source-derived card previews make no model calls. Ask tutor, lesson/course generation and agent runs can use credits. A failed or interrupted request may already have incurred charges; do not retry automatically.</p>
      <p>Delete individual notes in Notes, remove uploads in the materials manager, and manage account-deletion requests in Account. Resetting progress is not a privacy wipe. A deletion request is not confirmation that all records, provider copies or backups have been erased. Downloaded exports must be managed on your device.</p>
      {setPage && <div>
        <button type="button" onClick={() => setPage('notes')}>Open Notes controls</button>
        <button type="button" onClick={() => setPage('account')}>Open Account controls</button>
      </div>}
    </div>
  </details>
}
