import { useEffect, useMemo, useRef, useState } from 'react'
import { Send, Loader, Users, MessageSquare, Eye, EyeOff, CornerUpRight, Trash2, Check, Square } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../lib/authContext'
import { startAgentRun, resolveRunApproval, continueAgentRun, cancelAgentRun, reduceRunEvent } from '../../lib/agentRuns'
import RunTimeline from '../RunTimeline'
import ChatMessageBody from '../ChatMessageBody'
import { StepOutput, artifactSections } from '../PlanExecuteResultPanel'
import CurriculumArtifactPanel from '../CurriculumArtifactPanel'
import PlanExecuteResultPanel from '../PlanExecuteResultPanel'
import ResearchArtifactPanel from '../ResearchArtifactPanel'
import CodingArtifactPanel from '../CodingArtifactPanel'
import RepoPicker from './RepoPicker'
import { normalizeCodingArtifact, normalizeResearchArtifact } from './artifacts'
import { AGENT_CATALOG, CATALOG_BY_ID, TEAM_FITS, agentDisplay, agentStatusLabel, parseMention, codingRoute } from './agentCatalog'
import useIsMobile from '../../lib/useIsMobile'

// Calm palette: neutral surfaces, one warm accent (same token as Mammoth Mind's agent toggle).
const GOLD = 'var(--mm-color-agent-default, #d08a52)'
const GOLD_SOFT = 'var(--mm-color-agent-soft, rgba(208,138,82,0.14))'
const RAISED = 'var(--mm-color-surface-raised, #161b22)'
const SUNKEN = 'var(--mm-color-surface-sunken, #080a0e)'
const BORDER = 'var(--border)'
const DANGER = 'var(--mm-color-status-danger, #f87171)'

const THREADS_KEY = 'mammoth_agent_threads_v1'
const THREAD_LIMIT = 30
const HISTORY_TURNS = 8
const MAX_STORED_ARTIFACT_CHARS = 40000
// Keeps auto-scrolled messages clear of the sticky composer and the page header.
const SCROLL_MARGIN = { scrollMarginTop: 16, scrollMarginBottom: 180 }

const FINISHED_RUN = new Set(['completed', 'failed', 'cancelled', 'partial'])

function loadThreads(storageKey = THREADS_KEY) {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(storageKey) || '{}')
    if (!parsed || typeof parsed !== 'object') return {}
    // A run that was still streaming when the page closed cannot resume its stream.
    for (const messages of Object.values(parsed)) {
      if (!Array.isArray(messages)) continue
      for (const message of messages) {
        if (message?.run && !FINISHED_RUN.has(message.run.status)) {
          message.run = { ...message.run, status: 'cancelled', approval: null }
        }
      }
    }
    return parsed
  } catch {
    return {}
  }
}

function slimRun(run) {
  if (!run || JSON.stringify(run).length <= MAX_STORED_ARTIFACT_CHARS) return run
  // Keep the outcome (reply, plan, proposed diffs); drop bulky tool observations.
  const events = (run.events || []).filter(event => event?.type === 'diff.proposed').slice(-3)
  return { ...run, events }
}

function saveThreads(threads, storageKey = THREADS_KEY) {
  try {
    const slim = {}
    for (const [agentId, messages] of Object.entries(threads)) {
      slim[agentId] = messages.slice(-THREAD_LIMIT).map(message => {
        const rawSize = message.raw ? JSON.stringify(message.raw).length : 0
        const rest = rawSize > MAX_STORED_ARTIFACT_CHARS ? { ...message, raw: undefined } : message
        const size = rest.artifact ? JSON.stringify(rest.artifact).length : 0
        const trimmed = size > MAX_STORED_ARTIFACT_CHARS ? { ...rest, artifact: rest.text } : rest
        return trimmed.run ? { ...trimmed, run: slimRun(trimmed.run) } : trimmed
      })
    }
    window.localStorage.setItem(storageKey, JSON.stringify(slim))
  } catch {
    // storage full or unavailable: threads stay in memory for this session
  }
}

function digestArtifact(artifact) {
  if (!artifact) return ''
  const { summary, sections } = artifactSections(artifact)
  const parts = [summary]
  for (const section of sections.slice(0, 3)) {
    parts.push(section.text ? `${section.title}: ${section.text}` : `${section.title}: ${section.items.slice(0, 3).join('; ')}`)
  }
  return parts.filter(Boolean).join('\n').slice(0, 1200)
}

function errorText(res) {
  const result = res?.result
  const explicit = result?.error || result?.message || res?.error || result?.output?.error
  if (explicit) return String(explicit)
  const output = result?.output
  if (output && typeof output === 'object') {
    const warnings = Array.isArray(output.warnings) ? output.warnings.filter(item => typeof item === 'string' && item.trim()) : []
    const checks = Array.isArray(output.validation?.checks) ? output.validation.checks.filter(check => check?.status === 'failed').map(check => check.detail).filter(Boolean) : []
    const explanation = [output.summary, ...checks, ...warnings].filter(item => typeof item === 'string' && item.trim())
    if (explanation.length) return [...new Set(explanation)].join(' ')
  }
  const failedChecks = result?.execution_loop?.verification?.failed_checks
  const detail = Array.isArray(failedChecks) ? failedChecks.map(check => check?.detail).filter(Boolean).join('; ') : ''
  return detail ? `The agent could not complete this request (${detail}).` : 'The agent could not complete this request.'
}

