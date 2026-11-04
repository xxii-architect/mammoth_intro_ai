import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

function githubRepository(value) {
  if (typeof value !== 'string') return null
  const slug = value.replace(/^https:\/\/github\.com\//, '').replace(/\.git$/, '')
  return /^[A-Za-z0-9][A-Za-z0-9-]*\/[A-Za-z0-9_.-]+$/.exec(slug)?.[0] === slug
    && !slug.split('/').some(part => part === '.' || part === '..') ? slug : null
}

export default function DesktopHandoff({ executionId }) {
  const [job, setJob] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [localBranch, setLocalBranch] = useState(false)
  const generation = useRef(0)
  useEffect(() => {
    generation.current += 1
    setJob(null)
    setError('')
    setBusy(false)
    setLocalBranch(false)
    return () => { generation.current += 1 }
  }, [executionId])
  const prepare = async () => {
    const request = ++generation.current
    setBusy(true)
    setError('')
    setJob(null)
    setLocalBranch(false)
    try {
      if (typeof executionId !== 'string' || executionId.length !== 29
          || !/^exec-[a-f0-9]{24}$/.test(executionId)) throw new Error('Invalid execution identity.')
      const result = await api(`/owner-executions/${encodeURIComponent(executionId)}`)
      const saved = result?.execution
      if (saved?.id !== executionId || saved.status !== 'validated'
          || saved.application?.status !== 'applied'
          || saved.application.branch !== `mammoth/owner/${executionId}`
          || typeof saved.application.commit_sha !== 'string'
          || ![40, 64].includes(saved.application.commit_sha.length)
          || !/^[a-f0-9]+$/.test(saved.application.commit_sha)
          || typeof saved.patch !== 'string' || !saved.patch) {
        throw new Error('Applied branch evidence is unavailable. Refresh the execution before handing off.')
      }
      if (request === generation.current) setJob(saved)
    } catch (cause) {
      if (request === generation.current) setError(cause.message || 'Could not load Desktop handoff.')
    } finally {
      if (request === generation.current) setBusy(false)
    }
  }
  const slug = githubRepository(job?.repo)
  const repository = slug && `https://github.com/${slug}`
  const desktop = repository && `x-github-client://openRepo/${repository}`
  const downloadPatch = () => {
    const url = URL.createObjectURL(new Blob([job.patch], { type: 'text/plain;charset=utf-8' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${executionId}.patch`
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return <section aria-label="GitHub Desktop handoff">
    <button type="button" disabled={busy} onClick={prepare}>
      {busy ? 'Loading applied branch…' : 'Prepare GitHub Desktop handoff (no push)'}
    </button>
    {error && <p role="alert">{error}</p>}
    {job && <>
      <p>Branch: <code>{job.application.branch}</code>. Commit: <code>{job.application.commit_sha}</code>.</p>
      <p>This branch was created on the Mammoth backend, not necessarily on this computer.
        Opening Desktop does not transfer unpublished work, push, merge or deploy.</p>
      <button type="button" onClick={downloadPatch}>Download approved patch</button>
      <p>The patch contains private source changes. Keep it private. A patch is not a Git bundle:
        it does not install the branch or preserve its commit identity.</p>
      {desktop ? <>
        <p><a href={desktop}>Open repository in GitHub Desktop</a>
          {' · '}<a href={repository} target="_blank" rel="noopener noreferrer">Open repository on GitHub</a></p>
        <label><input type="checkbox" checked={localBranch} onChange={event => setLocalBranch(event.target.checked)} />
          I have this branch in my local clone (or it is already published), and will check its commit in Desktop.
        </label>
        {localBranch && <p><a href={`${desktop}?branch=${encodeURIComponent(job.application.branch)}`}>Open prepared branch in GitHub Desktop</a></p>}
        <p>Desktop must be installed; your browser may ask permission to open it. If nothing opens,
          launch Desktop manually and choose the repository and branch. No successful launch is assumed.</p>
        <p>Review the diff and commit, then use Push origin / Publish branch and Create Pull Request in Desktop.
          Review checks and merge on GitHub. If Mammoth runs on a different computer and the branch is
          unpublished, it first needs an operator-assisted transfer; this button cannot fetch it from the backend.</p>
      </> : <p>No unambiguous GitHub repository was recorded. No Desktop or GitHub link is generated.
        Open the correct clone manually; Mammoth never selects a default repository.</p>}
    </>}
  </section>
}
