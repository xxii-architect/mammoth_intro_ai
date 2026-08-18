import { useEffect, useMemo, useRef, useState } from 'react'
import { Bot, MessageSquare, Sparkles, Wrench, Brain, Terminal, Send, Trash2, ChevronDown, ChevronRight, Workflow } from 'lucide-react'
import { api } from '../api/client'
import RuntimeStatusBanner from '../components/RuntimeStatusBanner'

const TASK_CARD_STORAGE_KEY = 'mammoth_chat_task_cards_v1'

const AGENT_OPTIONS = [
  { id: 'assistant', label: 'Mammoth Assistant', Icon: MessageSquare, accent: 'var(--photon)', detail: 'Normal AI chat for planning, debugging, and product thinking.' },
  { id: 'coding_agent', label: 'Coding Agent', Icon: Wrench, accent: 'var(--cyan)', detail: 'Repo-focused coding help, patch strategy, and implementation tasks.' },
  { id: 'reasoning_agent', label: 'Reasoning Agent', Icon: Brain, accent: 'var(--violet)', detail: 'Break down decisions, tradeoffs, and next steps.' },
  { id: 'shell_agent', label: 'Shell Agent', Icon: Terminal, accent: '#22c55e', detail: 'Command-oriented ops thinking within the safe shell runtime.' },
]

const QUICK_ACTIONS = [
  {
    title: 'General chat',
    agentId: 'assistant',
    tone: 'normal',
    message: 'Help me think through the next MammothOS move with practical, grounded advice.',
  },
  {
    title: 'Code patch',
    agentId: 'coding_agent',
    tone: 'build',
    codingIntent: 'patch_existing',
    message: 'Patch the current MammothOS feature without scaffolding a new app. Tell me what files and changes you would make.',
  },
  {
    title: 'Deep reasoning',
    agentId: 'reasoning_agent',
    tone: 'reason',
    message: 'Compare the next two MammothOS upgrade options and tell me which one should come first.',
  },
  {
    title: 'Shell lane',
    agentId: 'shell_agent',
    tone: 'ops',
    message: 'Draft a safe shell-oriented step plan for the next MammothOS maintenance task.',
  },
]

const SLASH_ACTIONS = [
  '/agent coding_agent Patch the current feature safely',
  '/plan Build the next MammothOS upgrade slice',
  '/approvals',
  '/runs',
]