const chipStyle = (active) => ({
  fontSize: '0.74rem', padding: '5px 11px', borderRadius: 999, cursor: 'pointer',
  border: `1px solid ${active ? GOLD : BORDER}`,
  background: active ? GOLD_SOFT : 'transparent',
  color: active ? GOLD : 'var(--txt-sec)',
})

const ghostButton = {
  display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.7rem', color: 'var(--txt-mut)',
  background: 'none', border: `1px solid ${BORDER}`, borderRadius: 6, padding: '3px 9px', cursor: 'pointer',
}

const primaryButton = (disabled) => ({
  display: 'inline-flex', alignItems: 'center', gap: 7, fontSize: '0.8rem', fontWeight: 600,
  padding: '8px 16px', borderRadius: 8, border: `1px solid ${GOLD}`, background: GOLD_SOFT, color: GOLD,
  cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.55 : 1,
})

function Roster({ agents, selectedId, mode, busyAgentId, onSelect, onTeam, compact, allowedAgentIds }) {
  const [showOthers, setShowOthers] = useState(false)
  const registry = useMemo(() => Object.fromEntries(agents.map(agent => [agent.id, agent])), [agents])
  const known = AGENT_CATALOG.filter(entry => (!allowedAgentIds || allowedAgentIds.includes(entry.id)) && (registry[entry.id] || !agents.length))
  const others = agents.filter(agent => !CATALOG_BY_ID[agent.id] && (!allowedAgentIds || allowedAgentIds.includes(agent.id)))

  const row = (agentId, entry) => {
    const active = mode === 'chat' && selectedId === agentId
    const status = agentStatusLabel(registry[agentId]?.status, busyAgentId === agentId)
    return (
      <button key={agentId} onClick={() => onSelect(agentId)} title={entry.blurb}
        style={{
          display: 'block', width: '100%', textAlign: 'left', padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
          border: `1px solid ${active ? GOLD : 'transparent'}`, background: active ? GOLD_SOFT : 'transparent', marginBottom: 2,
        }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ width: 6, height: 6, borderRadius: 999, background: status.color, flexShrink: 0, opacity: 0.85 }} title={status.label} />
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: active ? GOLD : 'var(--txt-pri)' }}>{entry.name}</span>
        </div>
        <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', lineHeight: 1.45, marginTop: 2, paddingLeft: 13 }}>{entry.blurb}</div>
      </button>
    )
  }

  if (compact) {
    const chip = (key, active, label, onClick, dotColor, title) => (
      <button key={key} onClick={onClick} title={title} aria-pressed={active}
        style={{ ...chipStyle(active), flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 12px', whiteSpace: 'nowrap' }}>
        {dotColor && <span style={{ width: 6, height: 6, borderRadius: 999, background: dotColor, opacity: 0.85 }} />}
        {label}
      </button>
    )
    const agentChip = (agentId, entry) => {
      const status = agentStatusLabel(registry[agentId]?.status, busyAgentId === agentId)
      return chip(agentId, mode === 'chat' && selectedId === agentId, entry.name, () => onSelect(agentId), status.color, `${entry.blurb} (${status.label})`)
    }
    return (
      <nav aria-label="Agents" style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 10, borderBottom: `1px solid ${BORDER}`, scrollbarWidth: 'none', WebkitOverflowScrolling: 'touch' }}>
        {onTeam && chip('team', mode === 'team', <><Users size={12} /> Team run</>, onTeam)}
        {known.map(entry => agentChip(entry.id, entry))}
        {others.length > 0 && chip('others', showOthers, showOthers ? 'Hide system' : `+${others.length} system`, () => setShowOthers(open => !open))}
        {showOthers && others.map(agent => agentChip(agent.id, agentDisplay(agent.id, agent)))}
      </nav>
    )
  }

  return (
    <nav aria-label="Agents" style={{
      flex: '0 0 200px', minWidth: 180, alignSelf: 'flex-start', position: 'sticky', top: 12,
      maxHeight: 'calc(100dvh - 140px)', overflowY: 'auto', borderRight: `1px solid ${BORDER}`, paddingRight: 10,
    }}>
      {onTeam && <button onClick={onTeam}
        style={{
          display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '9px 10px', borderRadius: 8, cursor: 'pointer', marginBottom: 10,
          border: `1px solid ${mode === 'team' ? GOLD : BORDER}`, background: mode === 'team' ? GOLD_SOFT : 'transparent',
          color: mode === 'team' ? GOLD : 'var(--txt-pri)', fontSize: '0.8rem', fontWeight: 600,
        }}>
        <Users size={14} /> Team run
      </button>}
      <div style={{ fontSize: '0.62rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', margin: '4px 10px 6px' }}>Agents</div>
      {known.map(entry => row(entry.id, entry))}
      {others.length > 0 && (
        <>
          <button onClick={() => setShowOthers(open => !open)} style={{ ...ghostButton, border: 'none', margin: '8px 4px 4px' }}>
            {showOthers ? 'Hide' : 'Show'} system agents ({others.length})
          </button>
          {showOthers && others.map(agent => row(agent.id, agentDisplay(agent.id, agent)))}
        </>
      )}
    </nav>
  )
}

