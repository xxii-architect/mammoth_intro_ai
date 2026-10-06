import { useEffect, useState } from 'react'
import { Download, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react'
import { api } from '../api/client'

const pct = (value) => (value === null || value === undefined ? '—' : `${Math.round(value * 100)}%`)

const cell = { padding: '5px 8px', borderBottom: '1px solid var(--border)', fontSize: '0.74rem', color: 'var(--txt-sec)', textAlign: 'left' }
const control = { padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)', fontSize: '0.74rem', maxWidth: '100%' }
const emptyFilters = { agent_id: '', date_from: '', date_to: '' }

/** Owner/admin view of mammoth.feedback.v1 ratings. The backend enforces admin access. */
export default function ReplyRatingsPanel() {
  const [summary, setSummary] = useState(null)
  const [cases, setCases] = useState([])
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [openCase, setOpenCase] = useState('')
  const [draftFilters, setDraftFilters] = useState(emptyFilters)
  const [filters, setFilters] = useState(emptyFilters)
  const [revision, setRevision] = useState(0)
  const invalidRange = Boolean(draftFilters.date_from && draftFilters.date_to && draftFilters.date_from > draftFilters.date_to)

  useEffect(() => {
    const controller = new AbortController()
    let active = true
    const load = async () => {
      setBusy(true)
      setError('')
      setSummary(null)
      setCases([])
      setOpenCase('')
      const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value))
      try {
        const [summaryData, caseData] = await Promise.all([
          api(`/message-feedback/summary?${query}`, { signal: controller.signal }),
          api(`/message-feedback/regression-cases?limit=200&${query}`, { signal: controller.signal }),
        ])
        if (!active) return
        setSummary(summaryData)
        setCases(Array.isArray(caseData?.cases) ? caseData.cases : [])
      } catch (e) {
        if (active) setError(String(e?.message || 'Could not load reply ratings.'))
      } finally {
        if (active) setBusy(false)
      }
    }
    load()
    return () => { active = false; controller.abort() }
  }, [filters, revision])

  const downloadCases = () => {
    const blob = new Blob([JSON.stringify(cases, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `mammoth-regression-cases-${new Date().toISOString().slice(0, 10)}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const totals = summary?.totals || {}
  const reasons = Object.entries(summary?.down_reasons || {})

  return (
    <div className="glass-card-solid" style={{ padding: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
        <ThumbsUp size={16} color="var(--cyan)" />
        <span style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Mammoth Mind reply ratings (owner/admin)</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <button onClick={() => setRevision(value => value + 1)} disabled={busy} style={{ padding: '5px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.72rem', cursor: busy ? 'not-allowed' : 'pointer' }}>
            <RefreshCw size={12} style={{ marginRight: 5, verticalAlign: 'text-bottom' }} />Refresh
          </button>
          <button onClick={downloadCases} disabled={busy || Boolean(error) || !cases.length} style={{ padding: '5px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.72rem', cursor: cases.length ? 'pointer' : 'not-allowed', opacity: cases.length ? 1 : 0.6 }}>
            <Download size={12} style={{ marginRight: 5, verticalAlign: 'text-bottom' }} />Cases JSON
          </button>
        </div>
      </div>
      <p style={{ margin: '0 0 12px', fontSize: '0.74rem', color: 'var(--txt-mut)', lineHeight: 1.55 }}>
        Signal only — ratings do not retrain or change the model. Replay thumbs-down cases with
        {' '}<code>python -m mammoth_os.feedback_replay --input cases.json --out replay.md</code>.
      </p>

      <form onSubmit={event => { event.preventDefault(); if (!invalidRange) setFilters({ ...draftFilters }) }} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: 12 }}>
        <label style={{ display: 'grid', gap: 4, fontSize: '0.72rem', color: 'var(--txt-sec)' }}>
          Agent
          <select value={draftFilters.agent_id} onChange={event => setDraftFilters(value => ({ ...value, agent_id: event.target.value }))} style={control} disabled={busy}>
            <option value="">All agents</option>
            {[...new Set([...(summary?.available_agents || []), draftFilters.agent_id].filter(Boolean))].sort().map(agent => <option key={agent} value={agent}>{agent}</option>)}
          </select>
        </label>
        <label style={{ display: 'grid', gap: 4, fontSize: '0.72rem', color: 'var(--txt-sec)' }}>
          From (UTC)
          <input type="date" value={draftFilters.date_from} onChange={event => setDraftFilters(value => ({ ...value, date_from: event.target.value }))} style={control} disabled={busy} />
        </label>
        <label style={{ display: 'grid', gap: 4, fontSize: '0.72rem', color: 'var(--txt-sec)' }}>
          Through (UTC)
          <input type="date" value={draftFilters.date_to} onChange={event => setDraftFilters(value => ({ ...value, date_to: event.target.value }))} style={control} disabled={busy} />
        </label>
        <button type="submit" disabled={busy || invalidRange} style={control}>Apply filters</button>
        <button type="button" disabled={busy} onClick={() => { setDraftFilters(emptyFilters); setFilters({ ...emptyFilters }) }} style={control}>Clear</button>
      </form>
      <p style={{ margin: '0 0 10px', color: 'var(--txt-mut)', fontSize: '0.7rem' }}>Dates include both endpoints and use the rating's latest update, not the reply date. Filters also apply to Cases JSON.</p>
      {invalidRange && <div role="alert" style={{ color: '#fca5a5', fontSize: '0.76rem', marginBottom: 10 }}>From must not be after Through.</div>}
      {error && <div style={{ color: '#fca5a5', fontSize: '0.76rem', marginBottom: 10 }}>{error}</div>}

      {busy && <div role="status" style={{ color: 'var(--txt-mut)', fontSize: '0.76rem', marginBottom: 10 }}>Loading reply ratings...</div>}
      {summary && !busy && !error && <>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12, fontSize: '0.78rem', color: 'var(--txt-sec)' }}>
        <span><ThumbsUp size={12} color="#22c55e" style={{ verticalAlign: 'text-bottom' }} /> {totals.up ?? 0}</span>
        <span><ThumbsDown size={12} color="#f87171" style={{ verticalAlign: 'text-bottom' }} /> {totals.down ?? 0}</span>
        <span>Approval {pct(totals.approval)}</span>
        <span>{totals.raters ?? 0} rater{totals.raters === 1 ? '' : 's'}</span>
      </div>

      {Array.isArray(summary?.by_model) && summary.by_model.length > 0 && (
        <div style={{ overflowX: 'auto', marginBottom: 12 }}>
          <table style={{ borderCollapse: 'collapse', width: '100%' }}>
            <thead>
              <tr>{['Provider', 'Model', 'Up', 'Down', 'Approval'].map((h) => <th key={h} style={{ ...cell, color: 'var(--txt-mut)', fontWeight: 600 }}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {summary.by_model.map((row) => (
                <tr key={`${row.provider}/${row.model}`}>
                  <td style={cell}>{row.provider}</td>
                  <td style={{ ...cell, fontFamily: 'JetBrains Mono,monospace' }}>{row.model}</td>
                  <td style={cell}>{row.up}</td>
                  <td style={cell}>{row.down}</td>
                  <td style={cell}>{pct(row.approval)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {reasons.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
          {reasons.map(([reason, count]) => (
            <span key={reason} style={{ padding: '3px 8px', borderRadius: 999, border: '1px solid rgba(248,113,113,0.3)', color: '#fca5a5', fontSize: '0.68rem' }}>
              {reason.replaceAll('_', ' ')} · {count}
            </span>
          ))}
        </div>
      )}

      <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', marginBottom: 6 }}>Regression cases ({cases.length})</div>
      <div style={{ display: 'grid', gap: 8 }}>
        {cases.length === 0 ? (
          <div style={{ color: 'var(--txt-mut)', fontSize: '0.78rem' }}>No thumbs-down replies match these filters.</div>
        ) : cases.slice(0, 25).map((item) => (
          <div key={item.id} style={{ border: '1px solid var(--border)', borderRadius: 10, background: 'rgba(255,255,255,0.03)', padding: 10 }}>
            <button
              type="button"
              onClick={() => setOpenCase(openCase === item.id ? '' : item.id)}
              style={{ all: 'unset', cursor: 'pointer', display: 'block', width: '100%' }}
            >
              <div style={{ fontSize: '0.78rem', color: 'var(--txt-pri)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: openCase === item.id ? 'normal' : 'nowrap' }}>{item.prompt}</div>
              <div style={{ fontSize: '0.66rem', color: 'var(--txt-mut)', marginTop: 3 }}>
                {(item.reason || 'unspecified').replaceAll('_', ' ')} · {item.provider}/{item.model} · reported {item.reports}x
              </div>
            </button>
            {openCase === item.id && (
              <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                {item.comment && <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)' }}>Rater: {item.comment}</div>}
                <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)', whiteSpace: 'pre-wrap', maxHeight: 240, overflowY: 'auto', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,0,0,0.15)' }}>
                  {item.rejected_reply || '(empty reply)'}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
      </>}
    </div>
  )
}
