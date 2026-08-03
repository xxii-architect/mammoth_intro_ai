import { useState, useEffect } from 'react'
import { BookOpen, Send, ChevronRight } from 'lucide-react'
import { api } from '../api/client'

export default function LessonsPage() {
  const [atlasState, setAtlasState] = useState(null)
  const [topic, setTopic]           = useState('')
  const [code, setCode]             = useState('')
  const [result, setResult]         = useState(null)
  const [loading, setLoading]       = useState(false)
  const [tab, setTab]               = useState('lesson') // 'lesson' | 'submit'

  const loadState = async () => {
    try {
      const s = await api('/atlas/status')
      setAtlasState(s)
      if (s.current_exercise?.starter_files) {
        const files = s.current_exercise.starter_files
        const first = Object.values(files)[0] || ''
        setCode(first)
      }
    } catch (_) {}
  }

  useEffect(() => { loadState() }, [])

  const startLesson = async () => {
    if (!topic.trim()) return
    setLoading(true)
    setResult(null)
    try {
      const res = await api('/atlas/lesson', { method: 'POST', body: { topic } })
      setAtlasState(prev => ({ ...prev, ...res }))
      if (res.exercise?.starter_files) {
        const first = Object.values(res.exercise.starter_files)[0] || ''
        setCode(first)
      }
      await loadState()
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setLoading(false)
    }
  }

  const submitCode = async () => {
    if (!code.trim()) return
    setLoading(true)
    try {
      const res = await api('/atlas/submit', { method: 'POST', body: { code } })
      setResult(res.result || res)
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setLoading(false)
    }
  }

  const nextLesson = async () => {
    setLoading(true)
    try {
      await api('/atlas/next', { method: 'POST', body: {} })
      await loadState()
      setResult(null)
      setCode('')
    } catch (_) {}
    setLoading(false)
  }

  const exercise = atlasState?.current_exercise
  const curriculum = atlasState?.curriculum
  const modules = curriculum?.modules || []
  const currentLessonId = atlasState?.lesson_id

  return (
    <div className="page-enter" style={{ padding: 24, display: 'flex', gap: 20, height: 'calc(100vh - 100px)' }}>
      {/* Left curriculum tree */}
      <div style={{ width: 240, flexShrink: 0, overflowY: 'auto' }}>
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 12 }}>Curriculum</p>

          {modules.length > 0 ? modules.map((mod, mi) => (
            <div key={mi} style={{ marginBottom: 12 }}>
              <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--txt-pri)', marginBottom: 4 }}>{mod.title || mod.module_title || `Module ${mi+1}`}</p>
              {(mod.lessons || []).map((lesson, li) => (
                <div key={li} style={{
                  padding: '6px 10px', borderRadius: 6, marginBottom: 2,
                  background: lesson.lesson_id === currentLessonId ? 'rgba(77,166,255,0.12)' : 'transparent',
                  borderLeft: `2px solid ${lesson.lesson_id === currentLessonId ? 'var(--photon)' : 'transparent'}`,
                  fontSize: '0.78rem', color: lesson.lesson_id === currentLessonId ? 'var(--photon)' : 'var(--txt-sec)',
                }}>
                  {lesson.title || lesson.lesson_title || `Lesson ${li+1}`}
                </div>
              ))}
            </div>
          )) : (
            <p style={{ color: 'var(--txt-mut)', fontSize: '0.8rem' }}>No curriculum loaded.</p>
          )}

          {/* Start new lesson */}
          <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>New Lesson</p>
            <input value={topic} onChange={e => setTopic(e.target.value)}
              placeholder="e.g. Python for loops"
              style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem', outline: 'none', marginBottom: 8 }} />
            <button onClick={startLesson} disabled={loading}
              style={{ width: '100%', padding: '8px', borderRadius: 8, border: 'none', background: 'var(--photon)', color: '#050608', fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer', opacity: loading ? 0.7 : 1 }}>
              {loading ? 'Loading…' : 'Start Lesson'}
            </button>
          </div>
        </div>
      </div>

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0, overflowY: 'auto' }}>
        {exercise ? (
          <>
            <div className="glass-card-solid" style={{ padding: 20 }}>
              <div className="eyebrow">Exercise</div>
              <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: 8 }}>{exercise.title || 'Untitled Exercise'}</h2>
              <p style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', lineHeight: 1.6, marginBottom: 12 }}>{exercise.prompt || exercise.description}</p>

              {exercise.expected_test && (
                <details style={{ marginBottom: 8 }}>
                  <summary style={{ fontSize: '0.78rem', color: 'var(--txt-mut)', cursor: 'pointer' }}>View test scaffold</summary>
                  <pre style={{ fontSize: '0.75rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', padding: 12, background: 'rgba(255,255,255,0.03)', borderRadius: 8, marginTop: 8, overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                    {exercise.expected_test}
                  </pre>
                </details>
              )}
            </div>

            <div className="glass-card-solid" style={{ padding: 16, flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Your Solution</p>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={submitCode} disabled={loading}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, border: 'none', background: 'var(--photon)', color: '#050608', fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer', opacity: loading ? 0.7 : 1 }}>
                    <Send size={14} /> {loading ? 'Submitting…' : 'Submit'}
                  </button>
                  <button onClick={nextLesson} disabled={loading}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.82rem', cursor: 'pointer' }}>
                    <ChevronRight size={14} /> Next Lesson
                  </button>
                </div>
              </div>
              <textarea value={code} onChange={e => setCode(e.target.value)}
                placeholder="Write your Python solution here…"
                style={{ width: '100%', height: 220, background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: '#4ade80', resize: 'vertical', outline: 'none', boxSizing: 'border-box' }} />
            </div>

            {result && (
              <div className="glass-card-solid" style={{ padding: 16, borderLeft: `3px solid ${result.passed ? '#22c55e' : '#ef4444'}` }}>
                <p style={{ fontSize: '0.78rem', fontWeight: 600, color: result.passed ? '#22c55e' : '#ef4444', marginBottom: 8 }}>
                  {result.passed ? '✓ PASSED' : result.error ? '✗ ERROR' : '✗ FAILED'}
                </p>
                {result.hint && <p style={{ fontSize: '0.82rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>{result.hint}</p>}
                {result.error && <pre style={{ fontSize: '0.78rem', fontFamily: 'JetBrains Mono,monospace', color: '#f87171', whiteSpace: 'pre-wrap' }}>{result.error}</pre>}
                {result.recommendation && (
                  <p style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', marginTop: 8 }}>
                    Recommendation: {result.recommendation}
                  </p>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="glass-card-solid" style={{ padding: 32, textAlign: 'center' }}>
            <BookOpen size={32} color="var(--txt-mut)" style={{ marginBottom: 12 }} />
            <p style={{ color: 'var(--txt-sec)', fontSize: '0.9rem', marginBottom: 8 }}>No active lesson.</p>
            <p style={{ color: 'var(--txt-mut)', fontSize: '0.82rem' }}>Enter a topic in the sidebar to start a lesson.</p>
          </div>
        )}
      </div>
    </div>
  )
}
