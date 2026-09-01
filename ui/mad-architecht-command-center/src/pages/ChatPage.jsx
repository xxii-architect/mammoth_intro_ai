import { useEffect, useMemo, useRef, useState } from 'react'
import { Bot, MessageSquare, Sparkles, Wrench, Brain, Terminal, Send, Trash2, ChevronDown, ChevronRight, Workflow, Copy, Check, Plus, X, GitBranch, FolderGit2 } from 'lucide-react'
import { api, authorizedFetch } from '../api/client'
import { useAuth } from '../lib/authContext'
import ChatMessageBody from '../components/ChatMessageBody'
import AtlasMemoryBadge from '../components/AtlasMemoryBadge'
import GuideStepPanel from '../components/GuideStepPanel'

const TASK_CARD_STORAGE_KEY = 'mammoth_chat_task_cards_v1'

// ─── Repo picker helpers ────────────────────────────────────────────────────

function loadRepos(userId) {
  try {
    const raw = localStorage.getItem(`mammoth_repos:${userId}`)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch { return [] }
}

function saveRepos(userId, repos) {
  localStorage.setItem(`mammoth_repos:${userId}`, JSON.stringify(repos.slice(0, 20)))
}

function loadActiveRepo(userId) {
  try {
    return localStorage.getItem(`mammoth_active_repo:${userId}`) || null
  } catch { return null }
}

function saveActiveRepo(userId, repoId) {
  if (repoId) localStorage.setItem(`mammoth_active_repo:${userId}`, repoId)
  else localStorage.removeItem(`mammoth_active_repo:${userId}`)
}

// Convert a GitHub-format string (owner/repo) or path to a root string for repo_context
function repoToRoot(repo) {
  if (!repo) return null
  const entry = typeof repo === 'string' ? repo : repo.value
  if (!entry) return null
  // GitHub format: owner/repo → we pass it as-is and let backend use git remote context
  // Local path: /opt/... or C:\... → use directly
  return entry.trim()
}

// ────────────────────────────────────────────────────────────────────────────

const AGENT_OPTIONS = [
  { id: 'assistant', label: 'Mammoth Assistant', Icon: MessageSquare, accent: 'var(--photon)', detail: 'Normal AI chat for planning, debugging, and product thinking.' },
  { id: 'coding_agent', label: 'Coding Agent', Icon: Wrench, accent: 'var(--cyan)', detail: 'Repo-focused coding help, patch strategy, and implementation tasks.' },
  { id: 'reasoning_agent', label: 'Reasoning Agent', Icon: Brain, accent: 'var(--violet)', detail: 'Break down decisions, tradeoffs, and next steps.' },
  { id: 'shell_agent', label: 'Shell Agent', Icon: Terminal, accent: '#22c55e', detail: 'Command-oriented ops thinking within the safe shell runtime.' },
  { id: 'mammoth_guide', label: 'MammothOS Guide', Icon: MessageSquare, accent: 'var(--accent-guide)' },
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
  '/guide Walk me through the MammothOS SDK entry points',
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
  return null
}

function inferRepoTargets(message) {
  const text = String(message || '')

  // Highlighted text in the UI
  const selection =
    typeof window !== 'undefined' && window.getSelection
      ? String(window.getSelection() || '').trim()
      : ''

  // File paths inside the message (src/pages/..., components/..., etc.)
  const fileMatches = text.match(/(?:src|app|components|pages)[\\/][A-Za-z0-9_.\\/-]+/g) || []

  // Windows-style absolute paths (C:\folder\file.js)
  const windowsMatches = text.match(/(?:[A-Za-z]:)?[\\/](?:[A-Za-z0-9_.-]+[\\/])+(?:[A-Za-z0-9_.-]+)/g) || []

  // Code blocks
  const codeBlock = text.includes('```') ? text : null

  const all = [
    ...(fileMatches || []),
    ...(windowsMatches || []),
    selection || null,
    codeBlock || null
  ].filter(Boolean)

  // Normalize slashes and dedupe
  const normalized = [...new Set(all.map((item) => item.replace(/\\/g, '/').trim()))]

  return normalized.length > 0 ? normalized : null
}

function inferWebTargets(message) {
  const urls = String(message || '').match(/https?:\/\/[^\s]+/g)
  return urls || null
}

function buildLivePageContext() {
  const selection = typeof window !== 'undefined' && window.getSelection ? String(window.getSelection() || '').trim() : ''
  return {
    current_page: 'chat',
    route: typeof window !== 'undefined' ? window.location.pathname : '/chat',
    url: typeof window !== 'undefined' ? window.location.href : '',
    title: typeof document !== 'undefined' ? document.title : 'MammothOS Chat',
    selected_text: selection ? selection.slice(0, 400) : '',
    updated_at: new Date().toISOString(),
  }
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

function ChatBubble({ entry, busy, streaming, approvals, prevMessage, onSaveCard, onOpenHandoff }) {
  const [copied, setCopied] = useState(false)
  const isUser = entry.role === 'user'
  const isStreamingBubble = !isUser && entry.stream

  const agentLabel = isUser
    ? 'You'
    : entry.agent_id === 'assistant'
      ? 'MammothOS'
      : (entry.agent_id || 'assistant').replaceAll('_', ' ')

  const hasHandoff = !isUser && (entry.task_id || (Array.isArray(approvals) && approvals.some((a) => a.agent_id === entry.agent_id && a.status === 'pending')))

  const copyMessage = async () => {
    if (!entry.message) return
    try {
      await navigator.clipboard.writeText(entry.message)
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch { /* no-op */ }
  }

  return (
    <div style={{ alignSelf: isUser ? 'flex-end' : 'flex-start', maxWidth: '98%' }}>
      {/* Sender label */}
      <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.12em', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>{agentLabel}</span>
        {!isUser && entry.created_at && (
          <span style={{ fontWeight: 400 }}>{new Date(entry.created_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>
        )}
      </div>

      {/* Bubble */}
      <div style={{
        background: isUser ? 'rgba(77,166,255,0.15)' : 'rgba(255,255,255,0.04)',
        border: `1px solid ${isUser ? 'rgba(77,166,255,0.3)' : isStreamingBubble ? 'rgba(77,166,255,0.2)' : 'rgba(255,255,255,0.08)'}`,
        borderRadius: isUser ? '14px 14px 4px 14px' : '4px 14px 14px 14px',
        padding: '16px 18px',
        color: 'var(--txt-pri)',
        fontSize: '0.94rem',
        lineHeight: 1.8,
        boxShadow: isStreamingBubble ? '0 0 0 1px rgba(77,166,255,0.06) inset' : 'none',
        position: 'relative',
      }}>
        {isUser
          ? <div style={{ whiteSpace: 'pre-wrap' }}>{entry.message}</div>
          : entry.message
            ? <ChatMessageBody text={entry.message} />
            : (isStreamingBubble
              ? <span style={{ color: 'var(--txt-mut)' }}>MammothOS is composing…</span>
              : null)
        }
        {isStreamingBubble && busy && (
          <span style={{ display: 'inline-block', width: 8, height: 8, marginLeft: 6, borderRadius: '50%', background: 'var(--cyan)', boxShadow: '0 0 10px var(--cyan)', verticalAlign: 'middle' }} />
        )}
      </div>

      {/* Meta row */}
      {!isUser && (entry.model || entry.adapter || entry.task_id) && (
        <div style={{ marginTop: 4, fontSize: '0.66rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
          {(entry.adapter || 'runtime')} • {(entry.model || 'unknown')}{entry.task_id ? ` • ${entry.task_id}` : ''}
        </div>
      )}

      {/* Guide step panel for mammoth_guide responses */}
      {!isUser && Array.isArray(entry.guide_steps) && entry.guide_steps.length > 0 && (
        <GuideStepPanel steps={entry.guide_steps} branch={entry.guide_branch} query={prevMessage?.message} />
      )}

      {/* Evidence cards */}
      {!isUser && Array.isArray(entry.evidence_items) && entry.evidence_items.length > 0 && (
        <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
          {entry.evidence_items.slice(0, 4).map((item, i) => (
            <div key={`${item.agent_id || 'e'}-${i}`} style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.025)' }}>
              <div style={{ fontSize: '0.66rem', color: 'var(--photon)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 3 }}>
                {item.agent_id || 'source'} • {item.source || 'runtime'}
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{item.summary || 'No summary.'}</div>
            </div>
          ))}
        </div>
      )}

      {/* Action row for assistant messages */}
      {!isUser && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 7, alignItems: 'center' }}>
          <button
            type="button"
            onClick={copyMessage}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 8px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-mut)', fontSize: '0.66rem', cursor: 'pointer' }}
          >
            {copied ? <Check size={11} color="#22c55e" /> : <Copy size={11} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button
            type="button"
            onClick={onSaveCard}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 8px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.66rem', cursor: 'pointer' }}
          >
            Save card
          </button>
          {hasHandoff && (
            <button
              type="button"
              onClick={onOpenHandoff}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 8px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.08)', color: 'var(--photon)', fontSize: '0.66rem', cursor: 'pointer' }}
            >
              Open handoff →
            </button>
          )}
        </div>
      )}
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
  const [quickActionsOpen, setQuickActionsOpen] = useState(false)
  const [taskCards, setTaskCards] = useState(() => loadTaskCards())
  const [approvals, setApprovals] = useState([])
  const [autonomousRuns, setAutonomousRuns] = useState({ summary: null, runs: [] })
  const [isNarrowLayout, setIsNarrowLayout] = useState(() => (typeof window !== 'undefined' ? window.innerWidth < 1540 : false))
  const [isShortViewport, setIsShortViewport] = useState(() => (typeof window !== 'undefined' ? window.innerHeight < 860 : false))
  const [isMobile, setIsMobile] = useState(() => (typeof window !== 'undefined' ? window.innerWidth < 768 : false))
  const [rightRailOpen, setRightRailOpen] = useState(false)
  const [sessionResumed, setSessionResumed] = useState(false)
  // Repo picker state
  const [repos, setRepos] = useState([])
  const [activeRepoId, setActiveRepoId] = useState(null)
  const [repoInput, setRepoInput] = useState('')
  const [repoPickerOpen, setRepoPickerOpen] = useState(false)
  const bottomRef = useRef(null)
  const streamControllerRef = useRef(null)
  const { user } = useAuth()
  const scopeUserId = user?.id || 'local'

  const refreshOps = async () => {
    try {
      const [approvalList, runData] = await Promise.all([
        api(`/approvals?user_id=${encodeURIComponent(scopeUserId)}`),
        api(`/autonomous/runs?user_id=${encodeURIComponent(scopeUserId)}`),

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
    let stored = null
    try {
      stored = typeof window !== 'undefined' ? JSON.parse(window.localStorage.getItem(`mammoth_chat_history:${scopeUserId}`) || 'null') : null
    } catch {
      stored = null
    }
    if (Array.isArray(stored) && stored.length > 0) {
      setHistory(stored)
    }
    api('/mammoth/chat/history')
      .then((data) => {
        const chatHistory = Array.isArray(data?.chat_history) ? data.chat_history : []
        const nextHistory = chatHistory.length > 0 ? chatHistory : stored || []
        setHistory(nextHistory)
        const lastAssistant = [...nextHistory].reverse().find((entry) => entry.role === 'assistant')
        if (lastAssistant?.thought_steps) {
          setThoughtSteps(lastAssistant.thought_steps)
        }
      })
      .catch(() => {
        if (Array.isArray(stored) && stored.length > 0) {
          setHistory(stored)
        }
      })
    refreshOps()
  }, [scopeUserId])

  // Load repos from per-user localStorage
  useEffect(() => {
    const stored = loadRepos(scopeUserId)
    setRepos(stored)
    const active = loadActiveRepo(scopeUserId)
    setActiveRepoId(active || (stored[0]?.id || null))
  }, [scopeUserId])

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (history.length > 0) {
      window.localStorage.setItem(`mammoth_chat_history:${scopeUserId}`, JSON.stringify(history.slice(-50)))
    } else {
      window.localStorage.removeItem(`mammoth_chat_history:${scopeUserId}`)
    }
  }, [history, scopeUserId])

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
      setIsMobile(window.innerWidth < 768)
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    if (typeof document === 'undefined') return undefined
    document.body.style.overflow = rightRailOpen && isNarrowLayout ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [rightRailOpen, isNarrowLayout])

  const selectedAgent = useMemo(() => AGENT_OPTIONS.find((item) => item.id === agentId) || AGENT_OPTIONS[0], [agentId])
  const showRightRail = rightRailOpen
  const showInlineRightRail = showRightRail && !isNarrowLayout
  const showDrawerRightRail = showRightRail && isNarrowLayout

  // Active repo for context
  const activeRepo = repos.find((r) => r.id === activeRepoId) || repos[0] || null
  const activeRepoRoot = activeRepo ? repoToRoot(activeRepo) : '/opt/mammothos/mammoth_intro_ai'

  const addRepo = () => {
    const val = repoInput.trim()
    if (!val) return
    const id = `repo-${Date.now()}`
    const newRepo = { id, value: val, label: val, added_at: new Date().toISOString() }
    const next = [newRepo, ...repos].slice(0, 20)
    setRepos(next)
    saveRepos(scopeUserId, next)
    setActiveRepoId(id)
    saveActiveRepo(scopeUserId, id)
    setRepoInput('')
  }

  const removeRepo = (id) => {
    const next = repos.filter((r) => r.id !== id)
    setRepos(next)
    saveRepos(scopeUserId, next)
    if (activeRepoId === id) {
      const nextActive = next[0]?.id || null
      setActiveRepoId(nextActive)
      saveActiveRepo(scopeUserId, nextActive)
    }
  }

  const switchRepo = (id) => {
    setActiveRepoId(id)
    saveActiveRepo(scopeUserId, id)
  }

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
      status: 'queued',
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
    const patchedBody = {
        ...body,
        user_id: user?.id,
        slash: body.slash || null,
        repo: inferRepoTargets(body.message),
        web: inferWebTargets(body.message),
    };

    const response = await authorizedFetch('/mammoth/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patchedBody),
      signal: streamControllerRef.current?.signal,
    });

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
        } else if (Array.isArray(payload.guide_steps) && payload.guide_steps.length) {
          // Inject guide_steps into the placeholder bubble if history not replaced
          setHistory((prev) => {
            const next = [...prev]
            if (placeholderIndex >= 0 && next[placeholderIndex]) {
              next[placeholderIndex] = {
                ...next[placeholderIndex],
                guide_steps: payload.guide_steps,
                guide_branch: payload.guide_branch || 'main',
                adapter: payload.adapter || next[placeholderIndex].adapter,
                stream: false,
              }
            }
            return next
          })
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
        const summaryStatus = ops.autonomousRuns.summary?.latest_run_status || latestRun?.plan_status || 'unknown'
        const label = ops.autonomousRuns.summary?.latest_run_label || latestRun?.run_label || latestRun?.objective || 'Autonomous run'
        appendSystemMessage(
          latestRun
            ? `Latest autonomous run: ${label} • ${(latestRun.progress?.completed || 0)}/${(latestRun.progress?.total || 0)} complete. Current status: ${summaryStatus}.`
            : 'No autonomous runs recorded yet.',
          { evidence_items: ops.autonomousRuns.runs.slice(0, 3).map((run) => ({ agent_id: run.current_lane?.agent_id || 'orchestrator', summary: `${run.run_label || run.objective || 'Autonomous run'} • ${run.plan_status || 'unknown'}`, source: run.source || 'autonomous-run', status: run.plan_status })) },
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
      { ts: new Date().toISOString(), label: 'Priming mammoth cores', detail: 'Spinning up MammothOS reasoning lanes', status: 'info' },
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
        page_context: buildLivePageContext(),
        repo_context: {
          root: activeRepoRoot,
          query: message,
          branch: 'main',
          files: effectiveAgentId === 'mammoth_guide'
            ? [
                'src/mammoth_os/sdk.py',
                'src/mammoth_os/agents/mammoth_guide_agent.py',
                'src/mammoth_os/agent_registry.py',
                'src/mammoth_os/__init__.py',
                'api_server.py',
              ]
            : [],
          include_git_status: effectiveAgentId === 'coding_agent' || effectiveAgentId === 'reasoning_agent',
          max_results: effectiveAgentId === 'coding_agent' || effectiveAgentId === 'reasoning_agent' ? 4 : 2,
          max_snippets: effectiveAgentId === 'mammoth_guide' ? 4 : (effectiveAgentId === 'coding_agent' || effectiveAgentId === 'reasoning_agent' ? 3 : 2),
        },
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
    try {
      await authorizedFetch('/mammoth/chat/history', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
      })

    } catch (e) {
      console.warn('Failed to clear chat history on backend:', e)
    }
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(`mammoth_chat_history:${scopeUserId}`)
    }
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
          onClick={() => setRightRailOpen((prev) => !prev)}
          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.8rem' }}
        >
          {showRightRail ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
          {showRightRail ? 'Hide right rail' : 'Show right rail'}
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: showInlineRightRail ? 'minmax(0, 2.3fr) minmax(340px, 1fr)' : 'minmax(0, 1fr)', gap: 18, flex: 1, minHeight: 0 }}>
        <div className="glass-card-solid" style={{ display: 'flex', flexDirection: 'column', minHeight: isShortViewport ? '84vh' : '90vh', overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)' }}>Current lane</div>
              <div style={{ fontSize: '0.92rem', color: selectedAgent.accent, fontWeight: 700 }}>{selectedAgent.label}</div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <button
                onClick={clearLocalView}
                title="New Chat — clear history and start fresh"
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(var(--photon-rgb,99,102,241),0.35)', background: 'rgba(99,102,241,0.10)', color: 'var(--photon)', cursor: 'pointer', fontSize: '0.76rem', fontWeight: 600 }}
              >
                <Plus size={13} /> New Chat
              </button>
              {history.length > 0 && (
                <button
                  onClick={clearLocalView}
                  title="Delete Chat — permanently clear all messages"
                  style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 8, border: '1px solid rgba(239,68,68,0.35)', background: 'rgba(239,68,68,0.08)', color: '#f87171', cursor: 'pointer', fontSize: '0.76rem', fontWeight: 600 }}
                >
                  <Trash2 size={13} /> Delete Chat
                </button>
              )}
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

          <div style={{ flex: 1, overflowY: 'auto', padding: '22px 24px', display: 'flex', flexDirection: 'column', gap: 16, minHeight: 0 }}>
            {history.length === 0 && (
              <div style={{ margin: '24px auto', maxWidth: 680, textAlign: 'center' }}>
                <Sparkles size={28} color="var(--photon)" style={{ marginBottom: 10 }} />
                <p style={{ fontSize: '0.92rem', color: 'var(--txt-pri)', margin: '0 0 8px' }}>New MammothOS conversation</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--txt-mut)', margin: 0, lineHeight: 1.7 }}>
                  Use this when you want a normal AI chat feel without lesson guardrails, but still with the ability to hand work to agents.
                </p>
              </div>
            )}
            {history.map((entry, idx) => (
              <ChatBubble
                key={`${entry.created_at || idx}-${idx}`}
                entry={entry}
                busy={busy}
                streaming={streaming}
                approvals={approvals}
                prevMessage={history[idx - 1]}
                onSaveCard={() => saveTaskCardFromEntry(entry, { prompt: history[idx - 1]?.role === 'user' ? history[idx - 1].message : '' })}
                onOpenHandoff={() => setPage?.('agent')}
              />
            ))}
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
                rows={isMobile ? 2 : 4}
                placeholder="Ask MammothOS anything — debug, plan, patch, or think it through..."
                  style={{ flex: 1, resize: 'vertical', minHeight: 100, maxHeight: 240, overflowY: 'auto', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, color: 'var(--txt-pri)', fontSize: '0.94rem', padding: '14px 16px', outline: 'none', lineHeight: 1.6 }}
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
            style={{ position: 'fixed', inset: 0, border: 'none', background: 'rgba(2, 6, 12, 0.72)', backdropFilter: 'blur(2px)', zIndex: 35, cursor: 'pointer' }}
          />
        )}
        {showRightRail && (
        <div style={showDrawerRightRail ? { position: 'fixed', top: 86, right: 18, width: 'min(420px, calc(100vw - 36px))', maxHeight: 'calc(100vh - 110px)', zIndex: 40, display: 'grid', gap: isShortViewport ? 12 : 16, minHeight: 0, minWidth: 0, alignContent: 'start', overflowY: 'auto', paddingRight: 4, background: 'rgba(7, 12, 18, 0.9)', border: '1px solid var(--border)', borderRadius: 18, boxShadow: '0 24px 60px rgba(0,0,0,0.38)', padding: 12 } : { display: 'grid', gap: isShortViewport ? 12 : 16, minHeight: 0, minWidth: 0, alignContent: 'start', overflowY: 'auto', maxHeight: isShortViewport ? '80vh' : '84vh', paddingRight: 4 }}>
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

          {/* ─── Repo Context Picker ─────────────────────────────────────── */}
          <div className="glass-card-solid" style={{ padding: isShortViewport ? 14 : 16, borderLeft: '3px solid var(--cyan)' }}>
            <button
              type="button"
              onClick={() => setRepoPickerOpen((p) => !p)}
              style={{ width: '100%', textAlign: 'left', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-pri)' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <FolderGit2 size={14} color="var(--cyan)" />
                  <p style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700, margin: 0 }}>Repo Context</p>
                </div>
                {repoPickerOpen ? <ChevronDown size={13} color="var(--txt-mut)" /> : <ChevronRight size={13} color="var(--txt-mut)" />}
              </div>
            </button>
            {/* Active repo badge */}
            <div style={{ marginTop: 8, fontSize: '0.76rem', color: 'var(--txt-sec)' }}>
              Active: <span style={{ color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace', fontWeight: 700 }}>
                {activeRepo?.label || activeRepo?.value || 'default (server)'}
              </span>
            </div>

            {repoPickerOpen && (
              <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
                {/* Add repo */}
                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    value={repoInput}
                    onChange={(e) => setRepoInput(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') addRepo() }}
                    placeholder="owner/repo or /local/path"
                    style={{ flex: 1, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, color: 'var(--txt-pri)', fontSize: '0.76rem', padding: '7px 10px', outline: 'none', fontFamily: 'JetBrains Mono,monospace' }}
                  />
                  <button
                    type="button"
                    onClick={addRepo}
                    disabled={!repoInput.trim()}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '7px 10px', borderRadius: 8, border: '1px solid rgba(77,166,255,0.3)', background: 'rgba(77,166,255,0.12)', color: 'var(--photon)', fontSize: '0.74rem', cursor: repoInput.trim() ? 'pointer' : 'not-allowed', opacity: repoInput.trim() ? 1 : 0.5 }}
                  >
                    <Plus size={13} /> Add
                  </button>
                </div>
                <p style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', margin: 0, lineHeight: 1.5 }}>
                  GitHub: <code style={{ color: 'var(--photon)' }}>owner/repo</code> · Local: <code style={{ color: 'var(--photon)' }}>/opt/path</code>
                </p>

                {/* Repo list */}
                {repos.length > 0 && (
                  <div style={{ display: 'grid', gap: 6 }}>
                    {repos.map((repo) => (
                      <div
                        key={repo.id}
                        style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 10px', borderRadius: 9, border: `1px solid ${activeRepoId === repo.id ? 'rgba(77,166,255,0.35)' : 'var(--border)'}`, background: activeRepoId === repo.id ? 'rgba(77,166,255,0.08)' : 'rgba(255,255,255,0.025)', cursor: 'pointer' }}
                        onClick={() => switchRepo(repo.id)}
                      >
                        <GitBranch size={12} color={activeRepoId === repo.id ? 'var(--cyan)' : 'var(--txt-mut)'} />
                        <span style={{ flex: 1, fontSize: '0.74rem', fontFamily: 'JetBrains Mono,monospace', color: activeRepoId === repo.id ? 'var(--photon)' : 'var(--txt-sec)', overflowWrap: 'anywhere', wordBreak: 'break-all' }}>{repo.label || repo.value}</span>
                        {activeRepoId === repo.id && <Check size={12} color="var(--cyan)" />}
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); removeRepo(repo.id) }}
                          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', padding: 2, display: 'flex' }}
                        >
                          <X size={12} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {repos.length === 0 && (
                  <p style={{ fontSize: '0.74rem', color: 'var(--txt-mut)', margin: 0, lineHeight: 1.5 }}>
                    No repos added yet. Add one above to give context to any agent.
                  </p>
                )}
              </div>
            )}
          </div>
          {/* ─────────────────────────────────────────────────────────────── */}
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
