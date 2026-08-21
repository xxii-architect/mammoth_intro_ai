import { useMemo, useState, useEffect } from 'react'
import { ClipboardList, FolderKanban, Target } from 'lucide-react'

import { api } from '../api/client'

function normalizeEntry(entry) {
  const lesson = entry?.lesson && typeof entry.lesson === 'object' ? entry.lesson : {}
  const moduleName = String(lesson.module_title || lesson.module_name || '').trim()
  const projectName = moduleName || String(lesson.topic || lesson.title || lesson.lesson_title || entry?.lesson_id || 'Learning Project').trim()
  const lastSubmission = entry?.last_submission && typeof entry.last_submission === 'object' ? entry.last_submission : {}
  return {
    id: entry?.id || `${entry?.created_at || ''}-${entry?.title || ''}`,
    project: projectName || 'Learning Project',
    title: String(lesson.title || lesson.lesson_title || entry?.lesson_id || 'Lesson').trim(),
    status: lastSubmission.passed === true ? 'DONE' : lastSubmission.passed === false ? 'IN_PROGRESS' : 'LOGGED',
    created_at: String(entry?.updated_at || entry?.created_at || '').trim(),
    confidence: Number(lastSubmission?.score || 0),
  }
}

export default function ProjectsPage() {
  const [entries, setEntries] = useState([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let alive = true
    api('/atlas/status')
      .then((data) => {
        if (!alive) return
        const history = Array.isArray(data?.lesson_history) ? data.lesson_history : []
        const normalized = history.map(normalizeEntry)
        setEntries(normalized)
      })
      .catch((e) => {
        if (!alive) return
        setError(e instanceof Error ? e.message : 'Could not load project progress')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  const projectStats = useMemo(() => {
    const map = new Map()
    entries.forEach((entry) => {
      if (!map.has(entry.project)) {
        map.set(entry.project, { name: entry.project, total: 0, complete: 0, recent: '', avgConfidence: 0, confidenceCount: 0 })
      }
      const item = map.get(entry.project)
      item.total += 1
      if (String(entry.status).toUpperCase() === 'YES' || String(entry.status).toUpperCase() === 'DONE') {
        item.complete += 1
      }
      if (entry.created_at && (!item.recent || entry.created_at > item.recent)) {
        item.recent = entry.created_at
      }
      if (entry.confidence > 0) {
        item.avgConfidence += entry.confidence
        item.confidenceCount += 1
      }
    })
    return Array.from(map.values())
      .map((item) => ({
        ...item,
        avgConfidence: item.confidenceCount ? Math.round(item.avgConfidence / item.confidenceCount) : 0,
      }))
      .sort((a, b) => b.total - a.total)
  }, [entries])

  return (
    <div className="page-enter" style={{ padding: 24, display: 'grid', gap: 14 }}>
      <div>
        <div style={{ fontSize: '0.72rem', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--txt-mut)' }}>
          Learner Workspace
        </div>
        <h1 style={{ fontSize: '1.15rem', margin: '6px 0 0', display: 'flex', alignItems: 'center', gap: 8 }}>
          <FolderKanban size={18} color="var(--photon)" />
          Projects Progress
        </h1>
      </div>

      <div className="glass-card-solid" style={{ padding: 16 }}>
        <p style={{ margin: 0, color: 'var(--txt-sec)', fontSize: '0.84rem', lineHeight: 1.65 }}>
          Track your project momentum and session outcomes in one learner-friendly dashboard.
        </p>
      </div>

      {error && (
        <div style={{ padding: 12, borderRadius: 10, border: '1px solid rgba(239,68,68,0.24)', background: 'rgba(127,29,29,0.18)', color: '#fecaca', fontSize: '0.8rem' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="glass-card-solid" style={{ padding: 16, color: 'var(--txt-sec)' }}>Loading project progress…</div>
      ) : projectStats.length === 0 ? (
        <div className="glass-card-solid" style={{ padding: 16, color: 'var(--txt-sec)' }}>
          No project progress entries yet. Finish a lesson and your project activity will appear here.
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 10 }}>
          {projectStats.map((project) => (
            <section key={project.name} className="glass-card-solid" style={{ padding: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ fontSize: '0.92rem', color: 'var(--txt-pri)', fontWeight: 700 }}>{project.name}</div>
                <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)' }}>
                  {project.recent ? `Last update: ${new Date(project.recent).toLocaleString()}` : 'No timestamp'}
                </div>
              </div>
              <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 8 }}>
                <div className="glass-card" style={{ padding: 10 }}>
                  <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--txt-mut)' }}>Entries</div>
                  <div style={{ marginTop: 4, fontSize: '1rem', color: 'var(--photon)', fontFamily: 'JetBrains Mono,monospace' }}>{project.total}</div>
                </div>
                <div className="glass-card" style={{ padding: 10 }}>
                  <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--txt-mut)' }}>Completed</div>
                  <div style={{ marginTop: 4, fontSize: '1rem', color: '#22c55e', fontFamily: 'JetBrains Mono,monospace', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Target size={14} />
                    {project.complete}
                  </div>
                </div>
                <div className="glass-card" style={{ padding: 10 }}>
                  <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--txt-mut)' }}>Avg confidence</div>
                  <div style={{ marginTop: 4, fontSize: '1rem', color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace', display: 'flex', alignItems: 'center', gap: 6 }}>
                    <ClipboardList size={14} />
                    {project.avgConfidence}/10
                  </div>
                </div>
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
