import { useEffect, useMemo, useState } from 'react'
import { BookOpen, FileText } from 'lucide-react'

import { api } from '../api/client'

function lessonTitleFromEntry(entry) {
  const lesson = entry?.lesson && typeof entry.lesson === 'object' ? entry.lesson : {}
  return String(lesson.title || lesson.lesson_title || entry.lesson_id || 'Lesson').trim()
}

export default function LessonNotesPage() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let alive = true
    api('/atlas/status')
      .then((state) => {
        if (!alive) return
        const lessonHistory = Array.isArray(state?.lesson_history) ? state.lesson_history : []
        setHistory(lessonHistory)
      })
      .catch((e) => {
        if (!alive) return
        setError(e instanceof Error ? e.message : 'Could not load lesson notes')
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
  }, [])

  const normalizedLessons = useMemo(() => {
    return [...history]
      .map((entry) => {
        const resumePacket = entry?.resume_packet && typeof entry.resume_packet === 'object' ? entry.resume_packet : {}
        const notes = Array.isArray(resumePacket.notes) ? resumePacket.notes : []
        return {
          lessonId: String(entry?.lesson_id || '').trim(),
          lessonTitle: lessonTitleFromEntry(entry),
          summary: String(entry?.summary || resumePacket.summary || '').trim(),
          updatedAt: String(entry?.updated_at || entry?.created_at || '').trim(),
          notes: notes.slice(0, 5).map((note, idx) => ({
            id: String(note?.id || `${entry?.lesson_id || 'lesson'}-${idx}`),
            title: String(note?.title || 'Lesson note').trim(),
            preview: String(note?.preview || '').trim(),
          })),
        }
      })
      .filter((entry) => entry.lessonId)
      .sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1))
  }, [history])

  return (
    <div className="page-enter" style={{ padding: 24, display: 'grid', gap: 14 }}>
      <div>
        <div style={{ fontSize: '0.72rem', letterSpacing: '0.2em', textTransform: 'uppercase', color: 'var(--txt-mut)' }}>
          Learner Workspace
        </div>
        <h1 style={{ fontSize: '1.15rem', margin: '6px 0 0', display: 'flex', alignItems: 'center', gap: 8 }}>
          <FileText size={18} color="var(--cyan)" />
          Lesson Notes
        </h1>
      </div>

      <div className="glass-card-solid" style={{ padding: 16 }}>
        <p style={{ margin: 0, color: 'var(--txt-sec)', fontSize: '0.84rem', lineHeight: 1.65 }}>
          This is your learner notes view. It keeps your lesson takeaways organized without exposing operator/admin controls.
        </p>
      </div>

      {error && (
        <div style={{ padding: 12, borderRadius: 10, border: '1px solid rgba(239,68,68,0.24)', background: 'rgba(127,29,29,0.18)', color: '#fecaca', fontSize: '0.8rem' }}>
          {error}
        </div>
      )}

      {loading ? (
        <div className="glass-card-solid" style={{ padding: 16, color: 'var(--txt-sec)' }}>Loading notes…</div>
      ) : normalizedLessons.length === 0 ? (
        <div className="glass-card-solid" style={{ padding: 16, color: 'var(--txt-sec)' }}>
          No lesson history yet. Start a lesson and this page will track your learning snapshots.
        </div>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {normalizedLessons.map((entry) => (
            <section key={entry.lessonId} className="glass-card-solid" style={{ padding: 14 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <BookOpen size={15} color="var(--photon)" />
                <span style={{ fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>
                  {entry.lessonTitle}
                </span>
                <span style={{ fontSize: '0.72rem', color: 'var(--txt-sec)' }}>
                  {entry.updatedAt ? `Updated ${new Date(entry.updatedAt).toLocaleString()}` : ''}
                </span>
              </div>
              {entry.summary && (
                <div style={{ marginBottom: 10, fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>
                  {entry.summary}
                </div>
              )}
              <div style={{ display: 'grid', gap: 8 }}>
                {entry.notes.length > 0 ? (
                  entry.notes.map((note) => (
                    <div key={note.id} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 10, background: 'rgba(255,255,255,0.03)' }}>
                      <div style={{ fontSize: '0.84rem', color: 'var(--txt-pri)', fontWeight: 600 }}>
                        {note.title}
                      </div>
                      <div style={{ marginTop: 4, fontSize: '0.8rem', color: 'var(--txt-sec)', whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>
                        {note.preview || '—'}
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 10, background: 'rgba(255,255,255,0.03)', fontSize: '0.8rem', color: 'var(--txt-sec)' }}>
                    No saved resume notes for this lesson yet.
                  </div>
                )}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  )
}
