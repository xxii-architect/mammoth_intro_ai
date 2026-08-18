import { useState, useEffect } from 'react'
import { BookOpen, Send, ChevronRight, ExternalLink, GraduationCap, Flame, CheckCircle2, Circle, ChevronDown, ChevronUp, Sparkles } from 'lucide-react'
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [expandedModules, setExpandedModules] = useState({})

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
        if (!code.trim()) setCode(first)
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
      if (m?.active_model) setChatModel(m.active_model)
    }).catch(() => {})
  }, [])

  const startLesson = async (overrideTopic, moduleTrack = null) => {
    const requestedTopic = (overrideTopic || topic).trim()
    if (!requestedTopic) return
    setLoading(true)
    setResult(null)
    setCode('')
    try {
      const res = await api('/atlas/lesson', {
        method: 'POST',
        body: { topic: requestedTopic, module_id: moduleTrack?.id },
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
        body: { message: chatInput, model: chatModel || undefined },
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

  const exercise        = atlasState?.current_exercise
  const curriculum      = atlasState?.curriculum
  const modules         = curriculum?.modules || []
  const currentLessonId = atlasState?.lesson_id
  const chatHistory     = Array.isArray(atlasState?.chat_history) ? atlasState.chat_history : []
  const activeModule    = atlasState?.active_module

  const toggleModule = (id) => setExpandedModules(prev => ({ ...prev, [id]: !prev[id] }))

  return (
    <div className="page-enter" style={{ padding: 24, display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)', overflow: 'hidden' }}>
      {/* Hero header */}
      <div style={{ marginBottom: 16, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <h1 style={{ fontSize: '1.1rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
            <GraduationCap size={20} color="var(--photon)" /> Lessons
          </h1>
          <p style={{ fontSize: '0.78rem', color: 'var(--txt-sec)', margin: '4px 0 0' }}>
            Interactive operator curriculum · ATLAS-powered tutor
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {activeModule && (
            <div style={{ padding: '5px 12px', borderRadius: 999, background: 'rgba(0,245,212,0.1)', border: '1px solid rgba(0,245,212,0.3)', fontSize: '0.72rem', color: 'var(--cyan)', fontWeight: 600 }}>
              {activeModule.label || activeModule.id}
            </div>
          )}
          {setPage && (
            <button onClick={() => setPage('atlas')}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, border: '1px solid rgba(180,124,255,0.3)', background: 'rgba(180,124,255,0.08)', color: 'var(--violet)', fontWeight: 600, fontSize: '0.78rem', cursor: 'pointer' }}>
              <ExternalLink size={13} /> Full ATLAS Tutor
            </button>
          )}
        </div>
      </div>

      <div style={{ flex: 1, display: 'flex', gap: 16, minHeight: 0 }}>
        {/* Left sidebar */}
        <div style={{ width: sidebarCollapsed ? 40 : 240, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 10, transition: 'width 0.2s' }}>
          <button onClick={() => setSidebarCollapsed(c => !c)} title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            style={{ width: '100%', padding: '6px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ChevronRight size={14} style={{ transform: sidebarCollapsed ? 'none' : 'rotate(180deg)', transition: 'transform 0.2s' }} />
          </button>

          {!sidebarCollapsed && (
            <div style={{ overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10, flex: 1 }}>
              {/* Quick start input */}
              <div className="glass-card-solid" style={{ padding: 14 }}>
                <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 10, fontWeight: 600 }}>Quick Start</p>
                <input
                  value={topic}
                  onChange={e => setTopic(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && startLesson()}
                  placeholder="e.g. Python for loops"
                  style={{ width: '100%', padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.8rem', outline: 'none', marginBottom: 8, boxSizing: 'border-box' }}
                />
                <button onClick={() => startLesson()} disabled={loading || !topic.trim()}
                  style={{ width: '100%', padding: '8px', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', fontWeight: 700, fontSize: '0.8rem', cursor: 'pointer', opacity: (loading || !topic.trim()) ? 0.5 : 1 }}>
                  {loading ? 'Loading…' : 'Start Lesson'}
                </button>
              </div>

              {/* Curriculum tree — clickable lessons */}
              {modules.length > 0 && (
                <div className="glass-card-solid" style={{ padding: 14 }}>
                  <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 10, fontWeight: 600 }}>Curriculum</p>
                  {modules.map((mod, mi) => {
                    const modId = mod.id || `mod-${mi}`
                    const isExpanded = expandedModules[modId] !== false // default expanded
                    return (
                      <div key={modId} style={{ marginBottom: 10 }}>
                        <button onClick={() => toggleModule(modId)}
                          style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'none', border: 'none', cursor: 'pointer', padding: '4px 0', marginBottom: 4 }}>
                          <span style={{ fontSize: '0.76rem', fontWeight: 700, color: 'var(--txt-pri)', textAlign: 'left' }}>{mod.title || mod.module_title || `Module ${mi+1}`}</span>
                          {isExpanded ? <ChevronUp size={12} color="var(--txt-mut)" /> : <ChevronDown size={12} color="var(--txt-mut)" />}
                        </button>
                        {isExpanded && (mod.lessons || []).map((lesson, li) => {
                          const isCurrent = lesson.lesson_id === currentLessonId
                          const isDone = lesson.completed
                          return (
                            <button
                              key={lesson.lesson_id || li}
                              onClick={() => startLesson(lesson.title || lesson.lesson_title || lesson.topic, mod)}
                              disabled={loading}
                              style={{
                                display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left',
                                padding: '7px 10px', borderRadius: 6, marginBottom: 2, cursor: 'pointer', border: 'none',
                                background: isCurrent ? 'rgba(77,166,255,0.12)' : 'transparent',
                                borderLeft: `2px solid ${isCurrent ? 'var(--photon)' : 'transparent'}`,
                                transition: 'all 0.15s',
                              }}
                            >
                              {isDone ? <CheckCircle2 size={12} color="#22c55e" style={{ flexShrink: 0 }} /> : <Circle size={12} color="var(--txt-mut)" style={{ flexShrink: 0 }} />}
                              <span style={{ fontSize: '0.75rem', color: isCurrent ? 'var(--photon)' : 'var(--txt-sec)', fontWeight: isCurrent ? 700 : 400, lineHeight: 1.3 }}>
                                {lesson.title || lesson.lesson_title || `Lesson ${li+1}`}
                              </span>
                            </button>
                          )
                        })}
                      </div>
                    )
                  })}
                </div>
              )}

              {/* Module tracks */}
              <div className="glass-card-solid" style={{ padding: 14 }}>
                <p style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.16em', color: 'var(--txt-sec)', marginBottom: 10, fontWeight: 600 }}>Module Tracks</p>
                <div style={{ display: 'grid', gap: 6 }}>
                  {moduleCatalog.map((track) => {
                    const isActive = activeModule?.id === track.id
                    return (
                      <button
                        key={track.id || track.label}
                        onClick={() => { setTopic(track.topic); startLesson(track.topic, track) }}
                        disabled={loading}
                        style={{
                          width: '100%', textAlign: 'left', padding: '9px 10px', borderRadius: 8,
                          border: `1px solid ${isActive ? 'rgba(0,245,212,0.35)' : 'var(--border)'}`,
                          background: isActive ? 'rgba(0,245,212,0.08)' : 'rgba(255,255,255,0.03)',
                          cursor: 'pointer', opacity: loading ? 0.6 : 1, transition: 'all 0.15s',
                        }}
                      >
                        <div style={{ fontWeight: 600, color: isActive ? 'var(--cyan)' : 'var(--txt-pri)', marginBottom: 3, fontSize: '0.76rem', display: 'flex', alignItems: 'center', gap: 6 }}>
                          {isActive && <Flame size={12} color="var(--cyan)" />}
                          {track.label}
                        </div>
                        {track.summary && (
                          <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', lineHeight: 1.4 }}>
                            {track.summary}
                          </div>
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Main content area */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, overflowY: 'auto' }}>
          {exercise ? (
            <>
              {/* Exercise card */}
              <div className="glass-card-solid" style={{ padding: 20, borderLeft: '3px solid var(--photon)', flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                      <span style={{ fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--photon)', fontWeight: 700 }}>Exercise</span>
                      {activeModule?.label && (
                        <span style={{ fontSize: '0.66rem', color: 'var(--txt-mut)' }}>· {activeModule.label}</span>
                      )}
                    </div>
                    <h2 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: 8, color: 'var(--txt-pri)' }}>{exercise.title || 'Untitled Exercise'}</h2>
                    <p style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', lineHeight: 1.65, margin: 0 }}>{exercise.prompt || exercise.description}</p>
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                    <button onClick={submitCode} disabled={loading}
                      style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', fontWeight: 700, fontSize: '0.82rem', cursor: 'pointer', opacity: loading ? 0.7 : 1 }}>
                      <Send size={13} /> {loading ? 'Submitting…' : 'Submit'}
                    </button>
                    <button onClick={nextLesson} disabled={loading}
                      style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.82rem', cursor: 'pointer', fontWeight: 600 }}>
                      <ChevronRight size={14} /> Next
                    </button>
                  </div>
                </div>

                {exercise.expected_test && (
                  <details style={{ marginTop: 14 }}>
                    <summary style={{ fontSize: '0.76rem', color: 'var(--txt-mut)', cursor: 'pointer' }}>View test scaffold</summary>
                    <pre style={{ fontSize: '0.74rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', padding: 12, background: 'rgba(0,0,0,0.25)', borderRadius: 8, marginTop: 8, overflowX: 'auto', whiteSpace: 'pre-wrap', border: '1px solid var(--border)' }}>
                      {exercise.expected_test}
                    </pre>
                  </details>
                )}
              </div>

              {/* Code editor */}
              <div className="glass-card-solid" style={{ padding: 16, flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                  <p style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.14em', margin: 0 }}>Your Solution</p>
                  <code style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>Python</code>
                </div>
                <textarea value={code} onChange={e => setCode(e.target.value)}
                  placeholder="Write your solution here…"
                  style={{ width: '100%', height: 200, background: '#050608', border: '1px solid var(--border)', borderRadius: 8, padding: 12, fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: '#4ade80', resize: 'vertical', outline: 'none', boxSizing: 'border-box', lineHeight: 1.8 }} />
              </div>

              {/* Result feedback */}
              {result && (
                <div className="glass-card-solid" style={{ padding: 16, borderLeft: `3px solid ${result.passed ? '#22c55e' : '#ef4444'}`, flexShrink: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                    {result.passed ? <CheckCircle2 size={16} color="#22c55e" /> : null}
                    <p style={{ fontSize: '0.82rem', fontWeight: 700, color: result.passed ? '#22c55e' : result.error ? '#f87171' : '#ef4444', margin: 0 }}>
                      {result.passed ? '✓ Passed' : result.error ? 'Error' : '✗ Failed'}
                    </p>
                  </div>
                  {result.hint && <p style={{ fontSize: '0.82rem', color: 'var(--txt-sec)', lineHeight: 1.65, margin: 0 }}>{result.hint}</p>}
                  {result.error && <pre style={{ fontSize: '0.76rem', fontFamily: 'JetBrains Mono,monospace', color: '#f87171', whiteSpace: 'pre-wrap', margin: 0 }}>{result.error}</pre>}
                  {result.recommendation && (
                    <p style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', marginTop: 8, margin: '8px 0 0' }}>
                      Recommendation: {result.recommendation}
                    </p>
                  )}
                </div>
              )}

              {/* Tutor chat */}
              <div className="glass-card-solid" style={{ padding: 16, flexShrink: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                  <p style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--txt-sec)', textTransform: 'uppercase', letterSpacing: '0.14em', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <Sparkles size={13} color="var(--violet)" /> ATLAS Tutor Chat
                  </p>
                  <select
                    value={chatModel}
                    onChange={(e) => setChatModel(e.target.value)}
                    className="filter-select"
                    style={{ fontSize: '0.74rem', padding: '4px 8px' }}
                  >
                    {(models?.models || []).map((m) => (
                      <option key={m.id} value={m.id}>{m.id}{m.installed === false ? ' (not installed)' : ''}</option>
                    ))}
                    {!models?.models?.length && <option value="">default model</option>}
                  </select>
                </div>
                <div style={{ maxHeight: 200, overflowY: 'auto', padding: 10, background: 'rgba(0,0,0,0.25)', borderRadius: 8, border: '1px solid var(--border)', marginBottom: 10 }}>
                  {chatHistory.length ? chatHistory.slice(-20).map((msg, idx) => (
                    <div key={idx} style={{ marginBottom: 10 }}>
                      <p style={{ fontSize: '0.68rem', color: msg.role === 'user' ? 'var(--photon)' : 'var(--cyan)', marginBottom: 3, textTransform: 'uppercase', letterSpacing: '0.1em', fontWeight: 700 }}>
                        {msg.role === 'user' ? 'You' : 'ATLAS Tutor'}
                      </p>
                      <p style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', whiteSpace: 'pre-wrap', lineHeight: 1.6, margin: 0 }}>{msg.message}</p>
                    </div>
                  )) : (
                    <p style={{ color: 'var(--txt-mut)', fontSize: '0.82rem', margin: 0 }}>Ask ATLAS for hints, debugging help, or explanations.</p>
                  )}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <input
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Ask ATLAS Tutor…"
                    style={{ flex: 1, padding: '9px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(0,245,212,0.04)', color: 'var(--txt-pri)', fontSize: '0.82rem', outline: 'none' }}
                    onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); sendTutorChat() } }}
                  />
                  <button
                    onClick={sendTutorChat}
                    disabled={chatBusy}
                    style={{ padding: '8px 16px', borderRadius: 8, border: 'none', background: 'linear-gradient(90deg, var(--violet), var(--photon))', color: '#050608', fontWeight: 700, fontSize: '0.82rem', cursor: 'pointer', opacity: chatBusy ? 0.7 : 1 }}
                  >
                    {chatBusy ? '…' : 'Send'}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="glass-card-solid" style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', gap: 16 }}>
              <div style={{ padding: 20, borderRadius: '50%', background: 'rgba(77,166,255,0.08)', border: '1px solid rgba(77,166,255,0.2)' }}>
                <GraduationCap size={36} color="var(--photon)" />
              </div>
              <div>
                <p style={{ color: 'var(--txt-pri)', fontSize: '1rem', fontWeight: 600, marginBottom: 8 }}>No active lesson</p>
                <p style={{ color: 'var(--txt-mut)', fontSize: '0.84rem', maxWidth: 380, lineHeight: 1.6 }}>
                  Enter a custom topic or pick a module track from the sidebar to begin your first lesson with ATLAS.
                </p>
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center' }}>
                {FALLBACK_MODULE_TRACKS.slice(0, 3).map(t => (
                  <button key={t.id} onClick={() => { setTopic(t.topic); startLesson(t.topic, t) }} disabled={loading}
                    style={{ padding: '9px 16px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.8rem', cursor: 'pointer', fontWeight: 600, transition: 'all 0.15s' }}>
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}