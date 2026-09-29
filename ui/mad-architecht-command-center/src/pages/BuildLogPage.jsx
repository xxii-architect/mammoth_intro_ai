import { useEffect, useMemo, useState } from 'react'
import {
  ClipboardList,
  Plus,
  ChevronDown,
  ChevronRight,
  Target,
  BookOpen,
  TimerReset,
  Brain,
  Wrench,
  AlertTriangle,
  Flag,
} from 'lucide-react'
import { api } from '../api/client'

const EMPTY_FORM = {
  date: '',
  start_time: '',
  end_time: '',
  session_number: '',
  phase: 'Phase 1 — Boot Sequence',
  month: '',
  primary_task: '',
  resource: '',
  project: 'ATLAS/Mammoth',
  energy_level: '',
  focus_level: '',
  session_goal: '',
  concepts_learned: '',
  code_commands: '',
  errors_solved: '',
  open_questions: '',
  atlas_connections: '',
  resources_to_revisit: '',
  total_time_logged: '',
  goal_outcome: 'MOSTLY',
  top_wins: '',
  blockers: '',
  tomorrow_task: '',
  copilot_prompt: '',
  confidence_level: '',
  confidence_why: '',
  tags: '',
}

const MODULE_ROADMAP = [
  'Wilderness navigation, survival, and safety',
  'Hunting and fishing fundamentals',
  'Ham radio and emergency comms',
  'EMT and emergency management',
  'Horticulture, botany, and weather literacy',
]

function normalizeEntry(entry) {
  const fields = entry?.fields && typeof entry.fields === 'object' ? entry.fields : {}
  return {
    ...entry,
    fields,
    title: entry?.title || fields.primary_task || 'Untitled session',
    description: entry?.description || fields.session_goal || '',
    tags: Array.isArray(entry?.tags) ? entry.tags : [],
    phase: entry?.phase || fields.phase || '',
    month: entry?.month || fields.month || '',
    project: entry?.project || fields.project || '',
    status: entry?.status || fields.goal_outcome || '',
  }
}

function statCard(label, value, note, accent = 'var(--photon)') {
  return (
    <div className="glass-card-solid" style={{ padding: 16 }}>
      <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: '1.2rem', fontWeight: 800, color: accent, fontFamily: 'JetBrains Mono,monospace' }}>{value}</div>
      <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)', marginTop: 6 }}>{note}</div>
    </div>
  )
}

