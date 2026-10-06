import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import LessonsPage from './LessonsPage'
import AtlasTutorPage from './AtlasTutorPage'
import AgentWorkspace from '../components/agent-workspace/AgentWorkspace'
import { useAuth } from '../lib/authContext'
import useIsMobile from '../lib/useIsMobile'
import AtlasLearningProfile from '../components/AtlasLearningProfile'
import CurriculumArtifactPanel from '../components/CurriculumArtifactPanel'
import '../components/atlas-workspace.css'

const EDUCATION_AGENTS = ['tutor_agent', 'curriculum_agent', 'research_agent', 'reflection_agent', 'coding_agent', 'browser_agent']

export default function AtlasWorkspacePage() {
  const { user } = useAuth()
  return <LearningWorkspace key={user?.id || 'local'} />
}

function LearningWorkspace() {
  const { user } = useAuth()
  const mobile = useIsMobile()
  const [view, setView] = useState('lesson')
  const [tutorOpen, setTutorOpen] = useState(false)
  const [advanced, setAdvanced] = useState(false)
  const [state, setState] = useState(null)
  const [agents, setAgents] = useState([])
  const [error, setError] = useState('')
  const [agentError, setAgentError] = useState('')
  const [curricula, setCurricula] = useState([])
  const [libraryError, setLibraryError] = useState('')
  const pendingState = useRef(null)
  const mounted = useRef(true)

  const loadState = useCallback(async (refresh = false) => {
    if (refresh === true && pendingState.current) await pendingState.current.catch(() => {})
    if (!pendingState.current) {
      pendingState.current = api('/atlas/status')
        .then(snapshot => {
          if (mounted.current) { setState(snapshot); setError('') }
          return snapshot
        })
        .catch(cause => {
          if (mounted.current) setError(cause instanceof Error ? cause.message : 'Could not load ATLAS.')
          throw cause
        })
        .finally(() => { pendingState.current = null })
    }
    return pendingState.current
  }, [])

  const loadAgents = useCallback(async () => {
    try {
      const data = await api('/atlas/agents')
      const list = Array.isArray(data) ? data : data?.agents
      if (!Array.isArray(list)) throw new Error('The agent catalog returned an invalid response.')
      if (mounted.current) {
        setAgents(list.filter(agent => EDUCATION_AGENTS.includes(agent.id)))
        setAgentError('')
      }
    } catch (cause) {
      if (mounted.current) setAgentError(cause instanceof Error ? cause.message : 'Could not load learning agents.')
    }
  }, [])

  const loadCurricula = useCallback(async () => {
    try {
      const result = await api('/atlas/curricula')
      if (!Array.isArray(result.curricula)) throw new Error('Your curriculum library returned an invalid response.')
      if (mounted.current) { setCurricula(result.curricula); setLibraryError('') }
    } catch (cause) {
      if (mounted.current) setLibraryError(cause.message || 'Could not load your curricula.')
    }
  }, [])

  const startCurriculum = async curriculumId => {
    await api('/atlas/curricula/start', { method: 'POST', body: { curriculum_id: curriculumId } })
    await loadState(true)
    setView('lesson')
  }

  useEffect(() => {
    mounted.current = true
    loadAgents()
    loadCurricula()
    const interval = setInterval(() => { loadState().catch(() => {}) }, 15000)
    return () => { mounted.current = false; clearInterval(interval) }
  }, [loadAgents, loadState, loadCurricula])

  const lesson = state?.current_lesson
  const lessonContext = {
    lesson_id: state?.lesson_id || '',
    title: lesson?.title || lesson?.lesson_title || '',
    summary: lesson?.summary || '',
    content: lesson?.content || '',
    exercise: state?.current_exercise || null,
  }
  const showTutor = view === 'tutor' || (view === 'lesson' && tutorOpen && !mobile)
  const showLesson = view === 'lesson'

  return (
    <div className="atlas-workspace page-enter">
      <header className="atlas-workspace-header">
        <div>
          <h1>ATLAS</h1>
          <p>{lessonContext.title || 'Your learning workspace'} · Lessons, practice, tutor, and research</p>
        </div>
        <nav aria-label="ATLAS workspace">
          {['lesson', 'tutor', 'agents', 'curricula'].map(mode => (
            <button key={mode} type="button" aria-pressed={view === mode} onClick={() => setView(mode)}>
              {mode === 'lesson' ? 'Lesson & practice' : mode === 'tutor' ? 'ATLAS Tutor' : mode === 'agents' ? 'Learning agents' : 'My curricula'}
            </button>
          ))}
        </nav>
        {showLesson && <button type="button" aria-expanded={tutorOpen && !mobile} onClick={() => mobile ? setView('tutor') : setTutorOpen(open => !open)}>
          {tutorOpen && !mobile ? 'Hide tutor' : 'Consult tutor'}
        </button>}
        {view === 'tutor' && <button type="button" aria-pressed={advanced} onClick={() => setAdvanced(value => !value)}>Advanced tutor tools</button>}
      </header>
      <AtlasLearningProfile state={state} loadState={loadState} />
      {error && <div role="alert" className="atlas-workspace-error">{error} <button onClick={() => loadState().catch(() => {})}>Retry</button></div>}
      <div className={`atlas-workspace-content ${showLesson && showTutor ? 'with-tutor' : ''}`}>
        <section aria-label="Lesson and practice" hidden={!showLesson} className="atlas-workspace-lesson">
          <LessonsPage embedded sharedState={state} loadSharedState={loadState} />
        </section>
        <section aria-label="ATLAS tutor conversation" hidden={!showTutor} className="atlas-workspace-tutor">
          <AtlasTutorPage conversationOnly={!(view === 'tutor' && advanced)} sharedState={state} loadSharedState={loadState} />
        </section>
        <section aria-label="Education agents" hidden={view !== 'agents'} className="atlas-workspace-agents">
          <p className="atlas-workspace-context">Agents receive the active lesson and exercise as context. Research is supplemental; it does not replace the lesson or count as mastery.</p>
          {agentError ? <div role="alert" className="atlas-workspace-error">{agentError} <button onClick={loadAgents}>Retry catalog</button></div> : agents.length ? (
            <AgentWorkspace key={user?.id || 'local'} agents={agents} temperature={0.3} approvalMode
              allowedAgentIds={EDUCATION_AGENTS} lessonContext={lessonContext}
              onStartCurriculum={startCurriculum} onCurriculumSaved={loadCurricula}
              storageKey={`mammoth_education_threads_v1:${user?.id || 'local'}`} />
          ) : <p role="status">No learning agents available. <button onClick={loadAgents}>Refresh catalog</button></p>}
        </section>
        <section aria-label="Saved curricula" hidden={view !== 'curricula'} style={{ overflowY: 'auto' }}>
          <h2>My curricula</h2>
          <p>Review saved drafts or start an authored course. Your current lesson and progress remain available through Lesson &amp; practice.</p>
          {libraryError && <p role="alert">{libraryError} <button onClick={loadCurricula}>Retry curricula</button></p>}
          {!libraryError && !curricula.length && <p>No saved curricula yet. Use the Curriculum learning agent, review its preview, then choose Save to my curricula.</p>}
          {curricula.map(record => <details key={`${record.curriculum.curriculum_id}:${record.saved_at}`} style={{ marginBottom: 12 }}>
            <summary>{record.curriculum.title || record.curriculum.subject}</summary>
            <CurriculumArtifactPanel curriculum={record.curriculum} alreadySaved onStart={startCurriculum} onSaved={loadCurricula} />
          </details>)}
        </section>
      </div>
    </div>
  )
}