function AgentMessage({ message, onHandoff, onApplyPatch, applying, onRunDecision, runBusy, onStartCurriculum, onCurriculumSaved }) {
  const [showRaw, setShowRaw] = useState(false)
  const entry = agentDisplay(message.agent_id)
  const research = message.agent_id === 'research_agent' && message.raw ? normalizeResearchArtifact(message.raw) : null
  const coding = message.agent_id === 'coding_agent' && message.raw ? normalizeCodingArtifact(message.raw) : null
  if (coding && message.patchApplied) coding.applied = true
  const run = message.run
  const settled = message.status === 'ok' || run?.status === 'completed'
  const curriculum = message.agent_id === 'curriculum_agent' ? message.artifact?.curriculum : null

  let body
  if (run) {
    body = (
      <>
        <RunTimeline run={run} busy={runBusy && run.status !== 'awaiting_approval'}
          onContinue={() => onRunDecision?.(message, 'continue')}
          onApprove={() => onRunDecision?.(message, 'approve')} onReject={() => onRunDecision?.(message, 'reject')} />
        {run.reply ? <ChatMessageBody text={run.reply} /> : null}
      </>
    )
  } else if (message.status === 'notice') {
    body = <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>{message.text}</p>
  } else if (message.status === 'pending') {
    body = (
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--txt-sec)', fontSize: '0.8rem' }}>
        <Loader size={13} color={GOLD} style={{ animation: 'spin 1s linear infinite' }} /> Working on it…
      </div>
    )
  } else if (message.status === 'error') {
    body = <p style={{ margin: 0, fontSize: '0.8rem', color: DANGER, lineHeight: 1.6 }}>{message.text}</p>
  } else if (message.status === 'pending_approval') {
    body = (
      <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>
        Prepared a change that needs your approval. Review it under <strong style={{ color: 'var(--txt-pri)' }}>Pending Approvals</strong>.
      </p>
    )
  } else if (showRaw) {
    body = (
      <pre style={{ margin: 0, fontSize: '0.72rem', fontFamily: 'var(--mm-font-mono, monospace)', color: 'var(--txt-sec)', whiteSpace: 'pre-wrap', maxHeight: 320, overflowY: 'auto' }}>
        {JSON.stringify(message.raw || message.artifact, null, 2)}
      </pre>
    )
  } else if (curriculum) {
    body = <CurriculumArtifactPanel key={curriculum.curriculum_id} curriculum={curriculum} onStart={onStartCurriculum} onSaved={onCurriculumSaved} />
  } else if (research) {
    body = <ResearchArtifactPanel artifact={research} rawJson={null} />
  } else if (coding && (coding.code || coding.diff)) {
    body = <CodingArtifactPanel artifact={coding} rawJson={null} onApplyPatch={onApplyPatch ? () => onApplyPatch(message.id, coding) : undefined} applyingPatch={applying} />
  } else if (message.artifact?.artifact_type === 'advice') {
    body = <><p style={{ color: 'var(--txt-mut)', fontSize: '0.72rem' }}>{message.artifact.summary}</p><ChatMessageBody text={message.artifact.content} /></>
  } else {
    body = <StepOutput artifact={message.artifact || message.text} />
  }

  return (
    <div style={{ ...SCROLL_MARGIN, minWidth: 0, padding: '12px 14px', borderRadius: 10, background: RAISED, border: `1px solid ${BORDER}` }}>
      <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: '0.74rem', fontWeight: 600, color: GOLD }}>{entry.name}</span>
        {message.task && <span style={{ fontSize: '0.68rem', color: 'var(--txt-mut)' }}>· {message.task}</span>}
        {message.repo && <span style={{ fontSize: '0.68rem', color: 'var(--txt-mut)' }}>· {message.repo}</span>}
        {message.duration_ms ? <span style={{ fontSize: '0.66rem', color: 'var(--txt-mut)', fontFamily: 'var(--mm-font-mono, monospace)' }}>· {(message.duration_ms / 1000).toFixed(1)}s</span> : null}
        {settled && (
          <span style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
            {message.raw && (
              <button onClick={() => setShowRaw(open => !open)} style={ghostButton} aria-pressed={showRaw}>
                {showRaw ? <Eye size={11} /> : <EyeOff size={11} />} {showRaw ? 'Readable' : 'Raw'}
              </button>
            )}
            <button onClick={onHandoff} style={ghostButton} title="Ask another agent to build on this">
              <CornerUpRight size={11} /> Hand off
            </button>
          </span>
        )}
      </div>
      {body}
    </div>
  )
}

