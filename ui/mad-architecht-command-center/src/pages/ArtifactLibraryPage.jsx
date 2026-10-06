import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, authorizedFetch } from '../api/client'
import { useAuth } from '../lib/authContext'
import CurriculumArtifactPanel from '../components/CurriculumArtifactPanel'
import './artifact-library.css'

const STATUS_LABELS = { ready: 'Ready', draft: 'Draft / needs review', failed: 'Failed', unknown: 'Not assessed' }
const PAGE_LABELS = { atlas: 'ATLAS', agent: 'Agent workspace', chat: 'Mammoth Mind', notes: 'Notes', flashcards: 'Flashcards', lessonnotes: 'Lesson notes', taskinbox: 'Task Inbox', artifacts: 'Artifacts' }

function formatStamp(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? 'Date unavailable' : date.toLocaleString()
}

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export default function ArtifactLibraryPage({ setPage }) {
  const { user, loading, isGuest } = useAuth()
  if (loading) return <p role="status">Loading your account...</p>
  if (!user || isGuest) return <p role="status">Sign in to view your private artifact library.</p>
  return <ArtifactLibrary key={user.id} setPage={setPage} />
}

function ArtifactLibrary({ setPage }) {
  const [outputs, setOutputs] = useState([])
  const [courses, setCourses] = useState([])
  const [categories, setCategories] = useState([])
  const [loadErrors, setLoadErrors] = useState([])
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('all')
  const [agent, setAgent] = useState('all')
  const [status, setStatus] = useState('all')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const generation = useRef(0)

  const load = useCallback(async () => {
    const current = ++generation.current
    setLoading(true)
    const results = await Promise.allSettled([
      api('/workspace/artifacts').then(data => {
        if (!Array.isArray(data?.artifacts) || !Array.isArray(data?.categories)) throw new Error('Artifact index returned an invalid response.')
        return data
      }),
      api('/atlas/curricula').then(data => {
        if (!Array.isArray(data?.curricula)) throw new Error('Curriculum library returned an invalid response.')
        return data.curricula
      }),
    ])
    if (current !== generation.current) return
    const errors = []
    if (results[0].status === 'fulfilled') {
      setOutputs(results[0].value.artifacts)
      setCategories(results[0].value.categories)
    } else errors.push(`Saved outputs: ${results[0].reason.message}`)
    if (results[1].status === 'fulfilled') setCourses(results[1].value)
    else errors.push(`Curricula: ${results[1].reason.message}`)
    setLoadErrors(errors)
    setLoading(false)
  }, [])

  useEffect(() => {
    load()
    return () => { generation.current += 1 }
  }, [load])

  const items = useMemo(() => [
    ...outputs.map(item => ({ ...item, key: `output:${item.id}` })),
    ...courses.map(record => ({
      key: `curriculum:${record.curriculum.curriculum_id}`,
      id: record.curriculum.curriculum_id, curriculum: record.curriculum,
      title: record.curriculum.title || record.curriculum.subject,
      summary: record.curriculum.subject, created_at: record.saved_at, searchText: JSON.stringify(record.curriculum),
      category: 'curricula', artifact_status: record.curriculum.quality?.ready === true ? 'ready' : 'draft',
      agent_id: '', source: 'ATLAS curriculum library', origin: { page: 'atlas', curriculum_id: record.curriculum.curriculum_id },
      format: 'json',
    })),
  ].sort((a, b) => (Date.parse(b.created_at) || 0) - (Date.parse(a.created_at) || 0)), [outputs, courses])
  const agentIds = useMemo(() => [...new Set(items.map(item => item.agent_id).filter(Boolean))].sort(), [items])
  const dateError = from && to && from > to ? 'Start date must be on or before end date.' : ''
  const filtered = useMemo(() => items.filter(item => {
    const text = [item.title, item.summary, item.body, item.searchText, item.source, item.agent_id].filter(Boolean).join(' ').toLowerCase()
    const date = new Date(item.created_at)
    const lower = from ? new Date(`${from}T00:00:00`).getTime() : -Infinity
    const upper = to ? new Date(`${to}T23:59:59.999`).getTime() : Infinity
    return (!query.trim() || text.includes(query.trim().toLowerCase()))
      && (category === 'all' || item.category === category)
      && (agent === 'all' || (agent === 'unattributed' ? !item.agent_id : item.agent_id === agent))
      && (status === 'all' || item.artifact_status === status)
      && (!from && !to || !Number.isNaN(date.getTime()) && date.getTime() >= lower && date.getTime() <= upper)
  }), [items, query, category, agent, status, from, to])

  const action = async operation => {
    setBusy(true)
    setActionError('')
    setNotice('')
    try { await operation() }
    catch (cause) { setActionError(cause.message || 'Artifact operation failed.') }
    finally { setBusy(false) }
  }
  const remove = async () => {
    const target = confirmDelete
    await action(async () => {
      if (target === 'all') {
        await api('/workspace/artifacts', { method: 'DELETE' })
        setOutputs([])
        setNotice('Saved outputs cleared. Your curricula, notes, and flashcards were not deleted.')
      } else {
        await api(`/workspace/artifacts/${encodeURIComponent(target)}`, { method: 'DELETE' })
        setOutputs(previous => previous.filter(item => item.id !== target))
        setNotice('Artifact removed.')
      }
      setConfirmDelete(null)
    })
  }
  const download = item => action(async () => {
    if (item.curriculum) {
      saveBlob(new Blob([JSON.stringify(item.curriculum, null, 2)], { type: 'application/json' }), 'atlas-curriculum.json')
    } else {
      const extension = item.format === 'md' ? 'md' : 'txt'
      const name = (item.title || 'artifact').replace(/[^a-z0-9_-]+/gi, '-').slice(0, 80)
      saveBlob(new Blob([item.body], { type: 'text/plain;charset=utf-8' }), `${name}.${extension}`)
    }
  })
  const downloadDocx = item => action(async () => {
    const response = await authorizedFetch(`/download-docx/${encodeURIComponent(item.docx_filename)}`)
    if (!response.ok) throw new Error(`Document download failed (${response.status}). It may have expired or be unavailable to your account.`)
    saveBlob(await response.blob(), item.docx_filename)
  })

  return (
    <div className="artifact-library page-enter">
      <header>
        <div>
          <h1>Artifact library</h1>
          <p>Your saved outputs and ATLAS curricula. Categories organize content; they do not certify accuracy, mastery, or code safety.</p>
        </div>
        <div className="artifact-actions">
          <button onClick={load} disabled={busy || loading}>Refresh library</button>
          <button onClick={() => setConfirmDelete('all')} disabled={busy || loading || !outputs.length}>Clear saved outputs</button>
        </div>
      </header>
      {loadErrors.map(error => <p key={error} role="alert">{error} Use Refresh library to retry. Previously loaded items may be stale.</p>)}
      {actionError && <p role="alert">{actionError}</p>}
      {notice && <p role="status">{notice}</p>}
      {confirmDelete && <section aria-label="Confirm removal" className="glass-card-solid artifact-confirm">
        <p>{confirmDelete === 'all' ? 'Delete all saved outputs? This cannot be undone. ATLAS curricula and the Notes and Flashcards libraries are not affected.' : 'Remove this saved output? This cannot be undone.'}</p>
        <button onClick={remove} disabled={busy}>Confirm removal</button>
        <button onClick={() => setConfirmDelete(null)} disabled={busy}>Cancel</button>
      </section>}
      <nav aria-label="Artifact categories" className="artifact-actions">
        <button aria-pressed={category === 'all'} onClick={() => setCategory('all')}>All ({items.length})</button>
        {categories.map(type => <button key={type.id} aria-pressed={category === type.id} onClick={() => setCategory(type.id)}>
          {type.label} ({items.filter(item => item.category === type.id).length})
        </button>)}
      </nav>
      <section aria-label="Artifact filters" className="artifact-filters">
        <label>Search artifacts<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Title, content, source..." /></label>
        <label>Agent<select value={agent} onChange={event => setAgent(event.target.value)}>
          <option value="all">All agents</option><option value="unattributed">Not recorded</option>
          {agentIds.map(id => <option key={id} value={id}>{id}</option>)}
        </select></label>
        <label>Status<select value={status} onChange={event => setStatus(event.target.value)}>
          <option value="all">All statuses</option>
          {Object.entries(STATUS_LABELS).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
        </select></label>
        <label>From date<input type="date" value={from} onChange={event => setFrom(event.target.value)} /></label>
        <label>To date<input type="date" value={to} onChange={event => setTo(event.target.value)} /></label>
        <button onClick={() => { setQuery(''); setCategory('all'); setAgent('all'); setStatus('all'); setFrom(''); setTo('') }}>Reset filters</button>
      </section>
      {dateError && <p role="alert">{dateError}</p>}
      {loading && <p role="status">Loading your library...</p>}
      {!loading && <p role="status">{filtered.length} of {items.length} artifacts shown</p>}
      {!loading && !filtered.length && <p>{items.length ? 'No artifacts match these filters.' : loadErrors.length ? 'Your library could not be fully loaded.' : 'No saved artifacts yet. Save a report or an ATLAS curriculum to begin.'}</p>}
      <div className="artifact-grid">
        {filtered.map(item => <article key={item.key} className="glass-card-solid artifact-card" aria-label={item.title || 'Saved artifact'}>
          <h2>{item.title || 'Saved artifact'}</h2>
          <div className="artifact-tags">
            <span>{categories.find(type => type.id === item.category)?.label || item.category}</span>
            <span>{STATUS_LABELS[item.artifact_status] || STATUS_LABELS.unknown}</span>
            <span>{item.format || 'txt'}</span>
          </div>
          <p>{item.summary || item.body?.slice(0, 160) || 'No summary provided.'}</p>
          <p className="artifact-meta">{item.agent_id || 'Agent not recorded'} · {item.source || 'workspace'}<br />{formatStamp(item.created_at)}</p>
          {item.path && <p className="artifact-meta">Saved path: {item.path}</p>}
          <details>
            <summary>Preview artifact</summary>
            {item.curriculum
              ? <CurriculumArtifactPanel curriculum={item.curriculum} alreadySaved onSaved={load} />
              : <pre>{item.body}</pre>}
          </details>
          {Object.entries(item.origin || {}).filter(([key]) => key !== 'page').map(([key, value]) => <p className="artifact-meta" key={key}>{key.replaceAll('_', ' ')}: {value}</p>)}
          <div className="artifact-actions">
            <button onClick={() => download(item)} disabled={busy}>Download {item.curriculum ? 'JSON' : 'text'}</button>
            {item.docx_filename && <button onClick={() => downloadDocx(item)} disabled={busy}>Download DOCX</button>}
            {item.body && <button onClick={() => action(async () => { await navigator.clipboard.writeText(item.body); setNotice('Artifact copied.') })} disabled={busy}>Copy</button>}
            {setPage && PAGE_LABELS[item.origin?.page] && <button onClick={() => setPage(item.origin.page)}>Open {PAGE_LABELS[item.origin.page]}</button>}
            {!item.curriculum && <button onClick={() => setConfirmDelete(item.id)} disabled={busy || loading}>Remove</button>}
          </div>
        </article>)}
      </div>
      <p className="artifact-meta">Legacy outputs without type or assessment metadata remain Uncategorized / Not assessed. Notes and flashcards appear here only when saved as outputs; their live libraries remain separate. Origin buttons open the relevant workspace, not a replay of an old run.</p>
    </div>
  )
}
