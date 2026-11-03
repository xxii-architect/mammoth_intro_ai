import { useEffect, useState } from 'react'
import { api, authorizedFetch, parseApiResponse } from '../../api/client'
import { useAuth } from '../../lib/authContext'

export default function OwnerExecutionPanel({ repo }) {
  const { user, isGuest } = useAuth()
  if (!user || isGuest) return null
  return <ExecutionPanel key={`${user.id}:${repo}`} repo={repo} />
}

function ExecutionPanel({ repo = '' }) {
  const [capabilities, setCapabilities] = useState(null)
  const [changes, setChanges] = useState('[{"path":"example.py","content":""}]')
  const [profile, setProfile] = useState('python_unittest')
  const [acceptance, setAcceptance] = useState('')
  const [job, setJob] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [denied, setDenied] = useState(false)
  const [refresh, setRefresh] = useState(0)
  useEffect(() => {
    let alive = true
    authorizedFetch(`/owner-executions/capabilities?repo=${encodeURIComponent(repo)}`)
      .then(response => {
        if ([401, 403].includes(response.status)) { if (alive) setDenied(true); return null }
        return parseApiResponse(response)
      })
      .then(data => { if (alive) setCapabilities(data) })
      .catch(cause => { if (alive) setError(cause.message) })
    return () => { alive = false }
  }, [repo, refresh])
  const act = async operation => {
    setBusy(true)
    setError('')
    try {
      const result = await operation()
      if (!result?.execution?.id) throw new Error('Execution response was not valid.')
      setJob(result.execution)
    } catch (cause) { setError(cause.message || 'Owner execution failed.') }
    finally { setBusy(false) }
  }
  const ready = repo && capabilities?.enabled && capabilities?.isolation?.ready
  const profileAvailable = capabilities?.isolation?.profiles?.[profile] === true
  if (denied) return null
  return <details style={{ marginTop: 10, fontSize: '.76rem', overflowWrap: 'anywhere' }}>
    <summary>Owner isolated validation pilot</summary>
    <p>Disposable worktree and offline container checks. The selected checkout is never changed. Containers share the host kernel; no automatic merge or push.</p>
    {!repo && <p>Select a repository first. No default repository is used.</p>}
    <p>{capabilities?.isolation?.reason || 'Checking isolation availability...'}</p>
    {capabilities?.frontend_isolation && <p>Frontend image: {capabilities.frontend_isolation.reason}</p>}
    {capabilities?.isolation?.profile_reasons && <ul aria-label="Unavailable validation profiles">
      {Object.entries(capabilities.isolation.profile_reasons).map(([name, reason]) => <li key={name}>{name}: {reason}</li>)}
    </ul>}
    <button disabled={busy} onClick={() => { setCapabilities(null); setRefresh(value => value + 1) }}>Refresh isolation and HEAD</button>
    <p>Refresh rereads this backend checkout's committed HEAD and installed profiles. It does not fetch GitHub, switch branches, include uncommitted edits, or update your laptop. Connected repository clones must be synced separately.</p>
    {error && <p role="alert">{error}</p>}
    {ready && <>
      <p>Observed HEAD: <code>{capabilities.base_sha}</code></p>
      <label>Approved test profile
        <select value={profile} onChange={event => setProfile(event.target.value)} disabled={busy}>
          {capabilities.profiles.map(value => <option key={value} value={value} disabled={capabilities.isolation.profiles?.[value] !== true}>
            {value}{capabilities.isolation.profiles?.[value] !== true ? ' (unavailable)' : ''}
          </option>)}
        </select>
      </label>
      <p>Frontend availability checks the selected committed repository against reviewed image manifests, not coverage. The ui_* profiles target the MammothOS command-center workspace, not arbitrary Next/Vite apps. ui_build compiles the production UI. ui_component checks actual trust-row rendering, not browser interactions. ui_browser builds and runs the workspace browser suite in the offline locked image, with no skipped or flaky tests allowed. Browser phases are bounded to 10 minutes and 1024 MB; other frontend phases retain their existing limits.</p>
      <label style={{ display: 'block', marginTop: 8 }}>Proposal changes (JSON array: path with content, path with exact old/new edits, or path with delete:true)
        <textarea value={changes} onChange={event => setChanges(event.target.value)} rows={5} disabled={busy} style={{ width: '100%', boxSizing: 'border-box' }} />
      </label>
      <p>Exact edits must match once in the committed base, not uncommitted checkout text. Use content for new files. Deletion requires delete:true alone and an existing permitted base file; empty content empties a file, not deletes it. Testing and branch application still require separate approvals.</p>
      <label>Acceptance (JSON: expected_behavior and regression_tests arrays)
        <textarea value={acceptance} placeholder='{"expected_behavior":["Observable outcome"],"regression_tests":["tests/workspace-reliability.spec.js"]}' onChange={event => setAcceptance(event.target.value)} rows={3} disabled={busy} style={{ width: '100%', boxSizing: 'border-box' }} />
      </label>
      <p>UI JSX/TSX/CSS changes require observable expected behavior and an edit to a declared workspace browser regression-test file. Builds alone leave behavior not tested.</p>
      <button disabled={busy || !profileAvailable} onClick={() => act(() => api('/owner-executions', { method: 'POST', body: {
        repo_context: { root: repo }, base_sha: capabilities.base_sha, profile, changes: JSON.parse(changes),
        acceptance: acceptance.trim() ? JSON.parse(acceptance) : undefined,
      } }))}>Prepare proposal</button>
    </>}
    {job && <section aria-label="Owner execution evidence">
      <p>Execution {job.id}: <strong>{job.status}</strong></p>
      <p>Profile: {job.profile}. Base: {job.base_sha}. Approval expires: {new Date(job.expires_at * 1000).toLocaleString()}.</p>
      <p>Build: {job.validation_evidence?.build || 'not_tested'}. Behavior: {job.validation_evidence?.behavior || 'not_tested'}.</p>
      <p>{job.validation_evidence?.scope || 'Selected profile only; browser interactions not tested.'}</p>
      {job.acceptance?.expected_behavior?.length > 0 && <ul>{job.acceptance.expected_behavior.map((value, index) => <li key={index}>{value}</li>)}</ul>}
      {job.acceptance?.regression_tests?.length > 0 && <p>Declared regression tests: {job.acceptance.regression_tests.join(', ')}</p>}
      <pre style={{ whiteSpace: 'pre-wrap', maxHeight: 250, overflow: 'auto' }}>{job.patch}</pre>
      {job.status === 'pending_approval' && <button disabled={busy} onClick={() => act(() => api(`/owner-executions/${job.id}/approve`, {
        method: 'POST', body: { repo_context: { root: repo }, approval_digest: job.approval_digest },
      }))}>Approve isolated baseline and candidate checks</button>}
      {(['pending_approval', 'running'].includes(job.status) || busy) && <button onClick={async () => {
        try {
          const result = await api(`/owner-executions/${job.id}/cancel`, { method: 'POST' })
          if (!result?.execution?.id) throw new Error('Cancellation response was not valid.')
          setJob(result.execution)
        }
        catch (cause) { setError(cause.message) }
      }}>Cancel validation</button>}
      <button disabled={busy} onClick={() => act(() => api(`/owner-executions/${job.id}`))}>Refresh execution</button>
      {job.application?.status === 'ready' && <>
        <p>Second approval: create a commit on new local branch <code>{job.application.branch}</code>. This does not modify the selected checkout, push, merge or deploy.</p>
        <button disabled={busy} onClick={() => act(() => api(`/owner-executions/${job.id}/apply`, {
          method: 'POST', body: { repo_context: { root: repo }, approval_digest: job.application.approval_digest },
        }))}>Approve changes to new branch</button>
      </>}
      {job.application && <p>Branch application: <strong>{job.application.status}</strong>
        {job.application.commit_sha && <>. Commit: <code>{job.application.commit_sha}</code></>}
        {job.application.status === 'applied' && <>. Local branch: <code>{job.application.branch}</code>. Not pushed or deployed.</>}
      </p>}
      {job.application?.error && <p role="alert">{job.application.error}</p>}
      {job.error && <p role="alert">{job.error}</p>}
      {['baseline', 'candidate'].map(phase => job[phase] && <details key={phase}>
        <summary>{phase}: {job[phase].passed ? 'profile passed' : 'profile failed'} ({job[phase].duration_ms} ms)</summary>
        <pre style={{ whiteSpace: 'pre-wrap' }}>{job[phase].log}</pre>
        {job[phase].log_truncated && <p>Logs truncated at the bounded output limit.</p>}
      </details>)}
      <p>Passing a profile is not review approval or independent acceptance verification. Generated tests can be wrong. Review the patch and evidence before the separate branch-application approval.</p>
    </section>}
  </details>
}
