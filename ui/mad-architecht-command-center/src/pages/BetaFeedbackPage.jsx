import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Bug, CheckCircle2, ClipboardList, RefreshCw, ShieldCheck } from 'lucide-react'
import { api } from '../api/client'

const AREAS = [
  'Authentication',
  'Navigation',
  'Mammoth Mind Chat',
  'ATLAS Tutor',
  'Lessons',
  'Diagnostics',
  'Account',
  'Performance',
  'Mobile UX',
  'Other',
]

const SEVERITIES = ['low', 'medium', 'high', 'critical']
const STATUS_COLORS = {
  new: '#f59e0b',
  triaged: '#38bdf8',
  in_progress: '#a78bfa',
  fixed: '#22c55e',
  closed: '#94a3b8',
}

export default function BetaFeedbackPage() {
  const [entries, setEntries] = useState([])
  const [canManage, setCanManage] = useState(false)
  const [busy, setBusy] = useState(false)
  const [submitBusy, setSubmitBusy] = useState(false)
  const [error, setError] = useState('')
  const [ok, setOk] = useState('')
  const [form, setForm] = useState({
    area: 'Mammoth Mind Chat',
    severity: 'medium',
    title: '',
    summary: '',
    expected_behavior: '',
    actual_behavior: '',
    reproduction_steps: '',
    device: '',
    browser: '',
    reproducible: true,
    safety_acknowledged: false,
  })

  const incomplete = useMemo(() => {
    return !form.safety_acknowledged || !form.title.trim() || !form.summary.trim() || !form.reproduction_steps.trim()
  }, [form])

  const loadFeedback = async () => {
    setBusy(true)
    setError('')
    try {
      const data = await api('/beta-feedback')
      setEntries(Array.isArray(data?.entries) ? data.entries : [])
      setCanManage(Boolean(data?.can_manage))
    } catch (e) {
      setError(String(e?.message || 'Could not load beta feedback.'))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    loadFeedback()
  }, [])

  const submit = async () => {
    if (incomplete || submitBusy) return
    setSubmitBusy(true)
    setError('')
    setOk('')
    try {
      await api('/beta-feedback', { method: 'POST', body: form })
      setOk('Feedback submitted. Thank you for helping improve MammothOS.')
      setForm({
        area: form.area,
        severity: 'medium',
        title: '',
        summary: '',
        expected_behavior: '',
        actual_behavior: '',
        reproduction_steps: '',
        device: '',
        browser: '',
        reproducible: true,
        safety_acknowledged: false,
      })
      await loadFeedback()
    } catch (e) {
      setError(String(e?.message || 'Feedback submission failed.'))
    } finally {
      setSubmitBusy(false)
    }
  }

  const updateStatus = async (id, status) => {
    try {
      await api(`/beta-feedback/${id}/status`, { method: 'POST', body: { status } })
      await loadFeedback()
    } catch (e) {
      setError(String(e?.message || 'Could not update feedback status.'))
    }
  }

  return (
    <div className="page-enter" style={{ padding: '28px 24px 90px', display: 'grid', gap: 16 }}>
      <div className="glass-card-solid" style={{ padding: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <ClipboardList size={18} color="var(--cyan)" />
          <h1 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: 'var(--txt-pri)' }}>Beta Tester Feedback Portal</h1>
        </div>
        <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--txt-sec)', lineHeight: 1.65 }}>
          Submit reproducible bugs, UX confusion points, and suggestions. This portal is designed for safe beta testing only.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(280px,1fr))', gap: 16 }}>
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <ShieldCheck size={16} color="#22c55e" />
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--txt-pri)' }}>What beta testers should test</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 6, color: 'var(--txt-sec)', fontSize: '0.78rem', lineHeight: 1.55 }}>
            <li>Sign in / sign up flow and role visibility.</li>
            <li>Mammoth Mind and ATLAS tutor response clarity.</li>
            <li>Lesson flow (intro, content, feedback loop, practice).</li>
            <li>Mobile usability and navigation friction.</li>
            <li>Account profile, analytics, streaks, and progress views.</li>
            <li>Performance issues, slow screens, or hanging actions.</li>
          </ul>
        </div>

        <div className="glass-card-solid" style={{ padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
            <AlertTriangle size={16} color="#f59e0b" />
            <span style={{ fontSize: '0.8rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Safety scope (do not test)</span>
          </div>
          <ul style={{ margin: 0, paddingLeft: 18, display: 'grid', gap: 6, color: 'var(--txt-sec)', fontSize: '0.78rem', lineHeight: 1.55 }}>
            <li>No destructive commands or system-level experiments.</li>
            <li>No attempts to bypass authentication or access controls.</li>
            <li>No token/key extraction attempts from UI or network logs.</li>
            <li>No stress tests that intentionally crash services.</li>
            <li>Report risky behavior instead of executing it.</li>
          </ul>
        </div>
      </div>

      <div className="glass-card-solid" style={{ padding: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <Bug size={16} color="var(--violet)" />
          <span style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Submit feedback</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(220px,1fr))', gap: 10, marginBottom: 10 }}>
          <select value={form.area} onChange={(e) => setForm((prev) => ({ ...prev, area: e.target.value }))} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)' }}>
            {AREAS.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <select value={form.severity} onChange={(e) => setForm((prev) => ({ ...prev, severity: e.target.value }))} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)' }}>
            {SEVERITIES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
          <input value={form.device} onChange={(e) => setForm((prev) => ({ ...prev, device: e.target.value }))} placeholder="Device (e.g. iPhone 14, Windows laptop)" style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)' }} />
          <input value={form.browser} onChange={(e) => setForm((prev) => ({ ...prev, browser: e.target.value }))} placeholder="Browser (e.g. Chrome 139)" style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)' }} />
        </div>

        <div style={{ display: 'grid', gap: 10 }}>
          <input value={form.title} onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))} placeholder="Short title (required)" style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)' }} />
          <textarea value={form.summary} onChange={(e) => setForm((prev) => ({ ...prev, summary: e.target.value }))} placeholder="What happened? (required)" rows={3} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)' }} />
          <textarea value={form.expected_behavior} onChange={(e) => setForm((prev) => ({ ...prev, expected_behavior: e.target.value }))} placeholder="Expected behavior" rows={2} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)' }} />
          <textarea value={form.actual_behavior} onChange={(e) => setForm((prev) => ({ ...prev, actual_behavior: e.target.value }))} placeholder="Actual behavior" rows={2} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)' }} />
          <textarea value={form.reproduction_steps} onChange={(e) => setForm((prev) => ({ ...prev, reproduction_steps: e.target.value }))} placeholder="Exact reproduction steps (required)" rows={4} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)' }} />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 12, flexWrap: 'wrap' }}>
          <label style={{ fontSize: '0.76rem', color: 'var(--txt-sec)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <input type="checkbox" checked={form.reproducible} onChange={(e) => setForm((prev) => ({ ...prev, reproducible: e.target.checked }))} />
            Reproducible on my side
          </label>
          <label style={{ fontSize: '0.76rem', color: 'var(--txt-sec)', display: 'flex', alignItems: 'center', gap: 6 }}>
            <input type="checkbox" checked={form.safety_acknowledged} onChange={(e) => setForm((prev) => ({ ...prev, safety_acknowledged: e.target.checked }))} />
            I confirm this test did not use destructive commands
          </label>
        </div>

        {error && <div style={{ marginTop: 10, color: '#fca5a5', fontSize: '0.76rem' }}>{error}</div>}
        {ok && <div style={{ marginTop: 10, color: '#86efac', fontSize: '0.76rem' }}>{ok}</div>}

        <div style={{ marginTop: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={submit} disabled={incomplete || submitBusy} style={{ padding: '9px 14px', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg,var(--photon),var(--cyan))', color: '#050608', fontWeight: 700, cursor: incomplete || submitBusy ? 'not-allowed' : 'pointer', opacity: incomplete || submitBusy ? 0.6 : 1 }}>
            {submitBusy ? 'Submitting...' : 'Submit feedback'}
          </button>
          <button onClick={loadFeedback} disabled={busy} style={{ padding: '9px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', cursor: busy ? 'not-allowed' : 'pointer' }}>
            <RefreshCw size={13} style={{ marginRight: 6, verticalAlign: 'text-bottom' }} />
            Refresh list
          </button>
        </div>
      </div>

      <div className="glass-card-solid" style={{ padding: 18 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <CheckCircle2 size={16} color="var(--cyan)" />
          <span style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--txt-pri)' }}>
            Submitted feedback {canManage ? '(owner/admin view)' : '(my submissions)'}
          </span>
        </div>
        <div style={{ display: 'grid', gap: 10 }}>
          {entries.length === 0 ? (
            <div style={{ color: 'var(--txt-mut)', fontSize: '0.78rem' }}>No feedback submitted yet.</div>
          ) : entries.map((entry) => (
            <div key={entry.id} style={{ border: '1px solid var(--border)', borderRadius: 10, background: 'rgba(255,255,255,0.03)', padding: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                <div style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', fontWeight: 700 }}>{entry.title || entry.summary}</div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <span style={{ fontSize: '0.66rem', color: 'var(--txt-sec)', textTransform: 'uppercase' }}>{entry.severity}</span>
                  <span style={{ fontSize: '0.66rem', color: STATUS_COLORS[entry.status] || 'var(--txt-sec)', textTransform: 'uppercase', fontWeight: 700 }}>
                    {entry.status}
                  </span>
                </div>
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', marginBottom: 8 }}>
                {entry.area} • {entry.created_at ? new Date(entry.created_at).toLocaleString() : 'unknown'}
              </div>
              <div style={{ fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>
                {entry.summary}
              </div>
              {entry.reproduction_steps && (
                <div style={{ marginTop: 8, padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 4 }}>Reproduction steps</div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)', lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{entry.reproduction_steps}</div>
                </div>
              )}
              {canManage && (
                <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {['new', 'triaged', 'in_progress', 'fixed', 'closed'].map((status) => (
                    <button
                      key={status}
                      onClick={() => updateStatus(entry.id, status)}
                      style={{ border: '1px solid var(--border)', background: entry.status === status ? 'rgba(77,166,255,0.12)' : 'rgba(255,255,255,0.02)', color: 'var(--txt-sec)', borderRadius: 6, padding: '4px 8px', fontSize: '0.68rem', cursor: 'pointer' }}
                    >
                      {status}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
