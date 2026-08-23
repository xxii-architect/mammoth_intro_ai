import { useState, useEffect, useRef } from 'react'
import { BookOpen, Send, ChevronRight, MessageSquare } from 'lucide-react'
import { api } from '../api/client'
import { useInterval } from '../hooks/useApi'
import RuntimeStatusBanner from '../components/RuntimeStatusBanner'

export default function AtlasTutorPage() {
  const [atlasState, setAtlasState] = useState(null)
  const [topic, setTopic]           = useState('')
  const [code, setCode]             = useState('')
  const [result, setResult]         = useState(null)
  const [loading, setLoading]       = useState(false)
  const [chatInput, setChatInput]   = useState('')
  const [chatBusy, setChatBusy]     = useState(false)
  const [chatMode, setChatMode]     = useState('assistant')
  const [models, setModels]         = useState(null)
  const [chatModel, setChatModel]   = useState('')
  const [studyAid, setStudyAid]     = useState(null)
  const [evalSummary, setEvalSummary] = useState(null)
  const [atlasPlanProfile, setAtlasPlanProfile] = useState('coding')
  const [onboardingDraft, setOnboardingDraft] = useState({
    experience_level: 'unknown',
    preferred_pacing: 'gentle',
    learning_style: 'guided',
    goals: '',
    focus_areas: '',
  })
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' ? window.innerWidth < 768 : false)
  const [showLeftPanel, setShowLeftPanel] = useState(() => typeof window !== 'undefined' ? window.innerWidth >= 768 : true)
  const [showRightPanel, setShowRightPanel] = useState(() => typeof window !== 'undefined' ? window.innerWidth >= 768 : true)
  const chatBottomRef = useRef(null)
  const onboardingSeededRef = useRef(false)

  useEffect(() => {
    const onResize = () => {
      const mobile = window.innerWidth < 768
      setIsMobile(mobile)
      if (mobile) {
        setShowLeftPanel(false)
        setShowRightPanel(false)
      }
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

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
  }, [atlasState?.chat_history, atlasState?.assistant_chat_history])

  useEffect(() => {
    const onboarding = atlasState?.learner_model?.onboarding
    if (!onboarding || onboardingSeededRef.current) return
    setOnboardingDraft({
      experience_level: onboarding.experience_level || 'unknown',
      preferred_pacing: onboarding.preferred_pacing || 'gentle',
      learning_style: onboarding.learning_style || 'guided',
      goals: Array.isArray(onboarding.goals) ? onboarding.goals.join(', ') : '',
      focus_areas: Array.isArray(onboarding.focus_areas) ? onboarding.focus_areas.join(', ') : '',
    })
    onboardingSeededRef.current = true
  }, [atlasState?.learner_model?.onboarding])

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
      const res = await api('/atlas/submit', { method: 'POST', body: { code, regenerate_on_fail: false } })
      setResult({ ...(res.result || res), adaptive_feedback: res.adaptive_feedback || null })
      setAtlasState(prev => ({
        ...(prev || {}),
        learner_context: res.learner_context || prev?.learner_context,
        current_exercise: res.current_exercise || prev?.current_exercise,
      }))
      if (res?.regenerated_exercise?.starter_files) {
        const first = Object.values(res.regenerated_exercise.starter_files)[0] || ''
        if (first) setCode(first)
      }
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
      setStudyAid(null)
    } catch (_) {}
    setLoading(false)
  }

  const prevLesson = async () => {
    setLoading(true)
    try {
      const res = await api('/atlas/back', { method: 'POST', body: {} })
      if (res && res.status === 'ok') {
        setAtlasState(prev => ({ ...(prev || {}), ...res }))
      }
      await loadState()
      setResult(null)
      setStudyAid(null)
    } catch (_) {}
    setLoading(false)
  }

  const loadRecap = async () => {
    try {
      const res = await api('/atlas/recap')
      setStudyAid({ type: 'recap', data: res.recap })
    } catch (e) {
      setStudyAid({ type: 'recap', data: `Error: ${e.message}` })
    }
  }

  const loadQuiz = async () => {
    try {
      const res = await api('/atlas/quiz')
      setStudyAid({ type: 'quiz', data: res.quiz || [] })
    } catch (e) {
      setStudyAid({ type: 'quiz', data: [{ question: `Error: ${e.message}` }] })
    }
  }

  const loadReview = async () => {
    try {
      const res = await api('/atlas/review')
      setStudyAid({ type: 'review', data: res.review || {} })
    } catch (e) {
      setStudyAid({ type: 'review', data: { coach_note: `Error: ${e.message}` } })
    }
  }

  const loadFlashcards = async () => {
    try {
      const res = await api('/atlas/flashcards')
      setStudyAid({ type: 'flashcards', data: res.flashcards || [] })
    } catch (e) {
      setStudyAid({ type: 'flashcards', data: [{ front: `Error: ${e.message}`, back: 'Could not load flashcards.' }] })
    }
  }

  const regenerateExercise = async () => {
    setLoading(true)
    try {
      const res = await api('/atlas/regenerate', { method: 'POST', body: { reason: 'student_requested_new_variant' } })
      if (res?.exercise) {
        setAtlasState(prev => ({ ...(prev || {}), current_exercise: res.exercise }))
        if (res.exercise?.starter_files) {
          const first = Object.values(res.exercise.starter_files)[0] || ''
          setCode(first)
        } else {
          setCode('')
        }
      }
      setResult(null)
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setLoading(false)
    }
  }

  const loadResumeNotes = () => {
    const notes = Array.isArray(atlasState?.resume_packet?.notes) ? atlasState.resume_packet.notes : []
    setStudyAid({ type: 'resume_notes', data: notes })
  }

  const loadResumeFlashcards = () => {
    const cards = Array.isArray(atlasState?.resume_packet?.flashcards) ? atlasState.resume_packet.flashcards : []
    setStudyAid({ type: 'flashcards', data: cards })
  }

  const saveOnboarding = async () => {
    setLoading(true)
    try {
      const res = await api('/atlas/onboard', {
        method: 'POST',
        body: {
          experience_level: onboardingDraft.experience_level,
          preferred_pacing: onboardingDraft.preferred_pacing,
          learning_style: onboardingDraft.learning_style,
          goals: onboardingDraft.goals,
          focus_areas: onboardingDraft.focus_areas,
        },
      })
      if (res?.learner_model) {
        setAtlasState(prev => ({
          ...(prev || {}),
          learner_model: res.learner_model,
          learner_context: res.learner_context || prev?.learner_context,
          learner_profile: res.learner_profile || prev?.learner_profile,
        }))
        const onboarding = res.learner_model?.onboarding || {}
        setOnboardingDraft({
          experience_level: onboarding.experience_level || 'unknown',
          preferred_pacing: onboarding.preferred_pacing || 'gentle',
          learning_style: onboarding.learning_style || 'guided',
          goals: Array.isArray(onboarding.goals) ? onboarding.goals.join(', ') : '',
          focus_areas: Array.isArray(onboarding.focus_areas) ? onboarding.focus_areas.join(', ') : '',
        })
      }
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setLoading(false)
    }
  }

  const runAtlasPlan = async () => {
    setLoading(true)
    try {
      const res = await api('/atlas/plan', { method: 'POST', body: { plan_profile: atlasPlanProfile } })
      setAtlasState(prev => ({
        ...(prev || {}),
        active_plan: res.plan || null,
        plan_history: res.plan_history || prev?.plan_history || [],
        observability: res.observability || prev?.observability || null,
      }))
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setLoading(false)
    }
  }

  const runAtlasEvals = async () => {
    setLoading(true)
    try {
      const res = await api('/atlas/evals', { method: 'POST', body: {} })
      setEvalSummary(res.evaluation || null)
      setAtlasState(prev => ({
        ...(prev || {}),
        eval_history: res.history || prev?.eval_history || [],
        observability: res.observability || prev?.observability || null,
      }))
    } catch (e) {
      setResult({ error: e.message })
    } finally {
      setLoading(false)
    }
  }

  const sendChat = async () => {
    if (!chatInput.trim() || chatBusy) return
    const msg = chatInput.trim()
    setChatInput('')
    setChatBusy(true)
    try {
      const res = await api('/atlas/chat', {
        method: 'POST',
        body: {
          message: msg,
          model: chatModel || undefined,
          mode: chatMode,
          strict_guard: chatMode !== 'assistant',
          regenerate_on_guard: false,
          page_context: {
            current_page: 'atlas',
            lesson: {
              lesson_id: currentLessonId || null,
              exercise_prompt: exercise?.prompt || null,
              recommended_difficulty: learnerContext?.recommended_difficulty || null,
            },
          },
        },
      })
      if (res.chat_history) {
        setAtlasState(prev => ({
          ...(prev || {}),
          ...(chatMode === 'assistant'
            ? { assistant_chat_history: res.chat_history }
            : { chat_history: res.chat_history }),
        }))
      }
    } catch (e) {
      setAtlasState(prev => ({
        ...(prev || {}),
        ...(chatMode === 'assistant'
          ? {
              assistant_chat_history: [
                ...((prev && Array.isArray(prev.assistant_chat_history)) ? prev.assistant_chat_history : []),
                { role: 'assistant', message: `Error: ${e.message}` },
              ],
            }
          : {
              chat_history: [
                ...((prev && Array.isArray(prev.chat_history)) ? prev.chat_history : []),
                { role: 'assistant', message: `Error: ${e.message}` },
              ],
            }),
      }))
    } finally {
      setChatBusy(false)
    }
  }

  const exercise       = atlasState?.current_exercise
  const curriculum     = atlasState?.curriculum
  const modules        = curriculum?.modules || []
  const currentLessonId = atlasState?.lesson_id
  const lessonHistory   = Array.isArray(atlasState?.lesson_history) ? atlasState.lesson_history : []
  const lastSubmission  = atlasState?.last_submission || null
  const tutorHistory = Array.isArray(atlasState?.chat_history) ? atlasState.chat_history : []
  const assistantHistory = Array.isArray(atlasState?.assistant_chat_history) ? atlasState.assistant_chat_history : []
  const chatHistory = chatMode === 'assistant' ? assistantHistory : tutorHistory
  const learnerContext = atlasState?.learner_context || null
  const lessonPlan     = atlasState?.lesson_plan || null
  const resumePacket   = atlasState?.resume_packet || null
  const observability  = atlasState?.observability || null
  const planHistory    = Array.isArray(atlasState?.plan_history) ? atlasState.plan_history : []
  const evalHistory    = Array.isArray(atlasState?.eval_history) ? atlasState.eval_history : []
  const totalLessons = modules.reduce((sum, mod) => sum + (Array.isArray(mod?.lessons) ? mod.lessons.length : 0), 0)

  useEffect(() => {
    const context = {
      lesson_id: currentLessonId || null,
      lesson_title: atlasState?.current_lesson?.title || atlasState?.current_lesson?.lesson_title || null,
      exercise_title: exercise?.title || null,
      exercise_prompt: exercise?.prompt || null,
      latest_feedback: lastSubmission?.hint || lastSubmission?.error || null,
      recommended_difficulty: learnerContext?.recommended_difficulty || null,
      weakest_concepts: learnerContext?.weakest_concepts || [],
    }
    localStorage.setItem('atlas_fab_context', JSON.stringify(context))
  }, [
    atlasState?.current_lesson?.title,
    atlasState?.current_lesson?.lesson_title,
    currentLessonId,
    exercise?.prompt,
    exercise?.title,
    lastSubmission?.error,
    lastSubmission?.hint,
    learnerContext?.recommended_difficulty,
    learnerContext?.weakest_concepts,
  ])

  return (
    <div className="page-enter" style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 16, height: '100%', minHeight: 0, overflow: 'hidden' }}>
      <div style={{ flexShrink: 0 }}>
        <RuntimeStatusBanner title="ATLAS runtime" compact />
        {isMobile && (
          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button
              onClick={() => { setShowLeftPanel(p => !p); setShowRightPanel(false) }}
              style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: `1px solid ${showLeftPanel ? 'rgba(77,166,255,0.5)' : 'var(--border)'}`, background: showLeftPanel ? 'rgba(77,166,255,0.1)' : 'rgba(255,255,255,0.04)', color: showLeftPanel ? 'var(--photon)' : 'var(--txt-sec)', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer' }}
            >
              📚 Curriculum
            </button>
            <button
              onClick={() => { setShowRightPanel(p => !p); setShowLeftPanel(false) }}
              style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: `1px solid ${showRightPanel ? 'rgba(180,124,255,0.5)' : 'var(--border)'}`, background: showRightPanel ? 'rgba(180,124,255,0.1)' : 'rgba(255,255,255,0.04)', color: showRightPanel ? 'var(--violet)' : 'var(--txt-sec)', fontSize: '0.8rem', fontWeight: 600, cursor: 'pointer' }}
            >
              💬 ATLAS Chat
            </button>
          </div>
        )}
      </div>

      {/* Three-column row — fills all remaining height */}
      <div style={{ flex: 1, display: 'flex', flexDirection: isMobile ? 'column' : 'row', gap: 16, minHeight: 0, overflow: isMobile ? 'auto' : 'hidden' }}>

      {/* Left: Curriculum */}
      {(!isMobile || showLeftPanel) && (
      <div style={{ width: isMobile ? '100%' : 240, flexShrink: 0, overflowY: 'auto', minHeight: 0 }}>
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

          <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Onboarding</p>
            <div style={{ display: 'grid', gap: 8 }}>
              <select value={onboardingDraft.experience_level} onChange={e => setOnboardingDraft(prev => ({ ...prev, experience_level: e.target.value }))}
                style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.8rem' }}>
                <option value="unknown">Experience: unknown</option>
                <option value="beginner">Beginner</option>
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
              </select>
              <select value={onboardingDraft.preferred_pacing} onChange={e => setOnboardingDraft(prev => ({ ...prev, preferred_pacing: e.target.value }))}
                style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.8rem' }}>
                <option value="gentle">Gentle pacing</option>
                <option value="steady">Steady pacing</option>
                <option value="challenge">Challenge pacing</option>
              </select>
              <select value={onboardingDraft.learning_style} onChange={e => setOnboardingDraft(prev => ({ ...prev, learning_style: e.target.value }))}
                style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.8rem' }}>
                <option value="guided">Guided</option>
                <option value="hands-on">Hands-on</option>
                <option value="exploratory">Exploratory</option>
              </select>
              <textarea value={onboardingDraft.goals} onChange={e => setOnboardingDraft(prev => ({ ...prev, goals: e.target.value }))}
                placeholder="Goals, comma-separated"
                rows={2}
                style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.8rem', outline: 'none', boxSizing: 'border-box', resize: 'vertical' }} />
              <textarea value={onboardingDraft.focus_areas} onChange={e => setOnboardingDraft(prev => ({ ...prev, focus_areas: e.target.value }))}
                placeholder="Focus areas, comma-separated"
                rows={2}
                style={{ width: '100%', padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.8rem', outline: 'none', boxSizing: 'border-box', resize: 'vertical' }} />
              <button onClick={saveOnboarding} disabled={loading}
                style={{ width: '100%', padding: '8px', borderRadius: 8, border: 'none', background: 'var(--cyan)', color: '#050608', fontWeight: 700, fontSize: '0.8rem', cursor: 'pointer', opacity: loading ? 0.7 : 1 }}>
                {loading ? 'Saving…' : 'Save learning profile'}
              </button>
            </div>
          </div>

          <div style={{ marginTop: 16, borderTop: '1px solid var(--border)', paddingTop: 16 }}>
            <p style={{ fontSize: '0.7rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>Adaptive Learner Profile</p>
            <div style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', marginBottom: 8 }}>
              <div style={{ color: 'var(--txt-pri)', fontSize: '0.78rem', marginBottom: 4 }}>
                {learnerContext?.recommended_difficulty ? `Difficulty: ${learnerContext.recommended_difficulty}` : 'Ready to learn'}
              </div>
              <div style={{ color: 'var(--txt-sec)', fontSize: '0.7rem', lineHeight: 1.5 }}>
                Streak {learnerContext?.streak ?? 0} • Attempts {learnerContext?.attempts ?? 0} • Pace {learnerContext?.preferred_pacing || 'gentle'}
              </div>
            </div>
            {learnerContext?.memory_graph_summary ? (
              <div style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', marginBottom: 8 }}>
                <div style={{ color: 'var(--txt-pri)', fontSize: '0.72rem', fontWeight: 600, marginBottom: 4 }}>Memory map</div>
                <div style={{ color: 'var(--txt-sec)', fontSize: '0.68rem', lineHeight: 1.5 }}>
                  {learnerContext.memory_graph_summary.node_count} nodes • {learnerContext.memory_graph_summary.edge_count} edges
                </div>
                {learnerContext.memory_graph_summary.recent_nodes?.length ? (
                  <div style={{ marginTop: 6 }}>
                    {learnerContext.memory_graph_summary.recent_nodes.slice(-3).map(node => (
                      <div key={node.id} style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 2 }}>
                        {node.type}: {node.label}
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
            {learnerContext?.weakest_concepts?.length ? (
              <div style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', marginBottom: 8 }}>
                <div style={{ color: 'var(--txt-pri)', fontSize: '0.72rem', fontWeight: 600, marginBottom: 4 }}>Focus next</div>
                {learnerContext.weakest_concepts.slice(0, 3).map((item, idx) => (
                  <div key={`${item.concept || idx}`} style={{ color: 'var(--txt-sec)', fontSize: '0.68rem', marginTop: 3 }}>
                    {item.concept} • {Math.round((item.mastery || 0) * 100)}%
                  </div>
                ))}
              </div>
            ) : null}
            {observability?.metrics ? (
              <div style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.18)', marginBottom: 8 }}>
                <div style={{ color: 'var(--txt-pri)', fontSize: '0.72rem', fontWeight: 600, marginBottom: 4 }}>ATLAS observability</div>
                <div style={{ color: 'var(--txt-sec)', fontSize: '0.68rem', lineHeight: 1.55 }}>
                  Learner pass rate {observability.metrics.learner_pass_rate || 0}% • Eval pass rate {observability.metrics.eval_pass_rate || 0}%
                </div>
                <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', lineHeight: 1.5, marginTop: 4 }}>
                  Plan runs {observability.metrics.plan_runs || 0} • Eval runs {observability.metrics.eval_runs || 0} • Guard rate {observability.metrics.fab_guard_rate || 0}% • Sandbox success {observability.metrics.sandbox_success_rate || 0}%
                </div>
              </div>
            ) : null}
            <div style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', marginBottom: 8 }}>
              <div style={{ color: 'var(--txt-pri)', fontSize: '0.78rem', marginBottom: 4 }}>
                {currentLessonId ? `Resume: ${currentLessonId}` : 'No active lesson'}
              </div>
              <div style={{ color: 'var(--txt-sec)', fontSize: '0.7rem' }}>
                {lessonHistory.length} saved lesson{lessonHistory.length === 1 ? '' : 's'} • {totalLessons} total
              </div>
            </div>
            {lastSubmission && (
              <div style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border)', marginBottom: 8 }}>
                <div style={{ color: lastSubmission.passed ? '#22c55e' : '#f87171', fontSize: '0.75rem', fontWeight: 600, marginBottom: 4 }}>
                  {lastSubmission.passed ? 'Latest submission passed' : 'Latest submission needs work'}
                </div>
                <div style={{ color: 'var(--txt-sec)', fontSize: '0.68rem', lineHeight: 1.5 }}>
                  {lastSubmission.hint || lastSubmission.error || 'Submission recorded.'}
                </div>
              </div>
            )}
            {resumePacket?.summary ? (
              <div style={{ padding: '8px 10px', borderRadius: 8, background: 'rgba(77,166,255,0.08)', border: '1px solid rgba(77,166,255,0.28)', marginBottom: 8 }}>
                <div style={{ color: 'var(--photon)', fontSize: '0.72rem', fontWeight: 700, marginBottom: 5 }}>
                  Welcome back summary
                </div>
                <div style={{ color: 'var(--txt-sec)', fontSize: '0.68rem', lineHeight: 1.55, marginBottom: 7 }}>
                  {resumePacket.summary}
                </div>
                {resumePacket.prior_work_summary ? (
                  <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', lineHeight: 1.5, marginBottom: 7 }}>
                    Prior work: {resumePacket.prior_work_summary}
                  </div>
                ) : null}
                {resumePacket.latest_activity_at || resumePacket.resource_counts ? (
                  <div style={{ color: 'var(--txt-mut)', fontSize: '0.64rem', marginBottom: 7 }}>
                    {resumePacket.latest_activity_at ? `Last activity ${new Date(resumePacket.latest_activity_at).toLocaleString()}` : 'History recovered'}
                    {resumePacket.resource_counts ? ` • ${resumePacket.resource_counts.notes || 0} notes • ${resumePacket.resource_counts.flashcards || 0} flashcards` : ''}
                  </div>
                ) : null}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <button onClick={loadResumeNotes}
                    style={{ padding: '5px 8px', borderRadius: 7, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.66rem', cursor: 'pointer' }}>
                    Pull notes ({(resumePacket.notes || []).length})
                  </button>
                  <button onClick={loadResumeFlashcards}
                    style={{ padding: '5px 8px', borderRadius: 7, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.66rem', cursor: 'pointer' }}>
                    Pull flashcards ({(resumePacket.flashcards || []).length})
                  </button>
                </div>
              </div>
            ) : null}
            {lessonHistory.length > 0 ? lessonHistory.slice(-4).reverse().map((entry, idx) => (
              <div key={`${entry.lesson_id || idx}-${entry.created_at || idx}`} style={{ padding: '6px 0', borderTop: '1px solid var(--border)' }}>
                <div style={{ color: 'var(--txt-pri)', fontSize: '0.76rem' }}>{entry.lesson?.title || entry.lesson?.lesson_title || entry.lesson_id || 'Lesson'}</div>
                <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 2 }}>
                  {new Date(entry.created_at).toLocaleString()}
                </div>
              </div>
            )) : (
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.78rem' }}>No lesson history yet.</div>
            )}
          </div>
        </div>
      </div>
      )}

      {/* Center: Exercise + Editor */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, minWidth: 0, minHeight: 0, overflowY: 'auto' }}>
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
                  <button onClick={prevLesson} disabled={loading}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.8rem', cursor: 'pointer' }}>
                    Back
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

            <div className="glass-card-solid" style={{ padding: 12, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button onClick={loadRecap} style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.76rem', cursor: 'pointer' }}>Recap</button>
              <button onClick={loadQuiz} style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.76rem', cursor: 'pointer' }}>Quiz</button>
              <button onClick={loadFlashcards} style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.76rem', cursor: 'pointer' }}>Flashcards</button>
              <button onClick={loadReview} style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.76rem', cursor: 'pointer' }}>Review</button>
              <select value={atlasPlanProfile} onChange={e => setAtlasPlanProfile(e.target.value)} style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', fontSize: '0.76rem' }}>
                <option value="coding">Tutor + Coding</option>
                <option value="balanced">Balanced</option>
                <option value="atlas">ATLAS-first</option>
                <option value="autonomous">Autonomous Prep</option>
              </select>
              <button onClick={runAtlasPlan} disabled={loading} style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.35)', background: 'rgba(77,166,255,0.12)', color: 'var(--photon)', fontSize: '0.76rem', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.65 : 1 }}>Build Plan</button>
              <button onClick={runAtlasEvals} disabled={loading} style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(34,197,94,0.35)', background: 'rgba(34,197,94,0.12)', color: '#22c55e', fontSize: '0.76rem', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.65 : 1 }}>Run Evals</button>
              <button onClick={regenerateExercise} disabled={loading} style={{ padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(180,124,255,0.35)', background: 'rgba(180,124,255,0.12)', color: 'var(--violet)', fontSize: '0.76rem', cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.65 : 1 }}>New Variant</button>
            </div>

            {atlasState?.active_plan && (
              <div className="glass-card-solid" style={{ padding: 14, flexShrink: 0, borderLeft: '3px solid var(--photon)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <p style={{ margin: 0, fontSize: '0.74rem', fontWeight: 700, color: 'var(--photon)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>ATLAS plan</p>
                  <span style={{ fontSize: '0.66rem', fontFamily: 'JetBrains Mono,monospace', color: atlasState.active_plan.plan_status === 'completed' ? '#22c55e' : atlasState.active_plan.plan_status === 'pending_approval' ? '#f59e0b' : '#f87171' }}>
                    {atlasState.active_plan.plan_status}
                  </span>
                </div>
                <div style={{ marginBottom: 8 }}>
                  <div style={{ height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${Math.round(((atlasState.active_plan.progress?.completed || 0) / Math.max(1, atlasState.active_plan.progress?.total || 1)) * 100)}%`, background: atlasState.active_plan.plan_status === 'completed' ? '#22c55e' : atlasState.active_plan.plan_status === 'pending_approval' ? '#f59e0b' : '#f87171', borderRadius: 999 }} />
                  </div>
                  <div style={{ marginTop: 4, color: 'var(--txt-mut)', fontSize: '0.64rem', fontFamily: 'JetBrains Mono,monospace' }}>
                    {atlasState.active_plan.progress?.completed || 0}/{atlasState.active_plan.progress?.total || 0} steps • {atlasState.active_plan.progress?.pending_approval || 0} pending • {atlasState.active_plan.progress?.failed || 0} failed
                  </div>
                </div>
                {(atlasState.active_plan.plan_steps || []).map((step, idx) => (
                  <div key={step.id || idx} style={{ borderTop: '1px solid var(--border)', paddingTop: 8, marginTop: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                      <span style={{ color: 'var(--txt-pri)', fontSize: '0.74rem' }}>{idx + 1}. {step.title}</span>
                      <span style={{ fontSize: '0.64rem', textTransform: 'uppercase', color: step.status === 'completed' ? '#22c55e' : step.status === 'pending_approval' ? '#f59e0b' : '#f87171', fontFamily: 'JetBrains Mono,monospace' }}>{step.status}</span>
                    </div>
                    <div style={{ color: 'var(--txt-sec)', fontSize: '0.68rem', marginTop: 3 }}>
                      {step.agent_id} • {step.intent}
                    </div>
                    {step.response?.result?.output ? (
                      <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4, lineHeight: 1.45 }}>
                        {String(step.response.result.output).slice(0, 220)}
                      </div>
                    ) : null}
                  </div>
                ))}
                {atlasState.active_plan.synthesis ? (
                  <div style={{ borderTop: '1px solid var(--border)', paddingTop: 10, marginTop: 10 }}>
                    <div style={{ color: 'var(--txt-pri)', fontSize: '0.72rem', fontWeight: 700, marginBottom: 6 }}>ATLAS synthesis</div>
                    <div style={{ color: 'var(--txt-sec)', fontSize: '0.7rem', lineHeight: 1.55, marginBottom: 6 }}>
                      {atlasState.active_plan.synthesis.learner_summary}
                    </div>
                    {atlasState.active_plan.synthesis.coding_brief ? (
                      <div style={{ color: 'var(--txt-mut)', fontSize: '0.67rem', lineHeight: 1.5, marginBottom: 6 }}>
                        Coding brief: {atlasState.active_plan.synthesis.coding_brief}
                      </div>
                    ) : null}
                    <div style={{ color: 'var(--photon)', fontSize: '0.67rem', lineHeight: 1.5 }}>
                      Next action: {atlasState.active_plan.synthesis.next_action}
                    </div>
                    {(atlasState.active_plan.synthesis.checkpoints || []).length ? (
                      <div style={{ marginTop: 8 }}>
                        {(atlasState.active_plan.synthesis.checkpoints || []).map((checkpoint, idx) => (
                          <div key={`${idx}-${checkpoint.slice(0, 20)}`} style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4 }}>
                            {idx + 1}. {checkpoint}
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            )}

            {evalSummary && (
              <div className="glass-card-solid" style={{ padding: 14, flexShrink: 0, borderLeft: '3px solid #22c55e' }}>
                <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>
                  ATLAS evals
                </p>
                <div style={{ color: 'var(--txt-pri)', fontSize: '0.78rem', marginBottom: 6 }}>
                  {evalSummary.summary?.pass_count || 0} passed • {evalSummary.summary?.fail_count || 0} failed
                </div>
                {(evalSummary.checks || []).map((check, idx) => (
                  <div key={check.name || idx} style={{ borderTop: '1px solid var(--border)', paddingTop: 8, marginTop: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                      <span style={{ color: 'var(--txt-pri)', fontSize: '0.74rem' }}>{check.name}</span>
                      <span style={{ fontSize: '0.64rem', textTransform: 'uppercase', color: check.status === 'pass' ? '#22c55e' : '#f87171', fontFamily: 'JetBrains Mono,monospace' }}>{check.status}</span>
                    </div>
                    <div style={{ color: 'var(--txt-sec)', fontSize: '0.68rem', marginTop: 3, lineHeight: 1.45 }}>{check.detail}</div>
                  </div>
                ))}
                {evalHistory.length ? (
                  <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8, marginTop: 10 }}>
                    <div style={{ color: 'var(--txt-pri)', fontSize: '0.7rem', marginBottom: 4 }}>Recent eval history</div>
                    {evalHistory.slice().reverse().slice(0, 4).map((entry, idx) => (
                      <div key={`${entry.generated_at || idx}-${idx}`} style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 3 }}>
                        {entry.generated_at ? new Date(entry.generated_at).toLocaleString() : 'Unknown run'} • {(entry.summary?.pass_count || 0)} pass • {(entry.summary?.fail_count || 0)} fail
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            )}

            {planHistory.length ? (
              <div className="glass-card-solid" style={{ padding: 14, flexShrink: 0 }}>
                <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>
                  Plan history
                </p>
                {planHistory.slice().reverse().slice(0, 4).map((entry, idx) => (
                  <div key={entry.plan_id || idx} style={{ borderTop: idx === 0 ? 'none' : '1px solid var(--border)', paddingTop: idx === 0 ? 0 : 8, marginTop: idx === 0 ? 0 : 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
                      <span style={{ color: 'var(--txt-pri)', fontSize: '0.72rem' }}>{entry.objective || 'Plan objective'}</span>
                      <span style={{ fontSize: '0.64rem', textTransform: 'uppercase', color: entry.plan_status === 'completed' ? '#22c55e' : entry.plan_status === 'pending_approval' ? '#f59e0b' : '#f87171', fontFamily: 'JetBrains Mono,monospace' }}>
                        {entry.plan_status}
                      </span>
                    </div>
                    <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', marginTop: 4, lineHeight: 1.45 }}>
                      {entry.summary || entry.next_action || 'Plan run recorded.'}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            {studyAid && (
              <div className="glass-card-solid" style={{ padding: 14, flexShrink: 0 }}>
                <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', marginBottom: 8 }}>
                  {studyAid.type === 'recap'
                    ? 'Lesson Recap'
                    : studyAid.type === 'quiz'
                      ? 'Quick Quiz'
                      : studyAid.type === 'flashcards'
                        ? 'Flashcards'
                        : studyAid.type === 'resume_notes'
                          ? 'Resume Notes'
                          : 'Coach Review'}
                </p>
                {studyAid.type === 'quiz' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {(studyAid.data || []).map((q, i) => (
                      <p key={i} style={{ margin: 0, color: 'var(--txt-pri)', fontSize: '0.8rem' }}>{i + 1}. {q.question || String(q)}</p>
                    ))}
                  </div>
                ) : studyAid.type === 'flashcards' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {(studyAid.data || []).map((card, i) => (
                      <div key={i} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', background: 'rgba(255,255,255,0.03)' }}>
                        <p style={{ margin: 0, color: 'var(--txt-pri)', fontSize: '0.78rem' }}><strong>Q:</strong> {card.front || String(card)}</p>
                        <p style={{ margin: '5px 0 0 0', color: 'var(--txt-sec)', fontSize: '0.74rem' }}><strong>A:</strong> {card.back || 'Review this concept from your lesson notes.'}</p>
                      </div>
                    ))}
                    {!studyAid.data?.length && <p style={{ margin: 0, color: 'var(--txt-mut)', fontSize: '0.78rem' }}>No flashcards yet for this lesson.</p>}
                  </div>
                ) : studyAid.type === 'resume_notes' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {(studyAid.data || []).map((note, i) => (
                      <div key={note.id || i} style={{ border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', background: 'rgba(255,255,255,0.03)' }}>
                        <p style={{ margin: 0, color: 'var(--txt-pri)', fontSize: '0.78rem' }}>{note.title || `Note ${i + 1}`}</p>
                        <p style={{ margin: '5px 0 0 0', color: 'var(--txt-sec)', fontSize: '0.74rem', lineHeight: 1.5 }}>{note.preview || '(No preview available)'}</p>
                      </div>
                    ))}
                    {!studyAid.data?.length && <p style={{ margin: 0, color: 'var(--txt-mut)', fontSize: '0.78rem' }}>No matching notes were found yet.</p>}
                  </div>
                ) : studyAid.type === 'review' ? (
                  <div style={{ color: 'var(--txt-pri)', fontSize: '0.8rem', lineHeight: 1.5 }}>
                    <p style={{ margin: '0 0 6px 0' }}><strong>Strengths:</strong> {Array.isArray(studyAid.data?.strengths) ? studyAid.data.strengths.join(', ') : ''}</p>
                    <p style={{ margin: '0 0 6px 0' }}><strong>Focus next:</strong> {Array.isArray(studyAid.data?.focus_next) ? studyAid.data.focus_next.join(', ') : ''}</p>
                    <p style={{ margin: 0 }}><strong>Coach note:</strong> {studyAid.data?.coach_note || ''}</p>
                  </div>
                ) : (
                  <p style={{ margin: 0, color: 'var(--txt-pri)', fontSize: '0.8rem', lineHeight: 1.5 }}>{String(studyAid.data || '')}</p>
                )}
              </div>
            )}

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
                {result.adaptive_feedback && (
                  <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
                    <p style={{ margin: 0, color: 'var(--txt-pri)', fontSize: '0.72rem', fontWeight: 600 }}>
                      Adaptive coaching • {result.adaptive_feedback.hint_depth} hints • {result.adaptive_feedback.challenge_level} challenge
                    </p>
                    <p style={{ margin: '4px 0 0 0', color: 'var(--txt-sec)', fontSize: '0.72rem', lineHeight: 1.45 }}>
                      {result.adaptive_feedback.next_step}
                    </p>
                    {(result.adaptive_feedback.mastery_delta !== null && result.adaptive_feedback.mastery_delta !== undefined) ? (
                      <p style={{ margin: '4px 0 0 0', color: 'var(--txt-mut)', fontSize: '0.68rem' }}>
                        Mastery Δ {result.adaptive_feedback.mastery_delta} • Confidence Δ {result.adaptive_feedback.confidence_delta}
                      </p>
                    ) : null}
                  </div>
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
      {(!isMobile || showRightPanel) && (
      <div style={{ width: isMobile ? '100%' : 280, flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
        <div className="glass-card-solid" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '12px 14px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <MessageSquare size={14} color="var(--violet)" />
              <p style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--violet)', textTransform: 'uppercase', letterSpacing: '0.12em', margin: 0 }}>
                {chatMode === 'assistant' ? 'ATLAS Assistant' : 'ATLAS Tutor'}
              </p>
            </div>
            <select value={chatMode} onChange={e => setChatMode(e.target.value)}
              className="filter-select"
              style={{ fontSize: '0.68rem', padding: '3px 6px' }}>
              <option value="assistant">Assistant</option>
              <option value="tutor">Tutor</option>
              <option value="build">Build</option>
            </select>
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
                {chatMode === 'assistant'
                  ? 'Talk to ATLAS naturally about ideas, plans, architecture, and coding.'
                  : 'Ask ATLAS for hints, debugging help, or lesson explanations.'}
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
              placeholder={chatMode === 'assistant' ? 'Talk with ATLAS Assistant…' : 'Ask ATLAS Tutor…'}
              style={{ flex: 1, padding: '7px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.8rem', outline: 'none', fontFamily: 'Inter,sans-serif' }}
            />
            <button onClick={sendChat} disabled={chatBusy}
              style={{ padding: '7px 12px', borderRadius: 8, border: 'none', background: chatBusy ? 'rgba(180,124,255,0.3)' : 'var(--violet)', color: '#fff', fontWeight: 700, cursor: chatBusy ? 'not-allowed' : 'pointer', fontSize: '0.8rem' }}>
              {chatBusy ? '…' : '↑'}
            </button>
          </div>
        </div>
      </div>
      )}
      {/* End three-column row */}
      </div>
    </div>
  )
}