function ChatView({ agentId, agents, temperature, approvalMode, onTrace, onRunComplete, applyPatch, draft, onBusy, compact, allowedAgentIds, lessonContext, storageKey = THREADS_KEY, onStartCurriculum, onCurriculumSaved }) {
  const entry = agentDisplay(agentId, agents.find(agent => agent.id === agentId))
  const { user } = useAuth()
  const [threads, setThreads] = useState(() => loadThreads(storageKey))
  const [taskIntent, setTaskIntent] = useState(entry.tasks[0]?.intent || '')
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [applying, setApplying] = useState(false)
  const [repo, setRepo] = useState('')
  const [repoLabel, setRepoLabel] = useState('')
  const [runActive, setRunActive] = useState(false)
  const runControllerRef = useRef(null)
  const activeRunIdRef = useRef('')
  const listRef = useRef(null)
  const inputRef = useRef(null)
  const messages = threads[agentId] || []
  const task = entry.tasks.find(item => item.intent === taskIntent) || entry.tasks[0]

  useEffect(() => { setTaskIntent(entry.tasks[0]?.intent || '') }, [agentId])
  useEffect(() => {
    if (!draft) return
    if (draft.intent && entry.tasks.some(item => item.intent === draft.intent)) setTaskIntent(draft.intent)
    setText(draft.prompt || '')
    inputRef.current?.focus()
  }, [draft?.nonce])
  useEffect(() => { saveThreads(threads, storageKey) }, [threads, storageKey])

  // The page scrolls now (the card grows with its content), so bring the newest turn into view
  // on change: a fresh question or pending reply sits just above the composer, while a finished
  // reply is shown from its top so long reports read naturally.
  const seenRef = useRef({ count: messages.length, sending })
  useEffect(() => {
    const seen = seenRef.current
    seenRef.current = { count: messages.length, sending }
    if (messages.length === seen.count && sending === seen.sending) return
    const last = listRef.current?.lastElementChild
    if (!last || !messages.length) return
    const finished = !sending && seen.sending && messages[messages.length - 1]?.role === 'agent'
    last.scrollIntoView({ behavior: 'smooth', block: finished ? 'start' : 'nearest' })
  }, [messages.length, sending])

  const updateThread = (fn) => setThreads(prev => ({ ...prev, [agentId]: fn(prev[agentId] || []).slice(-THREAD_LIMIT) }))
  const replaceMessage = (id, fn) => updateThread(prev => prev.map(message => (message.id === id ? fn(message) : message)))

  // Streams a Mammoth Mind agent-loop run (start or approval resume) into one thread message.
  const streamRun = async (messageId, targetId, invoke, meta = {}) => {
    const controller = new AbortController()
    runControllerRef.current = controller
    setRunActive(true)
    setSending(true)
    onBusy?.(targetId)
    const started = performance.now()
    const onEvent = (event) => {
      if (event?.run_id) activeRunIdRef.current = event.run_id
      replaceMessage(messageId, message => {
        const run = reduceRunEvent(message.run, event)
        return { ...message, run, text: run.reply || message.text || '' }
      })
    }
    try {
      await invoke(controller.signal, onEvent)
    } catch (error) {
      const aborted = error?.name === 'AbortError'
      replaceMessage(messageId, message => ({
        ...message,
        run: { ...(message.run || {}), status: aborted ? 'cancelled' : 'failed', error: aborted ? '' : (error?.message || 'Run failed'), approval: null },
      }))
    } finally {
      replaceMessage(messageId, message => ({
        ...message,
        duration_ms: (message.duration_ms || 0) + Math.round(performance.now() - started),
        run: message.run?.status === 'running' ? { ...message.run, status: 'cancelled' } : message.run,
      }))
      runControllerRef.current = null
      activeRunIdRef.current = ''
      setRunActive(false)
      setSending(false)
      onBusy?.('')
      onRunComplete?.({ res: null, prompt: meta.prompt, agentId: targetId, intent: meta.intent })
    }
  }

  const decideRun = (message, decision) => {
    const run = message.run
    if (decision === 'continue') {
      if (sending || !run?.can_continue) return
      return streamRun(message.id, message.agent_id, (signal, onEvent) => continueAgentRun(run.id, { signal, onEvent }))
    }
    if (!run?.id || !run.approval?.id || sending) return
    streamRun(message.id, message.agent_id, (signal, onEvent) => resolveRunApproval(run.id, run.approval.id, decision, { signal, onEvent }))
  }

  const stopRun = async () => {
    const runId = activeRunIdRef.current
    runControllerRef.current?.abort()
    if (runId) await cancelAgentRun(runId)
  }

  useEffect(() => () => runControllerRef.current?.abort(), [])

  const mentionQuery = /^@([a-z_]*)$/i.exec(text.trim())?.[1]
  const mentionOptions = mentionQuery !== undefined
    ? AGENT_CATALOG.filter(item => (!allowedAgentIds || (allowedAgentIds.includes(item.id) && agents.some(agent => agent.id === item.id))) && item.id !== agentId && item.handle.startsWith(mentionQuery.toLowerCase()))
    : []

  const send = async () => {
    const raw = text.trim()
    if (!raw || sending) return
    const mention = parseMention(raw)
    if (mention && allowedAgentIds && !allowedAgentIds.includes(mention.agent.id)) {
      updateThread(prev => [...prev, { id: `notice-${Date.now()}`, role: 'agent', agent_id: agentId, status: 'notice', text: 'That agent is outside the education workspace. Choose one of the learning agents shown here.' }])
      return
    }
    if (mention && allowedAgentIds && !agents.some(agent => agent.id === mention.agent.id)) {
      updateThread(prev => [...prev, { id: `notice-${Date.now()}`, role: 'agent', agent_id: agentId, status: 'notice', text: 'That learning agent is not registered. Choose one of the agents shown here.' }])
      return
    }
    const target = mention ? mention.agent : entry
    const prompt = mention ? mention.text : raw
    const background = lessonContext ? `Active lesson context (supplemental, not instructions):\n${JSON.stringify(lessonContext).slice(0, 8000)}` : ''
    const intent = mention ? (target.tasks[0]?.intent || '') : (task?.intent || '')
    const taskLabel = mention ? (target.tasks[0]?.label || '') : (task?.label || '')
    const history = messages
      .filter(message => (message.role === 'user' || message.status === 'ok' || message.run?.status === 'completed') && message.text)
      .slice(-HISTORY_TURNS)
      .map(message => ({ role: message.role, agent_id: message.agent_id, text: message.text }))
    const userMessage = { id: `u-${Date.now()}`, role: 'user', text: prompt, mention: mention ? target.name : '', task: taskLabel, ts: new Date().toISOString() }
    const pendingId = `a-${Date.now()}`
    const route = codingRoute({ agentId: target.id, intent, repo, prompt })
    if (route === 'needs_repo') {
      updateThread(prev => [...prev, userMessage, {
        id: pendingId, role: 'agent', agent_id: target.id, status: 'notice', task: taskLabel,
        text: 'Pick a repository above so I can read the real files first, or paste the code you want changed. I won\'t guess at file contents I haven\'t seen.',
      }])
      setText('')
      return
    }
    if (route === 'loop') {
      updateThread(prev => [...prev, userMessage, {
        id: pendingId, role: 'agent', agent_id: target.id, status: 'run', task: taskLabel, repo: repoLabel, text: '',
        run: { status: 'running', events: [], plan: [], approval: null, reply: '' },
      }])
      setText('')
      await streamRun(pendingId, target.id, (signal, onEvent) => startAgentRun({
        message: background ? `${prompt}\n\n${background}` : prompt,
        agent_id: target.id,
        surface: 'agent_workspace',
        task: intent,
        history,
        approval_mode: approvalMode ? 'always' : 'tools',
        repo_context: { root: repo },
      }, { signal, onEvent }), { prompt, intent })
      return
    }
    updateThread(prev => [...prev, userMessage, { id: pendingId, role: 'agent', agent_id: target.id, status: 'pending', task: taskLabel }])
    setText('')
    setSending(true)
    onBusy?.(target.id)
    const started = performance.now()
    let res = null
    try {
      res = await api('/run', {
        method: 'POST',
        body: {
          agent_id: target.id,
          intent,
          temperature,
          approval_mode: approvalMode,
          payload: { prompt, history, ...(lessonContext ? { context: { lesson: lessonContext }, lesson_id: lessonContext.lesson_id, background } : {}), coding_intent: target.id === 'coding_agent' ? intent : undefined },
        },
      })
      const inner = res?.result || {}
      const failed = res?.status !== 'ok' || inner.status === 'error'
      const artifact = inner.output ?? null
      const reply = {
        id: pendingId, role: 'agent', agent_id: target.id, task: taskLabel,
        status: failed ? 'error' : inner.status === 'pending_approval' ? 'pending_approval' : 'ok',
        artifact: failed ? null : artifact,
        text: failed ? errorText(res) : digestArtifact(artifact),
        raw: res,
        duration_ms: Math.round(performance.now() - started),
      }
      updateThread(prev => prev.map(message => (message.id === pendingId ? reply : message)))
      if (Array.isArray(res?.thought_steps)) onTrace?.(res.thought_steps)
    } catch (error) {
      updateThread(prev => prev.map(message => (message.id === pendingId
        ? { id: pendingId, role: 'agent', agent_id: target.id, task: taskLabel, status: 'error', text: error.message || 'Request failed' }
        : message)))
      onTrace?.([{ ts: new Date().toISOString(), label: 'Request failed', detail: error.message, status: 'error' }])
    } finally {
      setSending(false)
      onBusy?.('')
      onRunComplete?.({ res, prompt, agentId: target.id, intent })
    }
  }

  const handleApply = async (messageId, artifact) => {
    setApplying(true)
    try {
      const applied = await applyPatch(artifact)
      if (applied?.applied) updateThread(prev => prev.map(message => (message.id === messageId ? { ...message, patchApplied: true } : message)))
    } finally {
      setApplying(false)
    }
  }

  const onKeyDown = (event) => {
    if (compact) return
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      if (mentionOptions.length === 1) setText(`@${mentionOptions[0].handle} `)
      else send()
    }
  }

  return (
    <section aria-label={`${entry.name} conversation`} style={{ flex: '1 1 380px', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      <header style={{ display: 'flex', alignItems: 'flex-start', gap: 10, paddingBottom: 10, borderBottom: `1px solid ${BORDER}` }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--txt-pri)' }}>{entry.name}</div>
          <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', marginTop: 2 }}>{entry.blurb}</div>
          {agentId === 'coding_agent' && (
            <div style={{ marginTop: 6 }}>
              <RepoPicker userId={user?.id || 'local'} value={repo} onChange={(value, label) => { setRepo(value); setRepoLabel(label) }} />
            </div>
          )}
        </div>
        {messages.length > 0 && (
          <button onClick={() => setThreads(prev => ({ ...prev, [agentId]: [] }))} style={ghostButton} title="Start a fresh conversation">
            <Trash2 size={11} /> New chat
          </button>
        )}
      </header>

      <div ref={listRef} style={{ flex: 1, padding: '14px 2px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.length === 0 && (
          <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--txt-mut)', fontSize: '0.8rem', lineHeight: 1.7, maxWidth: 380 }}>
            <MessageSquare size={18} color="var(--txt-mut)" style={{ marginBottom: 6 }} />
            <div>Pick a task below and describe what you need.</div>
            <div>Follow-ups keep the conversation's context. Start a message with <code style={{ color: GOLD }}>@research</code>, <code style={{ color: GOLD }}>@coding</code>, etc. to bring in another agent.</div>
          </div>
        )}
        {messages.map((message, index) => message.role === 'user' ? (
          <div key={message.id || index} style={{ ...SCROLL_MARGIN, alignSelf: 'flex-end', maxWidth: '82%', padding: '9px 13px', borderRadius: 10, background: SUNKEN, border: `1px solid ${BORDER}` }}>
            {(message.task || message.mention) && (
              <div style={{ fontSize: '0.64rem', color: 'var(--txt-mut)', marginBottom: 3 }}>{message.mention ? `→ ${message.mention}` : ''}{message.mention && message.task ? ' · ' : ''}{message.task}</div>
            )}
            <div style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>{message.text}</div>
          </div>
        ) : (
          <AgentMessage key={message.id || index} message={message} applying={applying} onApplyPatch={applyPatch ? handleApply : undefined}
            onStartCurriculum={onStartCurriculum} onCurriculumSaved={onCurriculumSaved}
            onRunDecision={decideRun} runBusy={sending}
            onHandoff={() => { setText('@'); inputRef.current?.focus() }} />
        ))}
      </div>

      <div style={{
        position: 'sticky', bottom: 0, zIndex: 2, background: 'var(--card)', borderTop: `1px solid ${BORDER}`,
        paddingTop: 10, paddingBottom: 'max(4px, env(safe-area-inset-bottom))',
      }}>
        {entry.tasks.length > 1 && (
          <div role="radiogroup" aria-label="Task" style={{ display: 'flex', flexWrap: compact ? 'nowrap' : 'wrap', overflowX: compact ? 'auto' : 'visible', gap: 6, marginBottom: 8, scrollbarWidth: 'none' }}>
            {entry.tasks.map(item => (
              <button key={item.intent} role="radio" aria-checked={item.intent === task?.intent} onClick={() => setTaskIntent(item.intent)} style={{ ...chipStyle(item.intent === task?.intent), flexShrink: 0, whiteSpace: 'nowrap' }}>
                {item.label}
              </button>
            ))}
          </div>
        )}
        {mentionOptions.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
            {mentionOptions.map(item => (
              <button key={item.id} onClick={() => { setText(`@${item.handle} `); inputRef.current?.focus() }} style={chipStyle(false)}>
                @{item.handle} <span style={{ color: 'var(--txt-mut)' }}>· {item.name}</span>
              </button>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <textarea ref={inputRef} value={text} onChange={event => setText(event.target.value)} onKeyDown={onKeyDown}
            aria-label={`Message ${entry.name}`}
            placeholder={task?.placeholder || `Message ${entry.name}…`}
            rows={2}
            style={{ flex: 1, minWidth: 0, resize: 'vertical', minHeight: 44, maxHeight: 200, background: SUNKEN, border: `1px solid ${BORDER}`, borderRadius: 8, padding: '10px 12px', fontSize: compact ? 16 : '0.84rem', color: 'var(--txt-pri)', fontFamily: 'inherit', lineHeight: 1.5 }}
          />
          {runActive ? (
            <button onClick={stopRun} style={primaryButton(false)} aria-label="Stop run" title="Stop this run">
              <Square size={13} />
            </button>
          ) : (
            <button onClick={send} disabled={sending || !text.trim()} style={primaryButton(sending || !text.trim())} aria-label="Send">
              {sending ? <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Send size={14} />}
            </button>
          )}
        </div>
        {(!compact || approvalMode) && (
          <div style={{ fontSize: '0.64rem', color: 'var(--txt-mut)', marginTop: 5 }}>
            {compact ? 'File changes wait for approval' : `Enter to send · Shift+Enter for a new line${approvalMode ? ' · file changes wait for approval' : ''}`}
          </div>
        )}
      </div>
    </section>
  )
}

function TeamRunView({ temperature, approvalMode, onTrace, onPlanRun, onRunComplete, draft, onBusy, compact }) {
  const [objective, setObjective] = useState('')
  const [fit, setFit] = useState('balanced')
  const [preview, setPreview] = useState(null)
  const [selected, setSelected] = useState({})
  const [phase, setPhase] = useState('compose')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!draft) return
    setObjective(draft.prompt || '')
    if (draft.planProfile) setFit(draft.planProfile)
    setPreview(null)
    setResult(null)
    setPhase('compose')
  }, [draft?.nonce])

  const fitHint = TEAM_FITS.find(item => item.value === fit)?.hint

  const loadPreview = async () => {
    if (!objective.trim()) return
    setError('')
    setPhase('previewing')
    try {
      const res = await api('/plan-execute', { method: 'POST', body: { objective, plan_profile: fit, approval_mode: approvalMode, dry_run: true } })
      if (res?.status !== 'ok') throw new Error(res?.error || 'Could not build a plan')
      setPreview(res)
      setSelected(Object.fromEntries((res.plan_steps || []).map(step => [step.id, true])))
      setPhase('review')
    } catch (err) {
      setError(err.message)
      setPhase('compose')
    }
  }

  const runTeam = async () => {
    const stepIds = (preview?.plan_steps || []).filter(step => step.kind !== 'synthesis' && selected[step.id]).map(step => step.id)
    if (!stepIds.length) return
    setError('')
    setPhase('running')
    onBusy?.('orchestrator')
    const running = { status: 'ok', objective, plan_profile: fit, plan_status: 'running', progress: { total: stepIds.length + 1, completed: 0 }, plan_steps: [] }
    onPlanRun?.(running)
    let res = null
    try {
      res = await api('/plan-execute', {
        method: 'POST',
        body: { objective, plan_profile: fit, approval_mode: approvalMode, temperature, stop_on_failure: true, step_ids: stepIds },
      })
      if (res?.status !== 'ok') throw new Error(res?.error || 'Team run failed')
      setResult(res)
      onPlanRun?.(res)
      onTrace?.((res.plan_steps || []).map((step, index) => ({
        ts: step.finished_at || new Date().toISOString(),
        label: `Step ${index + 1}: ${step.title}`,
        detail: `${step.agent_id} • ${step.status} • ${step.duration_ms || 0}ms${step.chained_context ? ' • used earlier results' : ''}`,
        status: step.status === 'completed' ? 'success' : step.status === 'pending_approval' || step.status === 'skipped' ? 'warning' : 'error',
      })))
      setPhase('done')
    } catch (err) {
      setError(err.message)
      onPlanRun?.({ ...running, plan_status: 'failed', error: err.message })
      setPhase('review')
    } finally {
      onBusy?.('')
      onRunComplete?.({ res, prompt: objective, agentId: 'orchestrator', intent: 'plan_execute', planProfile: fit, mode: 'plan' })
    }
  }

  const steps = preview?.plan_steps || []
  const chosenCount = steps.filter(step => step.kind !== 'synthesis' && selected[step.id]).length

  return (
    <section aria-label="Team run" style={{ flex: '1 1 380px', minWidth: 0, display: 'flex', flexDirection: 'column' }}>
      <header style={{ paddingBottom: 10, borderBottom: `1px solid ${BORDER}`, marginBottom: 12 }}>
        <div style={{ fontSize: '0.92rem', fontWeight: 600, color: 'var(--txt-pri)' }}>Team run</div>
        <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', marginTop: 2 }}>
          Several agents work the objective in order. Each one sees what the earlier ones found, and a final synthesis pulls it together.
        </div>
      </header>

      {phase === 'done' && result ? (
        <>
          <PlanExecuteResultPanel planRun={result} rawJson={JSON.stringify(result, null, 2)} />
          <div style={{ marginTop: 12 }}>
            <button onClick={() => { setPhase('compose'); setResult(null); setPreview(null) }} style={ghostButton}>New team run</button>
          </div>
        </>
      ) : (
        <>
          <textarea value={objective} onChange={event => { setObjective(event.target.value); if (phase === 'review') setPhase('compose') }}
            aria-label="Objective" placeholder="What should the team accomplish? One or two sentences is enough." rows={3}
            disabled={phase === 'running'}
            style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical', background: SUNKEN, border: `1px solid ${BORDER}`, borderRadius: 8, padding: '10px 12px', fontSize: compact ? 16 : '0.84rem', color: 'var(--txt-pri)', fontFamily: 'inherit', lineHeight: 1.5, marginBottom: 10 }}
          />
          <div role="radiogroup" aria-label="Team shape" style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 4 }}>
            {TEAM_FITS.map(item => (
              <button key={item.value} role="radio" aria-checked={fit === item.value} disabled={phase === 'running'}
                onClick={() => { setFit(item.value); if (phase === 'review') setPhase('compose') }} style={chipStyle(fit === item.value)}>
                {item.label}
              </button>
            ))}
          </div>
          <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 12 }}>{fitHint}</div>

          {phase !== 'review' && phase !== 'running' && (
            <div>
              <button onClick={loadPreview} disabled={!objective.trim() || phase === 'previewing'} style={primaryButton(!objective.trim() || phase === 'previewing')}>
                {phase === 'previewing' ? <Loader size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Users size={14} />} Preview the plan
              </button>
            </div>
          )}

          {(phase === 'review' || phase === 'running') && (
            <div style={{ border: `1px solid ${BORDER}`, borderRadius: 10, background: RAISED, padding: 12 }}>
              <div style={{ fontSize: '0.64rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 8 }}>
                {phase === 'running' ? 'Team is working — usually one to three minutes' : 'Planned steps — untick anything you do not need'}
              </div>
              {steps.map((step, index) => {
                const synthesis = step.kind === 'synthesis'
                const checked = synthesis || !!selected[step.id]
                return (
                  <label key={step.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '7px 2px', borderTop: index ? `1px solid ${BORDER}` : 'none', cursor: synthesis || phase === 'running' ? 'default' : 'pointer', opacity: checked ? 1 : 0.5 }}>
                    <input type="checkbox" checked={checked} disabled={synthesis || phase === 'running'}
                      onChange={event => setSelected(prev => ({ ...prev, [step.id]: event.target.checked }))}
                      style={{ marginTop: 3, accentColor: '#d08a52' }} />
                    <span style={{ flex: 1, minWidth: 0 }}>
                      <span style={{ fontSize: '0.8rem', color: 'var(--txt-pri)' }}>{step.title}</span>
                      <span style={{ fontSize: '0.68rem', color: 'var(--txt-mut)' }}> · {synthesis ? 'always runs' : agentDisplay(step.agent_id).name}{step.requires_approval ? ' · needs approval' : ''}</span>
                    </span>
                    {phase === 'running' && checked && <Loader size={12} color={GOLD} style={{ animation: 'spin 1.4s linear infinite', marginTop: 3 }} />}
                  </label>
                )
              })}
              {phase === 'review' && (
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button onClick={runTeam} disabled={!chosenCount} style={primaryButton(!chosenCount)}>
                    <Check size={14} /> Run {chosenCount + 1} steps
                  </button>
                  <button onClick={() => setPhase('compose')} style={ghostButton}>Edit objective</button>
                </div>
              )}
            </div>
          )}
        </>
      )}
      {error && <p role="alert" style={{ marginTop: 10, fontSize: '0.78rem', color: DANGER }}>{error}</p>}
    </section>
  )
}

