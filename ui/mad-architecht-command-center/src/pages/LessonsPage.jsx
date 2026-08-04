import { useState, useEffect } from 'react'
import { BookOpen, Send, ChevronRight, ExternalLink } from 'lucide-react'
import { api } from '../api/client'

const FALLBACK_MODULE_TRACKS = [
  { id: 'wilderness-survival', label: 'Wilderness Navigation + Survival', topic: 'Wilderness navigation survival and safety fundamentals', summary: 'Field-ready navigation, shelter, water, and risk management fundamentals.' },
  { id: 'hunting-fishing', label: 'Hunting + Fishing', topic: 'Hunting and fishing safety ethics and field basics', summary: 'Ethical harvest, gear discipline, and field-readiness basics for outdoor food systems.' },
  { id: 'ham-radio', label: 'Ham Radio', topic: 'Ham radio fundamentals call signs and emergency comms basics', summary: 'Introductory radio literacy for disciplined communication and emergency readiness.' },
  { id: 'emt-emergency-management', label: 'EMT + Emergency Mgmt', topic: 'EMT and emergency management triage and incident fundamentals', summary: 'Structured emergency response thinking with triage, ICS awareness, and scene safety.' },
  { id: 'horticulture-weather', label: 'Horticulture + Weather', topic: 'Horticulture botany and weather pattern literacy basics', summary: 'Plant care, growth cycles, and weather-aware decision-making for practical stewardship.' },
]

