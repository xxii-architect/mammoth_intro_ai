import { useEffect, useState } from 'react'
import { api } from '../api/client'

export default function OwnerExecutionReview({ approval, onReady }) {
  const [job, setJob] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    onReady(false)
    setJob(null)
    setError('')
    const load = async () => {
      try {
        const id = approval.args?.execution_id
        if (!/^exec-[a-f0-9]{24}$/.test(id || '')) throw new Error('Invalid execution identity.')
        const result = await api(`/owner-executions/${encodeURIComponent(id)}`)
        const execution = result?.execution
        const apply = approval.tool === 'owner_execution_apply'
        const permission = apply ? execution?.application : execution
        if (execution?.id !== id || !execution.patch || permission?.approval_digest !== approval.args.approval_digest ||
            permission?.status !== (apply ? 'ready' : 'pending_approval') ||
            !Number.isFinite(permission.expires_at) || permission.expires_at * 1000 <= Date.now() ||
            (apply && (execution.status !== 'validated' || execution.candidate?.passed !== true || execution.regression === true))) {
          throw new Error('Approval no longer matches an available execution. Reject and prepare a new proposal.')
        }
        if (active) { setJob(execution); onReady(true) }
      } catch (cause) {
        if (active) setError(cause.message || 'Execution evidence unavailable.')
      }
    }
    load()
    return () => { active = false }
  }, [approval, onReady])
  return <section aria-label="Owner approval evidence" style={{ minWidth: 0, overflowWrap: 'anywhere' }}>
    {!job && !error && <p>Loading recorded patch and approval evidence...</p>}
    {error && <p role="alert">{error}</p>}
    {job && <>
      <p>Repository: {job.repo}. Base: <code>{job.base_sha}</code></p>
      {approval.tool === 'owner_execution_apply'
        ? <p>Approve a commit on new local branch <code>{job.application.branch}</code>. Your selected checkout, remote and production deployment stay unchanged. No push or merge.</p>
        : <p>Approve isolated baseline/candidate checks only. This does not apply changes.</p>}
      <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 300, overflow: 'auto' }}>{job.patch}</pre>
      {['baseline', 'candidate'].map(phase => job[phase] && <details key={phase}>
        <summary>{phase}: {job[phase].passed ? 'profile passed' : 'profile failed'}</summary>
        <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 200, overflow: 'auto' }}>{job[phase].log}</pre>
        {job[phase].log_truncated && <p>Recorded output was truncated.</p>}
      </details>)}
      <p>Test success is not independent correctness certification. Review changes before approving.</p>
    </>}
  </section>
}
