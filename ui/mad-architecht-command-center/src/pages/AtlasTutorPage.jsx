import { useState, useEffect, useRef } from 'react'
import { BookOpen, Send, ChevronRight, MessageSquare } from 'lucide-react'
import { api } from '../api/client'
import { useInterval } from '../hooks/useApi'

export default function AtlasTutorPage() {
  const [atlasState, setAtlasState] = useState(null)
  const [topic, setTopic]           = useState('')
  const [code, setCode]             = useState('')
  const [result, setResult]         = useState(null)
  const [loading, setLoading]       = useState(false)
  const [chatInput, setChatInput]   = useState('')
  const [chatBusy, setChatBusy]     = useState(false)
  const [models, setModels]         = useState(null)
  const [chatModel, setChatModel]   = useState('')
  const chatBottomRef = useRef(null)

  const loadState = async () => {
    try {
      const s = await api('/atlas/status')
      setAtlasState(s)
      if (s.current_exercise?.starter_files) {
        const first = Object.values(s.current_exercise.starter_files)[0] || ''
        if (!code.trim()) setCode(first)
      }
    } catch (_) {}
  }

  useEffect(() => { loadState() }, [])
  useInterval(loadState, 15000)

  useEffect(() => {
    api('/models').then(m => {
      setModels(m)
      if (m?.active_model) setChatModel(m.active_model)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [atlasState?.chat_history])

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

  const sendChat = async () => {
    if (!chatInput.trim() || chatBusy) return
    const msg = chatInput.trim()
    setChatInput('')
    setChatBusy(true)
    try {
      const res = await api('/atlas/chat', {
        method: 'POST',
        body: { message: msg, model: chatModel || undefined },
      })
      if (res.chat_history) {
        setAtlasState(prev => ({ ...(prev || {}), chat_history: res.chat_history }))
      }
    } catch (e) {
      setAtlasState(prev => ({
        ...(prev || {}),
        chat_history: [
          ...((prev && Array.isArray(prev.chat_history)) ? prev.chat_history : []),
          { role: 'assistant', message: `Error: ${e.message}` },
        ],
      }))
    } finally {
      setChatBusy(false)
    }
  }

  const exercise       = atlasState?.current_exercise
  const curriculum     = atlasState?.curriculum
  const modules        = curriculum?.modules || []
  const currentLessonId = atlasState?.lesson_id
  const chatHistory    = Array.isArray(atlasState?.chat_history) ? atlasState.chat_history : []

  return (
    <div className="page-enter" style={{ padding: 20, display: 'flex', gap: 16, height: 'calc(100vh - 92px)', overflow: 'hidden' }}>

      {/* Left: Curriculum (240px) */}
      <div style={{ width: 240, flexShrink: 0, overflowY: 'auto' }}>
        <div className="glass-card-solid" style={{ padding: 16 }}>
          <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 12, fontWeight: 600 }}>
            Curriculum
          </p>
          {modules.length > 0 ? modules.map((mod, mi) => (
            <div key={mi} style={{ marginBottom: 12 }}>
              <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--txt-pri)', marginBottom: 4 }}>
                {mod.title || mod.module_title || `Module ${mi + 1}`}
              </p>
              {(mod.lessons || []).map((lesson, li) => (
                <div key={li} style={{
                  padding: '5px 10px', borderRadius: 6, marginBottom: 2,
                  background: lesson.lesson_id === currentLessonId ? 'rgba(77,166,255,0.12)' : 'transparent',
                  borderLeft: `2px solid ${lesson.lesson_id === currentLessonId ? 'var(--photon)' : 'transparent'}`,
                  fontSize: '0.76rem',
                  color: lesson.lesson_id === currentLessonId ? 'var(--photon)' : 'var(--txt-sec)',
                }}>
                  {lesson.title || lesson.lesson_title || `Lesson ${li + 1}`}
                </div>
              ))}
            </div>
          )) : (
            <p style={{ color: 'var(--txt-mut)', fontSize: '0.8rem' }}>No curriculum loaded.</p>
          )}

          <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>New Lesson</p>
            <input value={topic} onChange={e => setTopic(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && startLesson()}
              placeholder="e.g. Python for loops"
              style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.8rem', outline: 'none', marginBottom: 8, boxSizing: 'border-box' }} />
            <button onClick={startLesson} disabled={loading}
              style={{ width: '100%', padding: '8px', borderRadius: 8, border: 'none', background: 'var(--photon)', color: '#050608', fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer', opacity: loading ? 0.7 : 1 }}>
              {loading ? 'Loading…' : 'Start Lesson'}
            </button>
          </div>
        </div>
      </div>

      {/* Center: Exercise + Editor */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, overflowY: 'auto' }}>
        {exercise ? (
          <>
            <div className="glass-card-solid" style={{ padding: 18, flexShrink: 0 }}>
              <div className="eyebrow">Exercise</div>
              <h2 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: 8 }}>{exercise.title || 'Untitled Exercise'}</h2>
              <p style={{ fontSize: '0.83rem', color: 'var(--txt-sec)', lineHeight: 1.6, marginBottom: 8 }}>{exercise.prompt || exercise.description}</p>
              {exercise.expected_test && (
                <details>
                  <summary style={{ fontSize: '0.76rem', color: 'var(--txt-mut)', cursor: 'pointer' }}>View test scaffold</summary>
                  <pre style={{ fontSize: '0.73rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', padding: 10, background: 'rgba(255,255,255,0.03)', borderRadius: 8, marginTop: 8, overflowX: 'auto', whiteSpace: 'pre-wrap' }}>
                    {exercise.expected_test}
                  </pre>
                </details>
              )}
            </div>

            <div className="glass-card-solid" style={{ padding: 14, flex: 1, display: 'flex', flexDirection: 'column', minHeight: 280 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Your Solution</p>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={submitCode} disabled={loading}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 8, border: 'none', background: 'var(--photon)', color: '#050608', fontWeight: 600, fontSize: '0.8rem', cursor: 'pointer', opacity: loading ? 0.7 : 1 }}>
                    <Send size={13} /> {loading ? 'Submitting…' : 'Submit'}
                  </button>
                  <button onClick={nextLesson} disabled={loading}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.8rem', cursor: 'pointer' }}>
                    <ChevronRight size={13} /> Next
                  </button>
                </div>
              </div>
              <textarea value={code} onChange={e => setCode(e.target.value)}
                placeholder="Write your Python solution here…"
                style={{ flex: 1, minHeight: 200, background: 'rgba(5,6,8,0.8)', border: '1px solid var(--border)', borderRadius: 8, padding: 12, fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: '#4ade80', resize: 'vertical', outline: 'none', boxSizing: 'border-box', width: '100%' }} />
            </div>

            {result && (
              <div className="glass-card-solid" style={{ padding: 14, flexShrink: 0, borderLeft: `3px solid ${result.passed ? '#22c55e' : '#ef4444'}` }}>
                <p style={{ fontSize: '0.78rem', fontWeight: 600, color: result.passed ? '#22c55e' : '#ef4444', marginBottom: 6 }}>
                  {result.passed ? '✓ PASSED' : result.error ? '✗ ERROR' : '✗ FAILED'}
                </p>
                {result.hint && <p style={{ fontSize: '0.82rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{result.hint}</p>}
                {result.error && <pre style={{ fontSize: '0.76rem', fontFamily: 'JetBrains Mono,monospace', color: '#f87171', whiteSpace: 'pre-wrap' }}>{result.error}</pre>}
                {result.recommendation && (
                  <p style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', marginTop: 6 }}>
                    {result.recommendation}
                  </p>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="glass-card-solid" style={{ padding: 32, textAlign: 'center', flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            <BookOpen size={32} color="var(--txt-mut)" style={{ marginBottom: 12 }} />
            <p style={{ color: 'var(--txt-sec)', fontSize: '0.9rem', marginBottom: 8 }}>No active lesson.</p>
            <p style={{ color: 'var(--txt-mut)', fontSize: '0.82rem' }}>Enter a topic in the sidebar to start a lesson.</p>
          </div>
        )}
      </div>

      {/* Right: Chat (280px) */}
      <div style={{ width: 280, flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
        <div className="glass-card-solid" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <MessageSquare size={14} color="var(--violet)" />
              <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--violet)', textTransform: 'uppercase', letterSpacing: '0.12em', margin: 0 }}>ATLAS Tutor</p>
            </div>
            <select value={chatModel} onChange={e => setChatModel(e.target.value)}
              className="filter-select"
              style={{ fontSize: '0.7rem', padding: '3px 6px' }}>
              {(models?.models || []).map(m => (
                <option key={m.id} value={m.id}>{m.id}{m.installed === false ? ' ✗' : ''}</option>
              ))}
              {!models?.models?.length && <option value="">default</option>}
            </select>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {chatHistory.length === 0 ? (
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.8rem', textAlign: 'center', marginTop: 20, lineHeight: 1.6 }}>
                Ask ATLAS for hints, debugging help, or lesson explanations.
              </div>
            ) : chatHistory.slice(-40).map((msg, i) => (
              <div key={i}>
                <p style={{ fontSize: '0.68rem', color: msg.role === 'user' ? 'var(--photon)' : 'var(--cyan)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                  {msg.role === 'user' ? 'You' : 'ATLAS'}
                </p>
                <p style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', whiteSpace: 'pre-wrap', lineHeight: 1.5, margin: 0 }}>{msg.message}</p>
              </div>
            ))}
            {chatBusy && (
              <div style={{ display: 'flex', gap: 4, padding: '4px 0' }}>
                {[0, 1, 2].map(i => (
                  <span key={i} className="thinking-dot" style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--violet)', display: 'inline-block' }} />
                ))}
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8, flexShrink: 0 }}>
            <input
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat() } }}
              placeholder="Ask ATLAS Tutor…"
              style={{ flex: 1, padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.8rem', outline: 'none', fontFamily: 'Inter,sans-serif' }}
            />
            <button onClick={sendChat} disabled={chatBusy}
              style={{ padding: '7px 12px', borderRadius: 8, border: 'none', background: chatBusy ? 'rgba(180,124,255,0.3)' : 'var(--violet)', color: '#fff', fontWeight: 700, cursor: chatBusy ? 'not-allowed' : 'pointer', fontSize: '0.8rem' }}>
              {chatBusy ? '…' : '↑'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}