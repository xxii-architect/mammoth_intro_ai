import { useCallback, useEffect, useState } from 'react'
import { Download, RefreshCw, ThumbsDown, ThumbsUp } from 'lucide-react'
import { api } from '../api/client'

const pct = (value) => (value === null || value === undefined ? '—' : `${Math.round(value * 100)}%`)

const cell = { padding: '5px 8px', borderBottom: '1px solid var(--border)', fontSize: '0.74rem', color: 'var(--txt-sec)', textAlign: 'left' }

/** Owner/admin view of mammoth.feedback.v1 ratings. The backend enforces admin access. */
export default function ReplyRatingsPanel() {
  const [summary, setSummary] = useState(null)
  const [cases, setCases] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [openCase, setOpenCase] = useState('')

  const load = useCallback(async () => {
    setBusy(true)
    setError('')
    try {
      const [summaryData, caseData] = await Promise.all([
        api('/message-feedback/summary'),
        api('/message-feedback/regression-cases?limit=200'),
      ])
      setSummary(summaryData)
      setCases(Array.isArray(caseData?.cases) ? caseData.cases : [])
    } catch (e) {
      setError(String(e?.message || 'Could not load reply ratings.'))
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

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
          <button onClick={load} disabled={busy} style={{ padding: '5px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.72rem', cursor: busy ? 'not-allowed' : 'pointer' }}>
            <RefreshCw size={12} style={{ marginRight: 5, verticalAlign: 'text-bottom' }} />Refresh
          </button>
          <button onClick={downloadCases} disabled={!cases.length} style={{ padding: '5px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.72rem', cursor: cases.length ? 'pointer' : 'not-allowed', opacity: cases.length ? 1 : 0.6 }}>
            <Download size={12} style={{ marginRight: 5, verticalAlign: 'text-bottom' }} />Cases JSON
          </button>
        </div>
      </div>
      <p style={{ margin: '0 0 12px', fontSize: '0.74rem', color: 'var(--txt-mut)', lineHeight: 1.55 }}>
        Signal only — ratings do not retrain or change the model. Replay thumbs-down cases with
        {' '}<code>python -m mammoth_os.feedback_replay --input cases.json --out replay.md</code>.
      </p>

      {error && <div style={{ color: '#fca5a5', fontSize: '0.76rem', marginBottom: 10 }}>{error}</div>}

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
          <div style={{ color: 'var(--txt-mut)', fontSize: '0.78rem' }}>No thumbs-down replies yet.</div>
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
    </div>
  )
}