function loadTaskCards() {
  try {
    const raw = localStorage.getItem(TASK_CARD_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveTaskCards(cards) {
  localStorage.setItem(TASK_CARD_STORAGE_KEY, JSON.stringify(cards.slice(0, 20)))
}

function summarizePlanResult(result) {
  const progress = result?.progress || {}
  return [
    `Plan profile: ${result?.plan_profile || 'balanced'}`,
    `Status: ${result?.plan_status || 'unknown'}`,
    `Progress: ${progress.completed || 0}/${progress.total || 0} completed`,
    `Pending approvals: ${progress.pending_approval || 0}`,
  ].join(' • ')
}

function parseSlashCommand(input) {
  const message = String(input || '').trim()
  if (!message.startsWith('/')) return null
  const [command, ...rest] = message.split(/\s+/)
  const payload = rest.join(' ').trim()
  if (command === '/plan') {
    return { kind: 'plan', objective: payload }
  }
  if (command === '/approvals') {
    return { kind: 'approvals' }
  }
  if (command === '/runs') {
    return { kind: 'runs' }
  }
  if (command === '/agent') {
    const [requestedAgentId, ...remaining] = rest
    return {
      kind: 'agent',
      agentId: requestedAgentId || 'assistant',
      message: remaining.join(' ').trim(),
    }
  }
  return { kind: 'unknown', command }
}

function findLastAssistantIndex(list) {
  for (let i = list.length - 1; i >= 0; i -= 1) {
    if (list[i]?.role === 'assistant') return i
  }
  return -1
}

function updateLastAssistant(list, updater) {
  const idx = findLastAssistantIndex(list)
  if (idx < 0) return list
  const next = [...list]
  next[idx] = updater(next[idx])
  return next
}

function ThoughtTrail({ steps, busy, expandedIndex, onToggle, compact = false }) {
  const list = Array.isArray(steps) ? steps : []
  return (
    <div className="glass-card-solid" style={{ padding: compact ? 14 : 16, minHeight: compact ? 180 : 220, maxHeight: compact ? '34vh' : '42vh', display: 'flex', flexDirection: 'column', minWidth: 0 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: compact ? 8 : 10 }}>
        <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700, margin: 0 }}>
          Thought Trail
        </p>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {busy && <span style={{ fontSize: '0.72rem', color: 'var(--cyan)' }}>thinking…</span>}
          <span style={{ fontSize: '0.68rem', color: 'var(--txt-mut)' }}>{list.length} steps</span>
        </div>
      </div>
      <div style={{ display: 'grid', gap: 8, overflowY: 'auto', minHeight: 0, paddingRight: 2 }}>
        {list.length ? list.slice(-12).map((step, idx) => {
          const absoluteIndex = Math.max(0, list.length - Math.min(list.length, 12) + idx)
          const isOpen = expandedIndex === absoluteIndex
          const tone = step.status === 'error' ? '#f87171' : step.status === 'success' ? '#22c55e' : step.status === 'warning' ? '#f59e0b' : 'var(--photon)'
          return (
            <button
              key={`${step.ts || idx}-${idx}`}
              onClick={() => onToggle(absoluteIndex)}
              style={{ textAlign: 'left', padding: compact ? '9px 11px' : '10px 12px', borderRadius: 12, border: '1px solid var(--border)', background: isOpen ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)', cursor: 'pointer' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: tone, boxShadow: `0 0 10px ${tone}` }} />
                  <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{step.label || 'Step'}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: '0.68rem', color: tone, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{step.status || 'info'}</span>
                  {isOpen ? <ChevronDown size={14} color="var(--txt-mut)" /> : <ChevronRight size={14} color="var(--txt-mut)" />}
                </div>
              </div>
              {step.detail && <p style={{ margin: '6px 0 0', fontSize: '0.74rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{step.detail}</p>}
              {isOpen && (
                <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px dashed var(--border)', fontSize: '0.68rem', color: 'var(--txt-mut)', lineHeight: 1.6 }}>
                  <div>timestamp: {step.ts || 'n/a'}</div>
                  <div>status: {step.status || 'info'}</div>
                </div>
              )}
            </button>
          )
        }) : (
          <p style={{ fontSize: '0.8rem', color: 'var(--txt-mut)', lineHeight: 1.6, margin: 0 }}>
            No trail yet. Once you send a message, MammothOS will show its routing and response steps here.
          </p>
        )}
      </div>
    </div>
  )
}

export default function ChatPage({ setPage }) {
  const [history, setHistory] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [agentId, setAgentId] = useState('assistant')
  const [codingIntent, setCodingIntent] = useState('patch_existing')
  const [thoughtSteps, setThoughtSteps] = useState([])
  const [meta, setMeta] = useState(null)
  const [error, setError] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [expandedThoughtIndex, setExpandedThoughtIndex] = useState(-1)
  const [quickActionsOpen, setQuickActionsOpen] = useState(true)
  const [taskCards, setTaskCards] = useState(() => loadTaskCards())
  const [approvals, setApprovals] = useState([])
  const [autonomousRuns, setAutonomousRuns] = useState({ summary: null, runs: [] })
  const [isNarrowLayout, setIsNarrowLayout] = useState(() => (typeof window !== 'undefined' ? window.innerWidth < 1540 : false))
  const [isShortViewport, setIsShortViewport] = useState(() => (typeof window !== 'undefined' ? window.innerHeight < 860 : false))
  const [rightRailOpen, setRightRailOpen] = useState(() => (typeof window !== 'undefined' ? window.innerWidth >= 1540 : true))
  const bottomRef = useRef(null)
  const streamControllerRef = useRef(null)

  const refreshOps = async () => {
    try {
      const [approvalList, runData] = await Promise.all([
        api('/approvals'),
        api('/autonomous/runs'),
      ])
      const nextApprovals = Array.isArray(approvalList) ? approvalList : []
      const nextRuns = {
        summary: runData?.summary || null,
        runs: Array.isArray(runData?.runs) ? runData.runs : [],
      }
      setApprovals(nextApprovals)
      setAutonomousRuns(nextRuns)
      return { approvals: nextApprovals, autonomousRuns: nextRuns }
    } catch {
      return { approvals: [], autonomousRuns: { summary: null, runs: [] } }
    }
  }

  useEffect(() => {
    api('/mammoth/chat/history')
      .then((data) => {
        const chatHistory = Array.isArray(data?.chat_history) ? data.chat_history : []
        setHistory(chatHistory)
        const lastAssistant = [...chatHistory].reverse().find((entry) => entry.role === 'assistant')
        if (lastAssistant?.thought_steps) {
          setThoughtSteps(lastAssistant.thought_steps)
        }
      })
      .catch(() => {})
    refreshOps()
  }, [])

  useEffect(() => {
    const timer = setInterval(() => {
      refreshOps()
    }, 3000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history, busy, streaming])

  useEffect(() => () => {
    streamControllerRef.current?.abort?.()
  }, [])

  useEffect(() => {
    const onResize = () => {
      setIsNarrowLayout(window.innerWidth < 1540)
      setIsShortViewport(window.innerHeight < 860)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const selectedAgent = useMemo(() => AGENT_OPTIONS.find((item) => item.id === agentId) || AGENT_OPTIONS[0], [agentId])
  const showRightRail = rightRailOpen
  const showInlineRightRail = showRightRail && !isNarrowLayout
  const showDrawerRightRail = showRightRail && isNarrowLayout

  const pushThought = (step) => {
    setThoughtSteps((prev) => [...prev, step])
  }

  const pushEntries = (...entries) => {
    setHistory((prev) => [...prev, ...entries])
  }

  const persistTaskCards = (updater) => {
    setTaskCards((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      saveTaskCards(next)
      return next
    })
  }

  const saveTaskCardFromEntry = (entry, extras = {}) => {
    if (!entry) return
    const card = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      created_at: new Date().toISOString(),
      title: extras.title || (entry.agent_id === 'assistant' ? 'MammothOS task card' : `${entry.agent_id || 'agent'} task card`),
      prompt: extras.prompt || '',
      reply: entry.message || '',
      agent_id: extras.agent_id || entry.agent_id || 'assistant',
      task_id: extras.task_id || entry.task_id || '',
      coding_intent: extras.coding_intent || '',
      replay: extras.replay || null,
      evidence_items: Array.isArray(entry.evidence_items) ? entry.evidence_items : [],
    }
    persistTaskCards((prev) => [card, ...prev].slice(0, 20))
  }

  const loadTaskCard = (card) => {
    if (!card) return
    if (card.replay?.execution_mode === 'plan') {
      setInput(`/plan ${card.replay.objective || card.prompt || ''}`.trim())
      return
    }
    setAgentId(card.agent_id || 'assistant')
    if (card.coding_intent) setCodingIntent(card.coding_intent)
    setInput(card.prompt || '')
  }

  const appendSystemMessage = (message, extras = {}) => {
    pushEntries({
      role: 'assistant',
      agent_id: extras.agent_id || 'assistant',
      message,
      created_at: new Date().toISOString(),
      mode: 'chat',
      adapter: extras.adapter || 'mammoth-ui',
      model: extras.model || 'operator-handoff',
      task_id: extras.task_id || '',
      evidence_items: Array.isArray(extras.evidence_items) ? extras.evidence_items : [],
    })
  }

  const streamChat = async (body, effectiveAgentId, placeholderIndex) => {
    const response = await fetch('/api/mammoth/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: streamControllerRef.current?.signal,
    })
    if (!response.ok || !response.body) {
      throw new Error(`Streaming request failed (${response.status})`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let done = false

    const processBlock = (block) => {
      if (!block.trim()) return
      let eventType = 'message'
      let dataLine = ''
      block.split(/\r?\n/).forEach((line) => {
        if (line.startsWith('event:')) eventType = line.slice(6).trim()
        if (line.startsWith('data:')) dataLine += line.slice(5).trim()
      })
      if (!dataLine) return
      let payload = null
      try {
        payload = JSON.parse(dataLine)
      } catch {
        payload = dataLine
      }

      if (eventType === 'meta' && payload) {
        setMeta({
          agentId: payload.agent_id || effectiveAgentId,
          adapter: payload.adapter || 'unknown',
          model: payload.model || 'unknown',
          taskId: payload.task_id || '',
          dispatched: Boolean(payload.dispatched),
        })
      }

      if (eventType === 'thought' && payload) {
        setThoughtSteps((prev) => [...prev, payload])
      }

      if (eventType === 'chunk' && payload?.text) {
        const text = String(payload.text)
        setHistory((prev) => {
          const next = [...prev]
          if (placeholderIndex >= 0 && next[placeholderIndex]) {
            next[placeholderIndex] = {
              ...next[placeholderIndex],
              message: (next[placeholderIndex].message || '') + text,
              stream: true,
            }
          }
          return next
        })
      }

      if (eventType === 'done' && payload) {
        if (Array.isArray(payload.thought_steps) && payload.thought_steps.length) {
          setThoughtSteps(payload.thought_steps)
        }
        if (payload.chat_history) {
          setHistory(Array.isArray(payload.chat_history) ? payload.chat_history : [])
        }
        setMeta({
          agentId: payload.agent_id || effectiveAgentId,
          adapter: payload.adapter || 'unknown',
          model: payload.model || 'unknown',
          taskId: payload.task_id || '',
          dispatched: Boolean(payload.dispatched),
        })
        done = true
      }
    }

    while (!done) {
      const { value, done: readerDone } = await reader.read()
      if (value) {
        buffer += decoder.decode(value, { stream: true })
        let boundary = buffer.indexOf('\n\n')
        while (boundary >= 0) {
          const block = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)
          processBlock(block)
          boundary = buffer.indexOf('\n\n')
        }
      }
      if (readerDone) break
    }
  }

  const send = async (override, overrideAgentId = null) => {
    const message = (override || input).trim()
    if (!message || busy) return
    const slash = parseSlashCommand(message)
    if (slash) {
      setError('')
      if (!override) setInput('')
      if (slash.kind === 'approvals') {
        const ops = await refreshOps()
        const pendingApprovals = ops.approvals.filter((item) => item.status === 'pending')
        appendSystemMessage(
          pendingApprovals.length
            ? `There are ${pendingApprovals.length} approvals waiting. Open Agent Console to review or approve them.`
            : 'No approvals are currently waiting.',
          { evidence_items: pendingApprovals.slice(0, 4).map((item) => ({ agent_id: item.agent_id, summary: `${item.operation} • ${item.target}`, source: 'approval-queue', status: item.status })) },
        )
        return
      }
      if (slash.kind === 'runs') {
        const ops = await refreshOps()
        const latestRun = ops.autonomousRuns.runs[0]
        appendSystemMessage(
          latestRun
            ? `Latest autonomous run: ${latestRun.objective || 'Unnamed run'} • ${latestRun.plan_status || 'unknown'} • ${(latestRun.progress?.completed || 0)}/${(latestRun.progress?.total || 0)} complete.`
            : 'No autonomous runs recorded yet.',
          { evidence_items: ops.autonomousRuns.runs.slice(0, 3).map((run) => ({ agent_id: run.current_lane?.agent_id || 'orchestrator', summary: `${run.objective || 'Autonomous run'} • ${run.plan_status}`, source: run.source || 'autonomous-run', status: run.plan_status })) },
        )
        return
      }
      if (slash.kind === 'plan') {
        if (!slash.objective) {
          setError('Usage: /plan <objective>')
          return
        }
        setBusy(true)
        setStreaming(false)
        pushThought({ ts: new Date().toISOString(), label: 'Planning the herd', detail: slash.objective, status: 'info' })
        try {
          const result = await api('/plan-execute', {
            method: 'POST',
            body: {
              objective: slash.objective,
              approval_mode: true,
              stop_on_failure: true,
              plan_profile: agentId === 'coding_agent' ? 'coding' : 'atlas',
              coding_intent,
            },
          })
          const summary = summarizePlanResult(result)
          const evidenceItems = Array.isArray(result?.plan_steps)
            ? result.plan_steps.map((step) => ({
                agent_id: step.agent_id,
                summary: `${step.title} • ${step.status}`,
                source: 'plan-execute',
                status: step.status,
              }))
            : []
          appendSystemMessage(summary, {
            agent_id: 'orchestrator',
            task_id: result.plan_id || '',
            model: 'plan-execute',
            evidence_items: evidenceItems,
          })
          saveTaskCardFromEntry(
            { agent_id: 'orchestrator', message: summary, task_id: result.plan_id || '', evidence_items: evidenceItems },
            {
              title: `Plan card • ${slash.objective.slice(0, 32)}`,
              prompt: slash.objective,
              replay: {
                execution_mode: 'plan',
                objective: slash.objective,
                plan_profile: result.plan_profile || (agentId === 'coding_agent' ? 'coding' : 'atlas'),
                coding_intent: result.coding_intent || codingIntent,
                approval_mode: true,
              },
            },
          )
          setThoughtSteps((result.plan_steps || []).map((step, idx) => ({
            ts: step.finished_at || new Date().toISOString(),
            label: `Plan step ${idx + 1}: ${step.title}`,
            detail: `${step.agent_id} • ${step.status} • ${step.duration_ms || 0}ms`,
            status: step.status === 'completed' ? 'success' : step.status === 'pending_approval' ? 'warning' : 'error',
          })))
          await refreshOps()
        } catch (e) {
          setError(e instanceof Error ? e.message : 'Plan execution failed')
        } finally {
          setBusy(false)
        }
        return
      }
      if (slash.kind === 'agent') {
        if (!slash.message) {
          setError('Usage: /agent <agent_id> <message>')
          return
        }
        setAgentId(slash.agentId)
        return send(slash.message, slash.agentId)
      }
      setError(`Unknown slash action: ${slash.command}`)
      return
    }

    const effectiveAgentId = overrideAgentId || agentId
    setBusy(true)
    setStreaming(true)
    setError('')
    if (!override) setInput('')

    const userEntry = {
      role: 'user',
      message,
      created_at: new Date().toISOString(),
      agent_id: effectiveAgentId,
      mode: 'chat',
      page: 'chat',
    }
    const assistantPlaceholder = {
      role: 'assistant',
      message: '',
      created_at: new Date().toISOString(),
      agent_id: effectiveAgentId,
      mode: 'chat',
      adapter: 'streaming',
      model: 'streaming',
      stream: true,
      thought_steps: [],
    }

    let placeholderIndex = -1
    setHistory((prev) => {
      const next = [...prev, userEntry, assistantPlaceholder]
      placeholderIndex = next.length - 1
      return next
    })
    setThoughtSteps([
      { ts: new Date().toISOString(), label: 'Hearing hoofbeats', detail: `agent=${effectiveAgentId} mode=chat`, status: 'info' },
      { ts: new Date().toISOString(), label: 'Bribing the hamster', detail: 'Spinning up MammothOS reasoning lanes', status: 'info' },
    ])
    setMeta(null)
    setExpandedThoughtIndex(-1)

    try {
      streamControllerRef.current = new AbortController()
      const body = {
        message,
        agent_id: effectiveAgentId,
        mode: 'chat',
        coding_intent: effectiveAgentId === 'coding_agent' ? codingIntent : undefined,
        page_context: { current_page: 'chat' },
      }
      await streamChat(body, effectiveAgentId, placeholderIndex)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chat request failed')
    } finally {
      setBusy(false)
      setStreaming(false)
      streamControllerRef.current = null
      await refreshOps()
    }
  }

  const clearLocalView = async () => {
    setHistory([])
    setThoughtSteps([])
    setMeta(null)
    setError('')
    setExpandedThoughtIndex(-1)
  }

  const dispatchQuickAction = (action) => {
    setAgentId(action.agentId)
    if (action.codingIntent) setCodingIntent(action.codingIntent)
    send(action.message, action.agentId)
  }

  return (
    <div className="page-enter" style={{ padding: 24, height: '100%', boxSizing: 'border-box', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 18, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '1.15rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10, margin: 0 }}>
            <Bot size={20} color="var(--photon)" /> MammothOS Chat
          </h1>
          <p style={{ margin: '6px 0 0', fontSize: '0.82rem', color: 'var(--txt-sec)', maxWidth: 760 }}>
            A separate native chat surface for MammothOS thinking, planning, and agent-assisted work — distinct from lesson tutoring.
          </p>
        </div>
        <button
          onClick={clearLocalView}
          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.8rem' }}
        >
          <Trash2 size={14} /> Clear view
        </button>
        <button
          onClick={() => setRightRailOpen((prev) => !prev)}
          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.8rem' }}
        >
          {showRightRail ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
          {showRightRail ? 'Hide right rail' : 'Show right rail'}
        </button>
      </div>

      <RuntimeStatusBanner title="MammothOS runtime" />

      <div style={{ display: 'grid', gridTemplateColumns: showInlineRightRail ? 'minmax(0, 2.3fr) minmax(340px, 1fr)' : 'minmax(0, 1fr)', gap: 18, flex: 1, minHeight: 0 }}>
        <div className="glass-card-solid" style={{ display: 'flex', flexDirection: 'column', minHeight: isShortViewport ? '80vh' : '84vh', overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)' }}>Current lane</div>
              <div style={{ fontSize: '0.92rem', color: selectedAgent.accent, fontWeight: 700 }}>{selectedAgent.label}</div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, color: 'var(--txt-sec)', fontSize: '0.76rem', padding: '6px 8px', cursor: 'pointer' }}
              >
                {AGENT_OPTIONS.map((option) => (
                  <option key={option.id} value={option.id}>{option.label}</option>
                ))}
              </select>
              {agentId === 'coding_agent' && (
                <select
                  value={codingIntent}
                  onChange={(e) => setCodingIntent(e.target.value)}
                  style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 8, color: 'var(--txt-sec)', fontSize: '0.76rem', padding: '6px 8px', cursor: 'pointer' }}
                >
                  <option value="patch_existing">Patch Existing Files</option>
                  <option value="generate_code">Generate Code</option>
                  <option value="refactor_code">Refactor Code</option>
                  <option value="analyze_codebase">Analyze Codebase</option>
                </select>
              )}
            </div>
          </div>

          <div style={{ padding: isShortViewport ? 14 : 16, borderBottom: '1px solid var(--border)', display: 'grid', gap: isShortViewport ? 8 : 10 }}>
            <button
              type="button"
              onClick={() => setQuickActionsOpen((prev) => !prev)}
              style={{ justifySelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderRadius: 999, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.72rem', cursor: 'pointer' }}
            >
              {quickActionsOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              {quickActionsOpen ? 'Hide templates' : 'Show templates'}
            </button>

            {quickActionsOpen && (
              <>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {SLASH_ACTIONS.map((action) => (
                    <button
                      key={action}
                      onClick={() => setInput(action)}
                      style={{ padding: '6px 10px', borderRadius: 999, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.72rem', cursor: 'pointer', fontFamily: 'JetBrains Mono,monospace' }}
                    >
                      {action}
                    </button>
                  ))}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: 10 }}>
                  {QUICK_ACTIONS.map((card) => (
                    <button
                      key={card.title}
                      onClick={() => dispatchQuickAction(card)}
                      disabled={busy}
                      style={{ textAlign: 'left', padding: '12px 14px', borderRadius: 12, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', cursor: 'pointer' }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
                        <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{card.title}</div>
                        <Workflow size={14} color="var(--txt-mut)" />
                      </div>
                      <div style={{ fontSize: '0.74rem', lineHeight: 1.5 }}>{card.message}</div>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 12, minHeight: 0 }}>
            {history.length === 0 && (
              <div style={{ margin: '24px auto', maxWidth: 680, textAlign: 'center' }}>
                <Sparkles size={28} color="var(--photon)" style={{ marginBottom: 10 }} />
                <p style={{ fontSize: '0.92rem', color: 'var(--txt-pri)', margin: '0 0 8px' }}>New MammothOS conversation</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--txt-mut)', margin: 0, lineHeight: 1.7 }}>
                  Use this when you want a normal AI chat feel without lesson guardrails, but still with the ability to hand work to agents.
                </p>
              </div>
            )}
            {history.map((entry, idx) => {
              const isUser = entry.role === 'user'
              const isStreamingBubble = !isUser && entry.stream
              return (
                <div key={`${entry.created_at || idx}-${idx}`} style={{ alignSelf: isUser ? 'flex-end' : 'flex-start', maxWidth: '94%' }}>
                  <div style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.12em' }}>
                    {isUser ? 'You' : entry.agent_id === 'assistant' ? 'MammothOS' : entry.agent_id?.replaceAll('_', ' ') || 'Assistant'}
                  </div>
                  <div style={{ background: isUser ? 'rgba(77,166,255,0.18)' : 'rgba(255,255,255,0.05)', border: `1px solid ${isUser ? 'rgba(77,166,255,0.35)' : isStreamingBubble ? 'rgba(77,166,255,0.25)' : 'rgba(255,255,255,0.08)'}`, borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px', padding: '13px 15px', color: 'var(--txt-pri)', fontSize: '0.9rem', lineHeight: 1.72, whiteSpace: 'pre-wrap', boxShadow: isStreamingBubble ? '0 0 0 1px rgba(77,166,255,0.08) inset' : 'none' }}>
                    {entry.message || (isStreamingBubble ? 'MammothOS is composing…' : '')}
                    {isStreamingBubble && busy && <span style={{ display: 'inline-block', width: 8, height: 8, marginLeft: 6, borderRadius: '50%', background: 'var(--cyan)', boxShadow: '0 0 10px var(--cyan)' }} />}
                  </div>
                  {!isUser && (entry.model || entry.adapter || entry.task_id) && (
                    <div style={{ marginTop: 5, fontSize: '0.68rem', color: 'var(--txt-mut)' }}>
                      {(entry.adapter || 'runtime')} • {(entry.model || 'unknown')}{entry.task_id ? ` • ${entry.task_id}` : ''}
                    </div>
                  )}
                  {!isUser && Array.isArray(entry.evidence_items) && entry.evidence_items.length > 0 && (
                    <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                      {entry.evidence_items.slice(0, 4).map((item, evidenceIdx) => (
                        <div key={`${item.agent_id || 'evidence'}-${evidenceIdx}`} style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)' }}>
                          <div style={{ fontSize: '0.68rem', color: 'var(--photon)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 4 }}>
                            {item.agent_id || 'source'} • {item.source || 'runtime'}
                          </div>
                          <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{item.summary || 'No evidence summary provided.'}</div>
                        </div>
                      ))}
                    </div>
                  )}
                  {!isUser && (
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
                      <button
                        onClick={() => saveTaskCardFromEntry(entry, { prompt: history[idx - 1]?.role === 'user' ? history[idx - 1].message : '' })}
                        style={{ padding: '5px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.68rem', cursor: 'pointer' }}
                      >
                        Save task card
                      </button>
                      {(entry.task_id || approvals.some((item) => item.agent_id === entry.agent_id && item.status === 'pending')) && (
                        <button
                          onClick={() => setPage?.('agent')}
                          style={{ padding: '5px 8px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.08)', color: 'var(--photon)', fontSize: '0.68rem', cursor: 'pointer' }}
                        >
                          Open handoff
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
            {busy && !streaming && (
              <div style={{ alignSelf: 'flex-start', padding: '10px 12px', borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)', fontSize: '0.8rem', color: 'var(--txt-mut)' }}>
                MammothOS is checking the herd…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div style={{ padding: 16, borderTop: '1px solid var(--border)' }}>
            {error && <div style={{ marginBottom: 10, color: '#f87171', fontSize: '0.78rem' }}>{error}</div>}
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    send()
                  }
                }}
                rows={4}
                placeholder="Ask MammothOS anything — debug, plan, patch, or think it through..."
                style={{ flex: 1, resize: 'vertical', minHeight: 88, maxHeight: 160, overflowY: 'auto', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, color: 'var(--txt-pri)', fontSize: '0.9rem', padding: '13px 15px', outline: 'none', lineHeight: 1.55 }}
              />
              <button
                onClick={() => send()}
                disabled={busy}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, minWidth: 132, padding: '12px 14px', borderRadius: 12, border: 'none', background: busy ? 'rgba(77,166,255,0.35)' : 'linear-gradient(90deg,var(--photon),var(--cyan))', color: '#050608', fontWeight: 700, cursor: busy ? 'not-allowed' : 'pointer' }}
              >
                <Send size={15} /> {busy ? 'Thinking…' : 'Send'}
              </button>
            </div>
          </div>
        </div>

        {showDrawerRightRail && (
          <button
            type="button"
            onClick={() => setRightRailOpen(false)}
            aria-label="Close right rail"
            style={{ position: 'fixed', inset: 0, border: 'none', background: 'rgba(4,8,12,0.56)', zIndex: 35, cursor: 'pointer' }}
          />
        )}
        {showRightRail && (
        <div style={showDrawerRightRail ? { position: 'fixed', top: 86, right: 18, width: 'min(420px, calc(100vw - 36px))', maxHeight: 'calc(100vh - 110px)', zIndex: 40, display: 'grid', gap: isShortViewport ? 12 : 16, minHeight: 0, minWidth: 0, alignContent: 'start', overflowY: 'auto', paddingRight: 4 } : { display: 'grid', gap: isShortViewport ? 12 : 16, minHeight: 0, minWidth: 0, alignContent: 'start', overflowY: 'auto', maxHeight: isShortViewport ? '80vh' : '84vh', paddingRight: 4 }}>
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              onClick={() => setRightRailOpen(false)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 10px', borderRadius: 999, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.72rem', cursor: 'pointer' }}
            >
              <ChevronRight size={14} />
              Collapse rail
            </button>
          </div>
          <div className="glass-card-solid" style={{ padding: isShortViewport ? 14 : 16 }}>
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700, marginBottom: 10 }}>
              Routing Snapshot
            </p>
            <div style={{ display: 'grid', gap: 8, minWidth: 0 }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--txt-sec)' }}>Agent: <span style={{ color: selectedAgent.accent, fontWeight: 700 }}>{selectedAgent.label}</span></div>
              <div style={{ fontSize: '0.76rem', color: 'var(--txt-mut)', lineHeight: 1.6, overflowWrap: 'anywhere' }}>{selectedAgent.detail}</div>
              {meta && (
                <>
                  <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)', overflowWrap: 'anywhere' }}>Adapter: <span style={{ color: 'var(--photon)' }}>{meta.adapter}</span></div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)', overflowWrap: 'anywhere' }}>Model / Runtime: <span style={{ color: 'var(--photon)' }}>{meta.model}</span></div>
                  <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)' }}>Dispatch: <span style={{ color: meta.dispatched ? 'var(--cyan)' : '#22c55e' }}>{meta.dispatched ? 'agent-runtime' : 'native-chat'}</span></div>
                </>
              )}
            </div>
          </div>

          <ThoughtTrail steps={thoughtSteps} busy={busy} expandedIndex={expandedThoughtIndex} compact={isShortViewport} onToggle={(idx) => setExpandedThoughtIndex((cur) => (cur === idx ? -1 : idx))} />

          <div className="glass-card-solid" style={{ padding: isShortViewport ? 14 : 16 }}>
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700, marginBottom: 10 }}>
              Saved Task Cards
            </p>
            <div style={{ display: 'grid', gap: 8 }}>
              {taskCards.length > 0 ? taskCards.slice(0, 6).map((card) => (
                <button
                  key={card.id}
                  onClick={() => loadTaskCard(card)}
                  style={{ textAlign: 'left', padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)', cursor: 'pointer' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: '0.78rem', fontWeight: 700 }}>{card.title}</span>
                    <span style={{ fontSize: '0.66rem', color: 'var(--txt-mut)' }}>{card.agent_id}</span>
                  </div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', lineHeight: 1.5, overflowWrap: 'anywhere' }}>{(card.prompt || card.reply || '').slice(0, 120)}</div>
                </button>
              )) : <div style={{ fontSize: '0.78rem', color: 'var(--txt-mut)' }}>Save a reply to pin it as a reusable task card.</div>}
            </div>
          </div>

          <div className="glass-card-solid" style={{ padding: isShortViewport ? 14 : 16 }}>
            <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700, marginBottom: 10 }}>
              Approval + Run Handoff
            </p>
            <div style={{ display: 'grid', gap: 10 }}>
              <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--txt-pri)', marginBottom: 4 }}>
                  Pending approvals: {approvals.filter((item) => item.status === 'pending').length}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', overflowWrap: 'anywhere' }}>
                  {approvals.filter((item) => item.status === 'pending').slice(0, 2).map((item) => `${item.operation} • ${item.target}`).join(' • ') || 'No approvals waiting.'}
                </div>
              </div>
              <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--txt-pri)', marginBottom: 4 }}>
                  Recent autonomous runs: {autonomousRuns.summary?.total_runs || 0}
                </div>
                <div style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', overflowWrap: 'anywhere' }}>
                  {autonomousRuns.runs.slice(0, 2).map((run) => `${run.plan_status} • ${run.objective || 'Unnamed run'}`).join(' • ') || 'No autonomous runs recorded yet.'}
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button
                  onClick={() => setPage?.('agent')}
                  style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.08)', color: 'var(--photon)', fontSize: '0.74rem', cursor: 'pointer' }}
                >
                  Open Agent Console
                </button>
                <button
                  onClick={() => setInput('/approvals')}
                  style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.74rem', cursor: 'pointer' }}
                >
                  Inspect approvals
                </button>
                <button
                  onClick={() => setInput('/runs')}
                  style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.74rem', cursor: 'pointer' }}
                >
                  Inspect runs
                </button>
              </div>
            </div>
          </div>
        </div>
        )}
      </div>
    </div>
  )
}
