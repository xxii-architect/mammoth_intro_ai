import { useEffect, useState } from 'react'
import { hydrateRun } from '@mammothos/paths'
import { api } from '../api/client'
import { useAuth } from '../lib/authContext'
import RunTimeline from '../components/RunTimeline'

function RunReviewWorkspace() {
  const [runs, setRuns] = useState([])
  const [selected, setSelected] = useState('')
  const [snapshot, setSnapshot] = useState(null)
  const [run, setRun] = useState(null)
  const [listError, setListError] = useState('')
  const [detailError, setDetailError] = useState('')
  const [loadingList, setLoadingList] = useState(true)
  const [loadingRun, setLoadingRun] = useState(false)
  const [refresh, setRefresh] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoadingList(true)
    setListError('')
    api('/mammoth/runs', { signal: controller.signal }).then(payload => {
      if (controller.signal.aborted) return
      if (!Array.isArray(payload?.runs)) throw new Error('Backend returned an invalid saved-run list.')
      setRuns(payload.runs)
      setSelected(previous => payload.runs.some(item => item.id === previous) ? previous : payload.runs[0]?.id || '')
    }).catch(error => {
      if (controller.signal.aborted) return
      setRuns([])
      setSelected('')
      setListError(error.message)
    }).finally(() => {
      if (!controller.signal.aborted) setLoadingList(false)
    })
    return () => controller.abort()
  }, [refresh])

  useEffect(() => {
    const controller = new AbortController()
    setSnapshot(null)
    setRun(null)
    setDetailError('')
    setLoadingRun(Boolean(selected))
    if (selected) {
      api(`/mammoth/runs/${encodeURIComponent(selected)}`, { signal: controller.signal }).then(payload => {
        if (controller.signal.aborted) return
        if (payload?.run?.id !== selected) throw new Error('Saved run identity does not match the selection.')
        const recovered = hydrateRun(payload.run)
        setSnapshot(payload.run)
        setRun(recovered)
      }).catch(error => {
        if (!controller.signal.aborted) setDetailError(error.message)
      }).finally(() => {
        if (!controller.signal.aborted) setLoadingRun(false)
      })
    }
    return () => controller.abort()
  }, [selected, refresh])

  const exportSnapshot = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(snapshot, null, 2)], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.download = `${snapshot.id}-review.json`
    link.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  const current = run?.id === selected && !loadingList ? run : null
  return (
    <div className="page-enter" style={{ padding: 24, maxWidth: 1200, margin: '0 auto', width: '100%', minWidth: 0 }}>
      <header style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <h1>Run Review</h1>
        <button type="button" disabled={loadingList || loadingRun} onClick={() => setRefresh(value => value + 1)}>Refresh saved runs</button>
      </header>
      <p>Read-only saved evidence for your account. Refresh does not start a model call, continue work, approve tools or sync a repository.</p>
      {listError && <p role="alert">{listError}</p>}
      {loadingList ? <p role="status">Loading saved runs...</p> : !listError && runs.length === 0 ? <p>No saved runs yet.</p> : null}
      {runs.length > 0 && <label style={{ display: 'grid', gap: 8 }}>
        Saved run
        <select value={selected} onChange={event => setSelected(event.target.value)} style={{ width: '100%', minWidth: 0 }}>
          {runs.map(item => <option key={item.id} value={item.id}>{item.status} · {String(item.message || item.id).slice(0, 100)}</option>)}
        </select>
      </label>}
      {detailError && <p role="alert">{detailError}</p>}
      {loadingRun && <p role="status">Reading saved evidence...</p>}
      {current && <section aria-label="Saved run review" style={{ marginTop: 20, overflowWrap: 'anywhere' }}>
        <p><code>{current.id}</code> · Saved status: <strong>{current.status}</strong></p>
        <p>Saved approval and continuation state is historical until refreshed. Use Mammoth Mind to act; all backend access checks and approval expiry rules still apply.</p>
        <RunTimeline key={current.id} run={current} readOnly />
        {current.reply && <pre style={{ whiteSpace: 'pre-wrap', font: 'inherit' }}>{current.reply}</pre>}
        <details><summary>Recorded execution and check evidence</summary>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: '.78rem' }}>{JSON.stringify(current.progress, null, 2)}</pre>
        </details>
        <p>Downloads may contain prompts, source excerpts, tool arguments and logs. Review before sharing. They are saved receipts, not an independent correctness or security assessment.</p>
        <button type="button" onClick={exportSnapshot}>Download review JSON</button>
      </section>}
    </div>
  )
}

export default function RunReviewPage() {
  const { user, loading } = useAuth()
  if (loading) return <p role="status">Checking session...</p>
  if (!user?.id) return <p>Sign in to review your saved runs.</p>
  return <RunReviewWorkspace key={user.id} />
}