export default function LessonsPage({ setPage }) {
  const [atlasState, setAtlasState] = useState(null)
  const [topic, setTopic]           = useState('')
  const [code, setCode]             = useState('')
  const [result, setResult]         = useState(null)
  const [loading, setLoading]       = useState(false)
  const [chatInput, setChatInput]   = useState('')
  const [chatBusy, setChatBusy]     = useState(false)
  const [models, setModels]         = useState(null)
  const [chatModel, setChatModel]   = useState('')
  const [moduleCatalog, setModuleCatalog] = useState(FALLBACK_MODULE_TRACKS)

  const loadState = async () => {
    try {
      const s = await api('/atlas/status')
      setAtlasState(s)
      if (Array.isArray(s?.available_modules) && s.available_modules.length) {
        setModuleCatalog(s.available_modules)
      }
      if (s.current_exercise?.starter_files) {
        const files = s.current_exercise.starter_files
        const first = Object.values(files)[0] || ''
        if (!code.trim()) {
          setCode(first)
        }
      }
    } catch (_) {}
  }

  useEffect(() => { loadState() }, [])
  useEffect(() => {
    api('/atlas/modules').then((res) => {
      if (Array.isArray(res?.modules) && res.modules.length) {
        setModuleCatalog(res.modules)
      }
    }).catch(() => {})
  }, [])
  useEffect(() => {
    api('/models').then((m) => {
      setModels(m)
      if (m?.active_model) {
        setChatModel(m.active_model)
      }
    }).catch(() => {})
  }, [])

  const startLesson = async (overrideTopic, moduleTrack = null) => {
    const requestedTopic = (overrideTopic || topic).trim()
    if (!requestedTopic) return
    setLoading(true)
    setResult(null)
    try {
      const res = await api('/atlas/lesson', {
        method: 'POST',
        body: {
          topic: requestedTopic,
          module_id: moduleTrack?.id,
        },
      })
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

  const sendTutorChat = async () => {
    if (!chatInput.trim()) return
    setChatBusy(true)
    try {
      const res = await api('/atlas/chat', {
        method: 'POST',
        body: {
          message: chatInput,
          model: chatModel || undefined,
        },
      })
      setChatInput('')
      if (res.chat_history) {
        setAtlasState((prev) => ({ ...(prev || {}), chat_history: res.chat_history }))
      }
    } catch (e) {
      setAtlasState((prev) => ({
        ...(prev || {}),
        chat_history: [
          ...((prev && Array.isArray(prev.chat_history)) ? prev.chat_history : []),
          { role: 'assistant', message: `Tutor chat error: ${e.message}` },
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
  const activeModule   = atlasState?.active_module

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

          <div style={{ marginTop: 14, borderTop: '1px solid var(--border)', paddingTop: 14 }}>
            <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>
              Focused Module Quick Starts
            </p>
            <div style={{ display: 'grid', gap: 6 }}>
              {moduleCatalog.map((track) => {
                const isActive = activeModule?.id === track.id
                return (
                  <button
                    key={track.id || track.label}
                    onClick={() => {
                      setTopic(track.topic)
                      startLesson(track.topic, track)
                    }}
                    disabled={loading}
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '9px 10px',
                      borderRadius: 8,
                      border: `1px solid ${isActive ? 'rgba(77,166,255,0.35)' : 'var(--border)'}`,
                      background: isActive ? 'rgba(77,166,255,0.08)' : 'rgba(255,255,255,0.03)',
                      color: 'var(--txt-sec)',
                      fontSize: '0.78rem',
                      cursor: 'pointer',
                      opacity: loading ? 0.7 : 1,
                    }}
                  >
                    <div style={{ fontWeight: 600, color: isActive ? 'var(--photon)' : 'var(--txt-pri)', marginBottom: 3 }}>
                      {track.label}
                    </div>
                    {track.summary && (
                      <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', lineHeight: 1.4 }}>
                        {track.summary}
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* ATLAS Tutor link */}
          {setPage && (
            <div style={{ marginTop: 12 }}>
              <button onClick={() => setPage('atlas')}
                style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '8px', borderRadius: 8, border: '1px solid rgba(180,124,255,0.3)', background: 'rgba(180,124,255,0.08)', color: 'var(--violet)', fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer' }}>
                <ExternalLink size={13} /> Open Full ATLAS Tutor
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0, overflowY: 'auto' }}>
        {exercise ? (
          <>
            <div className="glass-card-solid" style={{ padding: 20 }}>
              <div className="eyebrow">Exercise</div>
              {activeModule?.label && (
                <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--photon)', marginBottom: 8 }}>
                  {activeModule.label}
                </p>
              )}
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

            <div className="glass-card-solid" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <p style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>
                  ATLAS Tutor Chat
                </p>
                <select
                  value={chatModel}
                  onChange={(e) => setChatModel(e.target.value)}
                  className="filter-select"
                  style={{ fontSize: '0.76rem', padding: '4px 8px' }}
                >
                  {(models?.models || []).map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.id}{m.installed === false ? ' (not installed)' : ''}
                    </option>
                  ))}
                  {!models?.models?.length && <option value="">default model</option>}
                </select>
              </div>
              <div style={{ maxHeight: 220, overflowY: 'auto', padding: 10, background: 'rgba(0,0,0,0.25)', borderRadius: 8, border: '1px solid var(--border)', marginBottom: 10 }}>
                {chatHistory.length ? chatHistory.slice(-20).map((msg, idx) => (
                  <div key={idx} style={{ marginBottom: 8 }}>
                    <p style={{ fontSize: '0.72rem', color: msg.role === 'user' ? 'var(--photon)' : 'var(--cyan)', marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                      {msg.role === 'user' ? 'You' : 'ATLAS Tutor'}
                    </p>
                    <p style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', whiteSpace: 'pre-wrap', lineHeight: 1.5 }}>{msg.message}</p>
                  </div>
                )) : (
                  <p style={{ color: 'var(--txt-mut)', fontSize: '0.82rem' }}>
                    Ask ATLAS for hints, debugging help, or lesson explanations.
                  </p>
                )}
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask ATLAS Tutor…"
                  style={{ flex: 1, padding: '9px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)', fontSize: '0.82rem', outline: 'none' }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault()
                      sendTutorChat()
                    }
                  }}
                />
                <button
                  onClick={sendTutorChat}
                  disabled={chatBusy}
                  style={{ padding: '8px 14px', borderRadius: 8, border: 'none', background: 'var(--cyan)', color: '#050608', fontWeight: 700, cursor: 'pointer', opacity: chatBusy ? 0.7 : 1 }}
                >
                  {chatBusy ? 'Sending…' : 'Send'}
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="glass-card-solid" style={{ padding: 32, textAlign: 'center' }}>
            <BookOpen size={32} color="var(--txt-mut)" style={{ marginBottom: 12 }} />
            <p style={{ color: 'var(--txt-sec)', fontSize: '0.9rem', marginBottom: 8 }}>No active lesson.</p>
            <p style={{ color: 'var(--txt-mut)', fontSize: '0.82rem' }}>Enter a topic or launch one of the focused module tracks from the sidebar.</p>
          </div>
        )}
      </div>
    </div>
  )
}