export default function BuildLogPage() {
  const [entries, setEntries] = useState([])
  const [open, setOpen] = useState({})
  const [showForm, setShowForm] = useState(false)
  const [filter, setFilter] = useState('')
  const [saving, setSaving] = useState(false)
  const [form, setForm] = useState(() => ({
    ...EMPTY_FORM,
    date: new Date().toISOString().slice(0, 10),
  }))

  useEffect(() => {
    api('/buildlog')
      .then((data) => setEntries(Array.isArray(data) ? data.map(normalizeEntry) : []))
      .catch(() => {})
  }, [])

  const toggleEntry = (id) => setOpen((prev) => ({ ...prev, [id]: !prev[id] }))

  const submit = async (e) => {
    e.preventDefault()
    setSaving(true)
    const tags = form.tags.split(',').map((t) => t.trim()).filter(Boolean)
    const fields = {
      date: form.date,
      start_time: form.start_time,
      end_time: form.end_time,
      session_number: form.session_number,
      phase: form.phase,
      month: form.month,
      primary_task: form.primary_task,
      resource: form.resource,
      project: form.project,
      energy_level: form.energy_level,
      focus_level: form.focus_level,
      session_goal: form.session_goal,
      concepts_learned: form.concepts_learned,
      code_commands: form.code_commands,
      errors_solved: form.errors_solved,
      open_questions: form.open_questions,
      atlas_connections: form.atlas_connections,
      resources_to_revisit: form.resources_to_revisit,
      total_time_logged: form.total_time_logged,
      goal_outcome: form.goal_outcome,
      top_wins: form.top_wins,
      blockers: form.blockers,
      tomorrow_task: form.tomorrow_task,
      copilot_prompt: form.copilot_prompt,
      confidence_level: form.confidence_level,
      confidence_why: form.confidence_why,
    }
    try {
      const entry = await api('/buildlog', {
        method: 'POST',
        body: {
          title: form.primary_task,
          description: form.session_goal,
          command: form.code_commands.split('\n').find(Boolean) || '',
          project: form.project,
          phase: form.phase,
          month: form.month,
          status: form.goal_outcome,
          tags,
          fields,
        },
      })
      setEntries((prev) => [...prev, normalizeEntry(entry)])
      setForm({
        ...EMPTY_FORM,
        date: new Date().toISOString().slice(0, 10),
        phase: form.phase,
        month: form.month,
        project: form.project,
      })
      setShowForm(false)
    } catch (err) {
      alert(`Failed: ${err.message}`)
    } finally {
      setSaving(false)
    }
  }

  const normalizedEntries = useMemo(() => entries.map(normalizeEntry), [entries])
  const allTags = [...new Set(normalizedEntries.flatMap((e) => e.tags || []))]
  const filtered = filter ? normalizedEntries.filter((e) => (e.tags || []).includes(filter)) : normalizedEntries
  const latest = filtered.length ? filtered[filtered.length - 1] : null
  const totalSessions = normalizedEntries.length
  const avgConfidence = normalizedEntries.length
    ? Math.round(normalizedEntries.reduce((sum, entry) => sum + Number(entry.fields?.confidence_level || 0), 0) / normalizedEntries.length)
    : 0
  const mostRecentProject = latest?.project || 'ATLAS/Mammoth'

  const notesBlock = (label, value, Icon) => (
    <div style={{ padding: '12px 14px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <Icon size={14} color="var(--cyan)" />
        <span style={{ fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>{label}</span>
      </div>
      <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.82rem', lineHeight: 1.6, color: 'var(--txt-sec)' }}>
        {value || '—'}
      </div>
    </div>
  )

  return (
    <div className="page-enter page-shell">
      <div className="page-header" style={{ marginBottom: 22 }}>
        <div style={{ maxWidth: 840 }}>
          <div style={{ fontSize: '0.72rem', letterSpacing: '0.28em', textTransform: 'uppercase', color: 'var(--txt-mut)', marginBottom: 8 }}>
            ATLAS Protocol // Operator Field Document
          </div>
          <h1 style={{ fontSize: '1.35rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <ClipboardList size={22} color="var(--photon)" /> Daily Build Log
          </h1>
          <p style={{ margin: 0, fontSize: '0.86rem', color: 'var(--txt-sec)', lineHeight: 1.7 }}>
            Structured as a living engineering field log: mission brief, field notes, debrief, and portfolio evidence.
            Each session becomes operational proof of progress for ATLAS, MammothOS, and your broader learning system.
          </p>
        </div>
        <div className="page-header__actions">
          <button
            onClick={() => setShowForm((v) => !v)}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '10px 16px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.08)', color: 'var(--photon)', fontSize: '0.85rem', cursor: 'pointer' }}
          >
            <Plus size={16} /> {showForm ? 'Close Entry Form' : 'New Session Entry'}
          </button>
        </div>
      </div>

      <div className="glass-card-solid" style={{ padding: 18, marginBottom: 18 }}>
        <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700, marginBottom: 10 }}>
          Operator manual
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12 }}>
          {[
            'Duplicate a clean session entry for every learning block.',
            'Fill the mission brief before opening code, lessons, or diagnostics.',
            'Use field notes as raw intelligence; refine during debrief, not before.',
            'Write tomorrow’s first task before closing the session.',
          ].map((line) => (
            <div key={line} style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', fontSize: '0.8rem', color: 'var(--txt-sec)' }}>
              {line}
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 18 }}>
        {statCard('Sessions logged', String(totalSessions), 'Running total of operator records')}
        {statCard('Latest project', mostRecentProject, 'Most recent build target', 'var(--cyan)')}
        {statCard('Avg confidence', totalSessions ? `${avgConfidence}/10` : '0/10', 'Confidence trend from debriefs', 'var(--violet)')}
        {statCard('Future module lane', String(MODULE_ROADMAP.length), 'Domain tracks queued for curriculum expansion', 'var(--photon)')}
      </div>

      <div className="buildlog-layout">
        <div style={{ display: 'grid', gap: 16 }}>
          {showForm && (
            <form onSubmit={submit} className="glass-card-solid" style={{ padding: 20 }}>
              <div style={{ marginBottom: 16 }}>
                <h2 style={{ margin: '0 0 6px', fontSize: '1rem', color: 'var(--txt-pri)' }}>Session Entry Template</h2>
                <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--txt-sec)' }}>
                  Mission brief first. Field notes during the session. Debrief before you close.
                </p>
              </div>

              <div style={{ display: 'grid', gap: 18 }}>
                <section>
                  <div style={{ fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 10 }}>Mission brief</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
                    {[
                      ['date', 'Date', 'date'],
                      ['start_time', 'Start Time', 'time'],
                      ['end_time', 'End Time', 'time'],
                      ['session_number', 'Session #', 'text'],
                      ['phase', 'Phase', 'text'],
                      ['month', 'Month', 'text'],
                      ['resource', 'Course / Resource', 'text'],
                      ['project', 'Project Being Built', 'text'],
                      ['energy_level', 'Energy (1-10)', 'number'],
                      ['focus_level', 'Focus (1-10)', 'number'],
                      ['confidence_level', 'Confidence (1-10)', 'number'],
                    ].map(([key, label, type]) => (
                      <div key={key}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>{label}</label>
                        <input
                          type={type}
                          value={form[key]}
                          onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
                          style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)' }}
                        />
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <label style={{ display: 'block', marginBottom: 4, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>Today&apos;s Primary Task</label>
                    <input
                      value={form.primary_task}
                      onChange={(e) => setForm((prev) => ({ ...prev, primary_task: e.target.value }))}
                      style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)' }}
                    />
                  </div>
                  <div style={{ marginTop: 12 }}>
                    <label style={{ display: 'block', marginBottom: 4, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>Session Goal</label>
                    <textarea
                      rows={2}
                      value={form.session_goal}
                      onChange={(e) => setForm((prev) => ({ ...prev, session_goal: e.target.value }))}
                      style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', resize: 'vertical' }}
                    />
                  </div>
                </section>

                <section>
                  <div style={{ fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 10 }}>Field notes</div>
                  <div style={{ display: 'grid', gap: 12 }}>
                    {[
                      ['concepts_learned', 'Concepts learned'],
                      ['code_commands', 'Code / commands'],
                      ['errors_solved', 'Errors encountered + how I solved them'],
                      ['open_questions', 'Questions I could not answer yet'],
                      ['atlas_connections', 'Ideas / connections to True XXII or ATLAS'],
                      ['resources_to_revisit', 'Links / resources to revisit'],
                    ].map(([key, label]) => (
                      <div key={key}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>{label}</label>
                        <textarea
                          rows={3}
                          value={form[key]}
                          onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
                          style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', resize: 'vertical' }}
                        />
                      </div>
                    ))}
                  </div>
                </section>

                <section>
                  <div style={{ fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 10 }}>Session debrief</div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: 12 }}>
                    <div>
                      <label style={{ display: 'block', marginBottom: 4, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>Total Time Logged</label>
                      <input
                        value={form.total_time_logged}
                        onChange={(e) => setForm((prev) => ({ ...prev, total_time_logged: e.target.value }))}
                        style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: 4, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>Did I hit my session goal?</label>
                      <select
                        value={form.goal_outcome}
                        onChange={(e) => setForm((prev) => ({ ...prev, goal_outcome: e.target.value }))}
                        style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)' }}
                      >
                        <option value="YES">YES</option>
                        <option value="MOSTLY">MOSTLY</option>
                        <option value="NO">NO</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: 4, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>Tags</label>
                      <input
                        value={form.tags}
                        onChange={(e) => setForm((prev) => ({ ...prev, tags: e.target.value }))}
                        placeholder="atlas, buildlog, diagnostics"
                        style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)' }}
                      />
                    </div>
                  </div>
                  <div style={{ display: 'grid', gap: 12, marginTop: 12 }}>
                    {[
                      ['top_wins', 'Top 3 wins today'],
                      ['blockers', 'Blockers / frustrations'],
                      ['tomorrow_task', "Tomorrow's first task"],
                      ['copilot_prompt', 'Copilot prompt I used today'],
                      ['confidence_why', 'Why this confidence level?'],
                    ].map(([key, label]) => (
                      <div key={key}>
                        <label style={{ display: 'block', marginBottom: 4, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>{label}</label>
                        <textarea
                          rows={key === 'top_wins' ? 3 : 2}
                          value={form[key]}
                          onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
                          style={{ width: '100%', boxSizing: 'border-box', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', resize: 'vertical' }}
                        />
                      </div>
                    ))}
                  </div>
                </section>

                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <button type="submit" disabled={saving} style={{ padding: '9px 18px', borderRadius: 8, border: 'none', background: 'var(--photon)', color: '#050608', fontWeight: 700, cursor: 'pointer' }}>
                    {saving ? 'Saving…' : 'Save Session Entry'}
                  </button>
                  <button type="button" onClick={() => setShowForm(false)} style={{ padding: '9px 16px', borderRadius: 8, border: '1px solid var(--border)', background: 'none', color: 'var(--txt-sec)', cursor: 'pointer' }}>
                    Cancel
                  </button>
                </div>
              </div>
            </form>
          )}

          <div className="glass-card-solid" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700 }}>Session archive</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--txt-mut)', marginTop: 4 }}>{filtered.length} entries visible</div>
              </div>
              {allTags.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  <span
                    onClick={() => setFilter('')}
                    style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', padding: '4px 10px', borderRadius: 20, border: `1px solid ${!filter ? 'var(--photon)' : 'var(--border)'}`, background: !filter ? 'rgba(77,166,255,0.1)' : 'rgba(255,255,255,0.04)', color: !filter ? 'var(--photon)' : 'var(--txt-sec)', cursor: 'pointer' }}
                  >
                    all
                  </span>
                  {allTags.map((tag) => (
                    <span
                      key={tag}
                      onClick={() => setFilter(tag)}
                      style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', padding: '4px 10px', borderRadius: 20, border: `1px solid ${filter === tag ? 'var(--cyan)' : 'var(--border)'}`, background: filter === tag ? 'rgba(0,245,212,0.08)' : 'rgba(255,255,255,0.04)', color: filter === tag ? 'var(--cyan)' : 'var(--txt-sec)', cursor: 'pointer' }}
                    >
                      #{tag}
                    </span>
                  ))}
                </div>
              )}
            </div>

            <div style={{ display: 'grid', gap: 10 }}>
              {filtered.length === 0 && <div style={{ color: 'var(--txt-mut)', fontSize: '0.88rem', padding: 12 }}>No session entries yet.</div>}
              {[...filtered].reverse().map((entry) => {
                const fields = entry.fields || {}
                return (
                  <div key={entry.id} className="glass-card-solid" style={{ borderRadius: 12, overflow: 'hidden' }}>
                    <div onClick={() => toggleEntry(entry.id)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14, padding: '14px 16px', cursor: 'pointer' }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                        {open[entry.id] ? <ChevronDown size={16} color="var(--txt-mut)" /> : <ChevronRight size={16} color="var(--txt-mut)" />}
                        <div>
                          <div style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{entry.title}</div>
                          <div style={{ marginTop: 4, fontSize: '0.74rem', color: 'var(--txt-sec)' }}>
                            {fields.date || (entry.created_at ? new Date(entry.created_at).toLocaleDateString() : 'Unknown date')}
                            {fields.start_time ? ` • ${fields.start_time}` : ''}
                            {entry.phase ? ` • ${entry.phase}` : ''}
                            {entry.project ? ` • ${entry.project}` : ''}
                          </div>
                          {entry.description && <div style={{ marginTop: 6, fontSize: '0.8rem', color: 'var(--txt-sec)' }}>{entry.description}</div>}
                        </div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
                        <span style={{ fontSize: '0.68rem', fontFamily: 'JetBrains Mono,monospace', color: entry.status === 'YES' ? '#22c55e' : entry.status === 'NO' ? '#f87171' : 'var(--cyan)' }}>
                          {entry.status || 'LOGGED'}
                        </span>
                        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'flex-end', gap: 4 }}>
                          {(entry.tags || []).slice(0, 4).map((tag) => (
                            <span key={tag} style={{ fontSize: '0.62rem', fontFamily: 'JetBrains Mono,monospace', padding: '2px 6px', borderRadius: 10, background: 'rgba(0,245,212,0.08)', color: 'var(--cyan)', border: '1px solid rgba(0,245,212,0.2)' }}>
                              #{tag}
                            </span>
                          ))}
                        </div>
                      </div>
                    </div>

                    {open[entry.id] && (
                      <div className="buildlog-expanded" style={{ padding: '0 16px 16px 42px', borderTop: '1px solid var(--border)', display: 'grid', gap: 12 }}>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10, paddingTop: 14 }}>
                          {[
                            ['Session #', fields.session_number || '—'],
                            ['Month', entry.month || '—'],
                            ['Energy', fields.energy_level ? `${fields.energy_level}/10` : '—'],
                            ['Focus', fields.focus_level ? `${fields.focus_level}/10` : '—'],
                            ['Confidence', fields.confidence_level ? `${fields.confidence_level}/10` : '—'],
                            ['Time Logged', fields.total_time_logged || '—'],
                          ].map(([label, value]) => (
                            <div key={label} style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                              <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--txt-mut)', marginBottom: 4 }}>{label}</div>
                              <div style={{ fontSize: '0.82rem', color: 'var(--txt-pri)' }}>{value}</div>
                            </div>
                          ))}
                        </div>
                        {notesBlock('Primary task', fields.primary_task, Target)}
                        {notesBlock('Resource / course', fields.resource, BookOpen)}
                        {notesBlock('Concepts learned', fields.concepts_learned, Brain)}
                        {notesBlock('Code / commands', fields.code_commands || entry.command, Wrench)}
                        {notesBlock('Errors solved', fields.errors_solved, AlertTriangle)}
                        {notesBlock('Tomorrow’s first task', fields.tomorrow_task, Flag)}
                        {notesBlock('Open questions', fields.open_questions, Target)}
                        {notesBlock('Connections to ATLAS / True XXII', fields.atlas_connections, ClipboardList)}
                        {notesBlock('Resources to revisit', fields.resources_to_revisit, BookOpen)}
                        {notesBlock('Top wins', fields.top_wins, TimerReset)}
                        {notesBlock('Blockers / frustrations', fields.blockers, AlertTriangle)}
                        {notesBlock('Copilot prompt used', fields.copilot_prompt, Brain)}
                        {notesBlock('Confidence rationale', fields.confidence_why, TimerReset)}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gap: 16 }}>
          <div className="glass-card-solid" style={{ padding: 18 }}>
            <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700, marginBottom: 10 }}>
              Phase tracker
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              {[
                ['Phase 1 — Boot Sequence', 'Python, ML foundations, dev environment'],
                ['Phase 2 — Model Forge', 'Deep learning, PyTorch, AWS AI Practitioner'],
                ['Phase 3 — Systems Online', 'LLMs, LangChain, Azure AI-102'],
                ['Phase 4 — Launch Sequence', 'Portfolio polish, applications, AWS MLA-C01'],
              ].map(([phase, note]) => (
                <div key={phase} style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: latest?.phase === phase ? 'rgba(77,166,255,0.08)' : 'rgba(255,255,255,0.03)' }}>
                  <div style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', fontWeight: 700 }}>{phase}</div>
                  <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)', marginTop: 4 }}>{note}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="glass-card-solid" style={{ padding: 18 }}>
            <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700, marginBottom: 10 }}>
              Module roadmap
            </div>
            <div style={{ display: 'grid', gap: 8 }}>
              {MODULE_ROADMAP.map((item) => (
                <div key={item} style={{ padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', fontSize: '0.8rem', color: 'var(--txt-sec)' }}>
                  {item}
                </div>
              ))}
            </div>
          </div>

          <div className="glass-card-solid" style={{ padding: 18 }}>
            <div style={{ fontSize: '0.78rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700, marginBottom: 10 }}>
              Operator creed
            </div>
            <p style={{ margin: 0, fontSize: '0.82rem', lineHeight: 1.7, color: 'var(--txt-sec)' }}>
              The portfolio is everything. The work is the credential. Every session logged here becomes proof:
              what you built, what you learned, what blocked you, and what happens next.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
