import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { decodeOwnerBranchExport } from '@mammothos/paths'

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
  const [exportReceipt, setExportReceipt] = useState(null)
  const generation = useRef(0)
  useEffect(() => {
    generation.current += 1
    setJob(null)
    setError('')
    setBusy(false)
    setLocalBranch(false)
    setExportReceipt(null)
    return () => { generation.current += 1 }
  }, [executionId])
  const prepare = async () => {
    const request = ++generation.current
    setBusy(true)
    setError('')
    setJob(null)
    setLocalBranch(false)
    setExportReceipt(null)
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
  const exportBranch = async () => {
    const request = ++generation.current
    setBusy(true)
    setError('')
    setExportReceipt(null)
    try {
      const result = await api(`/owner-executions/${encodeURIComponent(executionId)}/export`, {
        method: 'POST', body: { repo_context: { root: job.repo },
          expected_commit: job.application.commit_sha, confirm_private_export: true },
      })
      const receipt = result?.export
      const bytes = await decodeOwnerBranchExport(receipt, { executionId, expectedCommit: job.application.commit_sha })
      if (receipt.base_sha !== job.base_sha || receipt.repo !== job.repo) throw new Error('Export source does not match the recorded application.')
      if (request !== generation.current) return
      const url = URL.createObjectURL(new Blob([bytes], { type: 'application/octet-stream' }))
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = receipt.filename
      anchor.click()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
      setExportReceipt(receipt)
    } catch (cause) {
      if (request === generation.current) setError(cause.message || 'Branch export failed. No automatic retry.')
    } finally {
      if (request === generation.current) setBusy(false)
    }
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
      <button type="button" disabled={busy} onClick={exportBranch}>Confirm private branch bundle download (no push)</button>
      <p>The bundle preserves the applied commit, not the full repository. It requires the exact base
        <code> {job.base_sha}</code> in your local clone. It contains private source. Downloading does not import it or run code.</p>
      {exportReceipt && <details open>
        <summary>Verify and import the downloaded bundle</summary>
        <p>SHA-256: <code>{exportReceipt.sha256}</code>. {exportReceipt.size_bytes} bytes.
          Transport checksum verified; not a signature or independent code review.</p>
        <p>In the correct existing clone, a Git-capable tool/operator must verify prerequisites and create
          the new branch. These commands do not execute here; replace the download path. They do not
          switch your current checkout or push. Do not force an existing branch.</p>
        <pre style={{ whiteSpace: 'pre-wrap' }}>{`git bundle verify "<download-path>/${exportReceipt.filename}"\ngit fetch --no-tags "<download-path>/${exportReceipt.filename}" "refs/heads/${exportReceipt.branch}:refs/heads/${exportReceipt.branch}"\ngit rev-parse --verify "refs/heads/${exportReceipt.branch}"`}</pre>
        <p>Compare the last output to <code>{exportReceipt.commit_sha}</code>, then select the branch in Desktop.
          If the base is missing, sync the correct repository first. GitHub Desktop does not directly import bundles;
          fully terminal-free import still needs a local helper.</p>
      </details>}
      {desktop ? <>
        <p><a href={desktop}>Open repository in GitHub Desktop</a>
          {' · '}<a href={repository} target="_blank" rel="noopener noreferrer">Open repository on GitHub</a></p>
        <p><a href={`${repository}/tree/${encodeURIComponent(job.application.branch)}`} target="_blank" rel="noopener noreferrer">
          View approved branch on GitHub (after publishing)
        </a></p>
        <p>This website fallback does not publish the branch. GitHub may show “not found” until you push it
          and sign into an account with repository access.</p>
        <label><input type="checkbox" checked={localBranch} onChange={event => setLocalBranch(event.target.checked)} />
          I have this branch in my local clone (or it is already published), and will check its commit in Desktop.
        </label>
        {localBranch && <p><a href={`${desktop}?branch=${encodeURIComponent(job.application.branch)}`}>Open prepared branch in GitHub Desktop</a></p>}
        <p>Desktop must be installed; your browser may ask permission to open it. If nothing opens,
          launch Desktop manually and choose the repository and branch. No successful launch is assumed.</p>
        <p>Review the diff and commit, then use Push origin / Publish branch and Create Pull Request in Desktop.
          Review checks and merge on GitHub. If Mammoth runs on a different computer and the branch is
          unpublished, download and import the verified bundle first; this launch link alone cannot transfer it.</p>
      </> : <p>No unambiguous GitHub repository was recorded. No Desktop or GitHub link is generated.
        Open the correct clone manually; Mammoth never selects a default repository.</p>}
    </>}
  </section>
}