export default function AgentWorkspace({ agents, temperature, approvalMode, onTrace, onPlanRun, onRunComplete, applyPatch, replay, allowedAgentIds, lessonContext, storageKey = THREADS_KEY, onStartCurriculum, onCurriculumSaved }) {
  const [mode, setMode] = useState('chat')
  const [agentId, setAgentId] = useState(() => {
    try {
      const stored = window.localStorage.getItem(allowedAgentIds ? `${storageKey}:selected` : 'mammoth_workspace_agent')
      return stored && (!allowedAgentIds || allowedAgentIds.includes(stored)) ? stored : 'research_agent'
    } catch { return 'research_agent' }
  })
  const [busyAgentId, setBusyAgentId] = useState('')
  const [chatDraft, setChatDraft] = useState(null)
  const [teamDraft, setTeamDraft] = useState(null)

  useEffect(() => {
    if (!allowedAgentIds) return
    const available = agents.filter(agent => allowedAgentIds.includes(agent.id))
    if (available.length && !available.some(agent => agent.id === agentId)) {
      setAgentId(available.find(agent => agent.id === 'research_agent')?.id || available[0].id)
    }
  }, [agents, allowedAgentIds, agentId])

  useEffect(() => {
    try { window.localStorage.setItem(allowedAgentIds ? `${storageKey}:selected` : 'mammoth_workspace_agent', agentId) } catch { /* ignore */ }
  }, [agentId])

  useEffect(() => {
    if (!replay) return
    if (replay.mode === 'plan') {
      setMode('team')
      setTeamDraft(replay)
    } else {
      if (replay.agentId) setAgentId(replay.agentId)
      setMode('chat')
      setChatDraft(replay)
    }
  }, [replay?.nonce])

  const compact = useIsMobile()

  return (
    <div className="glass-card-solid" style={{
      padding: compact ? 10 : 14, display: 'flex', flexDirection: compact ? 'column' : 'row', gap: compact ? 10 : 14,
      // Grows with the conversation (the page scrolls); the minimum keeps an empty chat full-height.
      minHeight: compact ? 'calc(100dvh - 170px)' : 'calc(100dvh - 210px)',
    }}>
      <Roster agents={agents} selectedId={agentId} mode={mode} busyAgentId={busyAgentId} compact={compact}
        allowedAgentIds={allowedAgentIds}
        onSelect={(id) => { setAgentId(id); setMode('chat'); setChatDraft(null) }} onTeam={allowedAgentIds ? undefined : () => { setMode('team'); setTeamDraft(null) }} />
      {mode === 'team' ? (
        <TeamRunView temperature={temperature} approvalMode={approvalMode} onTrace={onTrace} onPlanRun={onPlanRun}
          onRunComplete={onRunComplete} draft={teamDraft} onBusy={setBusyAgentId} compact={compact} />
      ) : (
        <ChatView key={agentId} agentId={agentId} agents={agents} temperature={temperature} approvalMode={approvalMode}
          onTrace={onTrace} onRunComplete={onRunComplete} applyPatch={applyPatch} draft={chatDraft} onBusy={setBusyAgentId} compact={compact}
          allowedAgentIds={allowedAgentIds} lessonContext={lessonContext} storageKey={storageKey}
          onStartCurriculum={onStartCurriculum} onCurriculumSaved={onCurriculumSaved} />
      )}
    </div>
  )
}
