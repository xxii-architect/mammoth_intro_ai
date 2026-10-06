import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Bot, MessageSquare, Sparkles, Wrench, Brain, Terminal, Send, Trash2, ChevronDown, ChevronRight, Workflow, Copy, Check, Plus, X, PanelLeft, Paperclip, Square } from 'lucide-react'
import { api, authorizedFetch } from '../api/client'
import { useAuth } from '../lib/authContext'
import { startAgentRun, resolveRunApproval, cancelAgentRun, reduceRunEvent } from '../lib/agentRuns'
import RunTimeline from '../components/RunTimeline'
import ChatMessageBody from '../components/ChatMessageBody'
import AgentResultPanel from '../components/AgentResultPanel'
import AtlasMemoryBadge from '../components/AtlasMemoryBadge'
import GuideStepPanel from '../components/GuideStepPanel'
import AgentThinkingIndicator from '../components/AgentThinkingIndicator'
import ChatThreadSidebar from '../components/ChatThreadSidebar'
import FileAttachmentPanel from '../components/FileAttachmentPanel'
import { TrustBadgeRow } from '../components/TrustSurfaces'
import RepoSourcesPanel from '../components/RepoSourcesPanel'
import MessageRating, { isRateable, messageFeedbackKey } from '../components/MessageRating'

const TASK_CARD_STORAGE_KEY = 'mammoth_chat_task_cards_v1'

function safeStorageGet(key, fallback = null) {
  if (typeof window === 'undefined') return fallback
  try {
    const value = window.localStorage.getItem(key)
    return value === null ? fallback : value
  } catch {
    return fallback
  }
}

function safeStorageSet(key, value) {
  if (typeof window === 'undefined') return false
  try {
    window.localStorage.setItem(key, value)
    return true
  } catch {
    return false
  }
}

function safeStorageRemove(key) {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.removeItem(key)
  } catch {
    // no-op: storage protections should never crash the UI
  }
}


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
    const raw = safeStorageGet(TASK_CARD_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function saveTaskCards(cards) {
  safeStorageSet(TASK_CARD_STORAGE_KEY, JSON.stringify(cards.slice(0, 20)))
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

function labelForAgent(agentId) {
  const found = AGENT_OPTIONS.find((item) => item.id === agentId)
  if (found?.label) return found.label
  return (agentId || 'assistant').replaceAll('_', ' ')
}

function buildSuccessToast({ agentId, keyResult, nextAction }) {
  const resultText = String(keyResult || '').trim()
  const actionText = String(nextAction || '').trim()
  return {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 7)}`,
    title: `${labelForAgent(agentId)} run completed`,
    keyResult: resultText || 'Response delivered to chat.',
    nextAction: actionText || 'Review the latest response and continue.',
  }
}

function deriveSuccessDetailsFromMessage(message, fallbackResult = '') {
  const structured = parseStructuredAgentMessage(message)
  if (structured && typeof structured === 'object') {
    const result = structured.result && typeof structured.result === 'object' ? structured.result : {}
    return {
      keyResult: structured.summary || result.summary || structured.message || fallbackResult,
      nextAction: structured.next_action || result.next_action || structured.runtime_notice?.next_action || '',
    }
  }
  const plain = String(message || '').trim().replace(/\s+/g, ' ')
  return {
    keyResult: plain ? plain.slice(0, 170) : fallbackResult,
    nextAction: '',
  }
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
  const filenameMatches = text.match(/\b[A-Za-z0-9_.-]+\.(?:py|js|jsx|ts|tsx|md|json|toml|ya?ml|sql|sh|ps1)\b/g) || []

  // Windows-style absolute paths (C:\folder\file.js)
  const windowsMatches = text.match(/(?:[A-Za-z]:)?[\\/](?:[A-Za-z0-9_.-]+[\\/])+(?:[A-Za-z0-9_.-]+)/g) || []

  // Code blocks
  const codeBlock = text.includes('```') ? text : null

  const all = [
    ...(fileMatches || []),
    ...(filenameMatches || []),
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

function parseStructuredAgentMessage(message) {
  if (typeof message !== 'string') return null
  const trimmed = message.trim()
  if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) return null
  try {
    const parsed = JSON.parse(trimmed)
    if (!parsed || typeof parsed !== 'object') return null
    const hasReadableAgentShape =
      typeof parsed.status === 'string' ||
      typeof parsed.summary === 'string' ||
      Array.isArray(parsed.quality_flags) ||
      typeof parsed.agent === 'string'
    return hasReadableAgentShape ? parsed : null
  } catch {
    return null
  }
}

function normalizeConfidence(value, fallback = 0.74) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return fallback
  if (numeric > 1) return Math.max(0, Math.min(1, numeric / 100))
  return Math.max(0, Math.min(1, numeric))
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

function ChatBubble({ entry, busy, streaming, approvals, prevMessage, onSaveCard, onOpenHandoff, onRunDecision, rating, onRate }) {
  const [copied, setCopied] = useState(false)
  const isUser = entry.role === 'user'
  const isStreamingBubble = !isUser && entry.stream
  const structuredResult = !isUser ? parseStructuredAgentMessage(entry.message) : null
  const contradictionFlags = !isUser
    ? (
      Array.isArray(structuredResult?.contradictions)
        ? structuredResult.contradictions
        : Array.isArray(structuredResult?.quality_flags)
          ? structuredResult.quality_flags.filter((flag) => String(flag).toLowerCase().includes('contrad'))
          : entry.trust_metadata?.has_contradictions
            ? ['Potential contradiction signals detected in trust metadata.']
          : []
    )
    : []
  const evidenceItems = Array.isArray(entry.evidence_items) ? entry.evidence_items : []
  const evidenceDerivedSourceCount = evidenceItems.reduce((count, item) => {
    if (!item || typeof item !== 'object') return count
    const nested = ['files', 'source_files', 'references', 'evidence', 'citations']
      .map((key) => (Array.isArray(item[key]) ? item[key].length : 0))
      .reduce((a, b) => a + b, 0)
    if (nested > 0) return count + nested
    return count + 1
  }, 0)
  const trustCitationCount = Number(entry.trust_metadata?.citation_count)
  const sourceCount = !isUser
    ? (
      Array.isArray(structuredResult?.citations) ? structuredResult.citations.length
        : Array.isArray(structuredResult?.sources) ? structuredResult.sources.length
          : Array.isArray(structuredResult?.references) ? structuredResult.references.length
            : Number.isFinite(trustCitationCount) ? trustCitationCount
              : evidenceDerivedSourceCount
    )
    : 0
  const providerLabel = String(
    entry.adapter
      || entry.trust_metadata?.provider
      || structuredResult?.provider
      || structuredResult?.runtime_state?.provider
      || 'unknown'
  )
  const confidenceScore = normalizeConfidence(
    entry.trust_metadata?.confidence
    ?? entry.runtime_status?.confidence
    ?? structuredResult?.confidence
    ?? structuredResult?.confidence_score
    ?? entry.confidence
  )

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
        {!isUser && entry.run && (
          <RunTimeline
            run={entry.run}
            busy={busy && entry.run.status !== 'awaiting_approval'}
            onApprove={() => onRunDecision?.(entry, 'approve')}
            onReject={() => onRunDecision?.(entry, 'reject')}
          />
        )}
        {isUser
          ? <div style={{ whiteSpace: 'pre-wrap' }}>{entry.message}</div>
          : entry.message
            ? (structuredResult
              ? <AgentResultPanel result={structuredResult} rawJson={entry.message} agentId={entry.agent_id} />
              : <ChatMessageBody text={entry.message} />)
            : (isStreamingBubble && !entry.run
              ? <span style={{ color: 'var(--txt-mut)' }}>MammothOS is composing…</span>
              : null)
        }
        {isStreamingBubble && busy && (
          <span style={{ display: 'inline-block', width: 8, height: 8, marginLeft: 6, borderRadius: '50%', background: 'var(--cyan)', boxShadow: '0 0 10px var(--cyan)', verticalAlign: 'middle' }} />
        )}
      </div>

      {!isUser && (
        <TrustBadgeRow
          provider={providerLabel}
          confidence={confidenceScore}
          contradictions={contradictionFlags}
          sourceCount={sourceCount}
          showEvidence={sourceCount > 0}
          style={{ marginTop: 6, marginBottom: 0, borderBottom: 'none', padding: '4px 0 0' }}
        />
      )}

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
          {onRate && isRateable(entry) && (
            <MessageRating
              key={messageFeedbackKey(entry)}
              rating={rating}
              onRate={(direction, extra) => onRate(entry, direction, extra)}
            />
          )}
        </div>
      )}
    </div>
  )
}

function persistSessionContext(agentId, history) {
  if (typeof window === 'undefined') return
  try {
    // Extract topics from the last few user messages
    const userMsgs = history.filter(e => e.role === 'user').slice(-5)
    const topics = [...new Set(
      userMsgs.flatMap(e => {
        const words = String(e.message || '').split(/\s+/).filter(w => w.length > 4)
        return words.slice(0, 3)
      })
    )].slice(0, 5)

    // Collect agent IDs used
    const agentsUsed = [...new Set(
      history.map(e => e.agent_id).filter(Boolean)
    )].slice(0, 4)

    // Last assistant message summary
    const lastAssistant = [...history].reverse().find(e => e.role === 'assistant' && e.message)
    const last_summary = lastAssistant ? String(lastAssistant.message).slice(0, 200) : ''

    const ctx = {
      updated_at: new Date().toISOString(),
      topics,
      agents: agentsUsed.length ? agentsUsed : [agentId],
      last_summary,
    }
    safeStorageSet('mammoth_session_context_v1', JSON.stringify(ctx))
  } catch { /* no-op */ }
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
  const [streamStatus, setStreamStatus] = useState('idle')
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
  // '' means no repository context. Options are resolved server-side per user.
  const [activeRepoValue, setActiveRepoValue] = useState('')
  const [activeThreadId, setActiveThreadId] = useState(null)
  const [threadSidebarOpen, setThreadSidebarOpen] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState([])
  const [successToast, setSuccessToast] = useState(null)
  const [agentMode, setAgentMode] = useState(() => safeStorageGet('mammoth_mind_agent_mode', '1') !== '0')
  const activeRunIdRef = useRef(null)
  const threadSidebarRef = useRef(null)
  const templatesRef = useRef(null)
  const bottomRef = useRef(null)
  const streamControllerRef = useRef(null)
  const toastTimerRef = useRef(null)
  const historySnapshotRef = useRef([])
  const { user } = useAuth()
  const scopeUserId = user?.id || 'local'
  const [ratings, setRatings] = useState({})

  useEffect(() => { setAttachedFiles([]) }, [scopeUserId])

  useEffect(() => {
    let cancelled = false
    setRatings({})
    api('/message-feedback')
      .then((data) => {
        if (cancelled) return
        const map = {}
        for (const item of Array.isArray(data?.ratings) ? data.ratings : []) {
          if (item?.message_key) map[item.message_key] = item
        }
        setRatings(map)
      })
      .catch(() => { /* ratings are optional; anonymous viewers get 401 */ })
    return () => { cancelled = true }
  }, [scopeUserId])

  const rateMessage = useCallback(async (entry, direction, extra = {}) => {
    const key = messageFeedbackKey(entry)
    if (!key) return
    let previous
    setRatings((current) => {
      previous = current[key]
      const next = { ...current }
      if (direction === 'none') delete next[key]
      else next[key] = { ...(current[key] || {}), message_key: key, direction, ...extra }
      return next
    })
    try {
      const runId = entry.run_id || entry.run?.id
      const data = await api('/message-feedback', {
        method: 'POST',
        body: {
          ...(runId ? { run_id: runId } : { created_at: entry.created_at }),
          direction,
          thread_id: activeThreadId || '',
          ...extra,
        },
      })
      if (data?.rating && direction !== 'none') {
        setRatings((current) => ({ ...current, [key]: data.rating }))
      }
    } catch (err) {
      setRatings((current) => {
        const next = { ...current }
        if (previous) next[key] = previous
        else delete next[key]
        return next
      })
      throw err
    }
  }, [activeThreadId])

  const publishSuccessToast = useCallback((payload) => {
    if (!payload) return
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current)
    }
    setSuccessToast(payload)
    toastTimerRef.current = setTimeout(() => {
      setSuccessToast(null)
      toastTimerRef.current = null
    }, 4800)
  }, [])

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
      stored = typeof window !== 'undefined' ? JSON.parse(safeStorageGet(`mammoth_chat_history:${scopeUserId}`, 'null') || 'null') : null
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

  useEffect(() => {
    if (typeof window === 'undefined') return
    if (history.length > 0) {
      safeStorageSet(`mammoth_chat_history:${scopeUserId}`, JSON.stringify(history.slice(-50)))
    } else {
      safeStorageRemove(`mammoth_chat_history:${scopeUserId}`)
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

  useEffect(() => () => {
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current)
    }
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
          const nextHistory = Array.isArray(payload.chat_history) ? payload.chat_history : []
          setHistory(nextHistory)
          const lastAssistant = [...nextHistory].reverse().find((entry) => entry.role === 'assistant')
          if (lastAssistant) {
            const derived = deriveSuccessDetailsFromMessage(lastAssistant.message, 'Agent run finished.')
            publishSuccessToast(
              buildSuccessToast({
                agentId: payload.agent_id || lastAssistant.agent_id || effectiveAgentId,
                keyResult: derived.keyResult,
                nextAction: derived.nextAction,
              }),
            )
          }
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

  const updateRunEntry = (localId, updater) => {
    setHistory((prev) => prev.map((item) => (item.local_id === localId ? updater(item) : item)))
  }

  const applyRunEvent = (localId, effectiveAgentId) => (event) => {
    if (event?.run_id) activeRunIdRef.current = event.run_id
    updateRunEntry(localId, (item) => {
      const run = reduceRunEvent(item.run, event)
      const summary = run.summary || {}
      return {
        ...item,
        run,
        run_id: run.id,
        message: run.reply || item.message,
        stream: !['completed', 'failed', 'cancelled', 'awaiting_approval'].includes(run.status),
        adapter: summary.provider || item.adapter,
        model: summary.model || item.model,
      }
    })
    if (event?.type === 'run.completed') {
      const derived = deriveSuccessDetailsFromMessage(event.data?.reply || '', 'Agent run finished.')
      publishSuccessToast(buildSuccessToast({ agentId: effectiveAgentId, keyResult: derived.keyResult, nextAction: derived.nextAction }))
      setMeta({ agentId: effectiveAgentId, adapter: event.data?.provider || 'unknown', model: event.data?.model || 'unknown', taskId: '', dispatched: false })
    }
  }

  const runWithStream = async (localId, effectiveAgentId, invoke) => {
    setBusy(true)
    setStreaming(true)
    setStreamStatus('working')
    streamControllerRef.current = new AbortController()
    try {
      await invoke(streamControllerRef.current.signal, applyRunEvent(localId, effectiveAgentId))
    } catch (e) {
      if (e?.name !== 'AbortError') setError(e instanceof Error ? e.message : 'Agent run failed')
      updateRunEntry(localId, (item) => ({ ...item, stream: false, run: item.run ? { ...item.run, status: item.run.status === 'running' ? 'cancelled' : item.run.status } : item.run }))
    } finally {
      setBusy(false)
      setStreaming(false)
      setStreamStatus('idle')
      streamControllerRef.current = null
    }
  }

  const decideRun = (entry, decision) => {
    const run = entry.run
    if (!run?.id || !run.approval?.id || busy) return
    runWithStream(entry.local_id, entry.agent_id, (signal, onEvent) => resolveRunApproval(run.id, run.approval.id, decision, { signal, onEvent }))
  }

  const stopActive = async () => {
    const runId = activeRunIdRef.current
    streamControllerRef.current?.abort?.()
    if (runId) await cancelAgentRun(runId)
  }

  const toggleAgentMode = () => {
    setAgentMode((prev) => {
      safeStorageSet('mammoth_mind_agent_mode', prev ? '0' : '1')
      return !prev
    })
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
              coding_intent: codingIntent,
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
          publishSuccessToast(
            buildSuccessToast({
              agentId: 'orchestrator',
              keyResult: summary,
              nextAction: result?.next_action || (result?.progress?.pending_approval ? 'Review pending approvals in Agent Console.' : 'Start execution or refine the plan.'),
            }),
          )
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
    const useAgentLoop = agentMode && !message.startsWith('/')
    if (useAgentLoop) {
      setError('')
      if (!override) setInput('')
      const localId = `run-local-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
      const now = new Date().toISOString()
      setHistory((prev) => [
        ...prev,
        { role: 'user', message, created_at: now, agent_id: effectiveAgentId, mode: 'agent', page: 'chat' },
        { role: 'assistant', message: '', created_at: now, agent_id: effectiveAgentId, mode: 'agent', adapter: 'agent-loop', model: '', stream: true, local_id: localId, run: { status: 'running', events: [], plan: [], approval: null, reply: '' } },
      ])
      setMeta(null)
      activeRunIdRef.current = null
      const body = {
        message,
        agent_id: effectiveAgentId,
        thread_id: activeThreadId || undefined,
        attached_file_ids: attachedFiles.map(file => file.file_id),
        repo_context: activeRepoValue ? { root: activeRepoValue } : undefined,
      }
      setAttachedFiles([])
      await runWithStream(localId, effectiveAgentId, (signal, onEvent) => startAgentRun(body, { signal, onEvent }))
      return
    }
    setBusy(true)
    setStreaming(true)
    setStreamStatus(effectiveAgentId === 'coding_agent' ? 'patching' : effectiveAgentId === 'reasoning_agent' ? 'reasoning' : 'thinking')
    setError('')
    if (!override) setInput('')
    setAttachedFiles([])

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
        thread_id: activeThreadId || undefined,
        attached_file_ids: attachedFiles.map(f => f.file_id),
        coding_intent: effectiveAgentId === 'coding_agent' ? codingIntent : undefined,
        page_context: buildLivePageContext(),
        repo_context: activeRepoValue ? {
          root: activeRepoValue,
          query: message,
          files: [],
          include_git_status: effectiveAgentId === 'coding_agent' || effectiveAgentId === 'reasoning_agent',
          max_results: effectiveAgentId === 'coding_agent' || effectiveAgentId === 'reasoning_agent' ? 4 : 2,
          max_snippets: effectiveAgentId === 'mammoth_guide' ? 4 : (effectiveAgentId === 'coding_agent' || effectiveAgentId === 'reasoning_agent' ? 3 : 2),
        } : undefined,
      }
      await streamChat(body, effectiveAgentId, placeholderIndex)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chat request failed')
    } finally {
      setBusy(false)
      setStreaming(false)
      setStreamStatus('idle')
      streamControllerRef.current = null
      await refreshOps()
    }
  }

  const createThread = async (title = '') => {
    try {
      const data = await authorizedFetch('/mammoth/chat/threads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: title || 'New conversation', agent_id: agentId }),
      })
      const json = await data.json()
      if (json?.thread_id) {
        setActiveThreadId(json.thread_id)
        setHistory([])
        setThoughtSteps([])
        setMeta(null)
        setError('')
        setExpandedThoughtIndex(-1)
        setAttachedFiles([])
        safeStorageRemove(`mammoth_chat_history:${scopeUserId}`)
        // Refresh sidebar
        threadSidebarRef.current?.reload?.()
      }
    } catch { /* no-op */ }
  }

  const selectThread = async (threadId) => {
    if (!threadId) return
    setActiveThreadId(threadId)
    setHistory([])
    setError('')
    setThoughtSteps([])
    setMeta(null)
    setAttachedFiles([])
    try {
      const data = await api(`/mammoth/chat/threads/${threadId}/history`)
      const msgs = Array.isArray(data?.chat_history) ? data.chat_history : []
      setHistory(msgs)
      const lastAssistant = [...msgs].reverse().find(e => e.role === 'assistant')
      if (lastAssistant?.thought_steps) setThoughtSteps(lastAssistant.thought_steps)
    } catch { /* no-op */ }
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
    safeStorageRemove(`mammoth_chat_history:${scopeUserId}`)
    setHistory([])
    setThoughtSteps([])
    setMeta(null)
    setError('')
    setExpandedThoughtIndex(-1)
    setAttachedFiles([])
    // Create a new thread for the fresh start
    await createThread()
  }

  const dispatchQuickAction = (action) => {
    setAgentId(action.agentId)
    if (action.codingIntent) setCodingIntent(action.codingIntent)
    send(action.message, action.agentId)
  }

  useEffect(() => {
    if (!quickActionsOpen) return undefined
    const onPointerDown = (event) => {
      if (templatesRef.current && !templatesRef.current.contains(event.target)) setQuickActionsOpen(false)
    }
    const onKeyDown = (event) => {
      if (event.key === 'Escape') setQuickActionsOpen(false)
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [quickActionsOpen])

  return (
    <div className="page-enter" style={{ padding: 24, height: '100%', boxSizing: 'border-box', display: 'flex', flexDirection: 'column' }}>
      {successToast && (
        <div style={{ position: 'fixed', top: 16, right: 16, zIndex: 70, maxWidth: 420, borderRadius: 12, border: '1px solid rgba(34,197,94,0.35)', background: 'rgba(6,25,15,0.95)', boxShadow: '0 10px 30px rgba(0,0,0,0.35)', padding: '10px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#86efac', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 4 }}>
            <Check size={14} />
            Run complete
          </div>
          <div style={{ fontSize: '0.84rem', color: 'var(--txt-pri)', fontWeight: 700, marginBottom: 4 }}>{successToast.title}</div>
          <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)', lineHeight: 1.5, marginBottom: 4 }}>Result: {successToast.keyResult}</div>
          <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)', lineHeight: 1.4 }}>Next: {successToast.nextAction}</div>
        </div>
      )}
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginBottom: 18, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            title="Toggle chat history sidebar"
            onClick={() => setThreadSidebarOpen(p => !p)}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 10px', borderRadius: 8, border: `1px solid ${threadSidebarOpen ? 'rgba(77,166,255,0.35)' : 'var(--border)'}`, background: threadSidebarOpen ? 'rgba(77,166,255,0.08)' : 'rgba(255,255,255,0.04)', color: threadSidebarOpen ? 'var(--photon)' : 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.8rem' }}
          >
            <PanelLeft size={14} />
          </button>
          <div>
            <h1 style={{ fontSize: '1.15rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: 10, margin: 0 }}>
              <Bot size={20} color="var(--photon)" /> MammothOS Chat
            </h1>
            <p style={{ margin: '4px 0 0', fontSize: '0.8rem', color: 'var(--txt-sec)', maxWidth: 700 }}>
              Native chat for MammothOS planning, debugging, and agent-assisted work.
            </p>
          </div>
        </div>
        <button
          onClick={() => setRightRailOpen((prev) => !prev)}
          style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.8rem' }}
        >
          {showRightRail ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
          {showRightRail ? 'Hide right rail' : 'Show right rail'}
        </button>
      </div>

      {/* Main layout: [thread sidebar] [chat] [right rail] */}
      <div style={{ display: 'flex', flex: 1, minHeight: 0, gap: 14 }}>
        {/* Thread history sidebar */}
        {threadSidebarOpen && (
          <div style={{ width: 220, flexShrink: 0, borderRadius: 14, overflow: 'hidden', border: '1px solid var(--border)' }}>
            <ChatThreadSidebar
              ref={threadSidebarRef}
              activeThreadId={activeThreadId}
              onSelectThread={selectThread}
              onNewThread={createThread}
              scopeUserId={scopeUserId}
            />
          </div>
        )}

      <div style={{ flex: 1, minWidth: 0, display: 'grid', gridTemplateColumns: showInlineRightRail ? 'minmax(0, 2.3fr) minmax(340px, 1fr)' : 'minmax(0, 1fr)', gap: 18 }}>
        <div className="glass-card-solid" style={{ display: 'flex', flexDirection: 'column', minHeight: isShortViewport ? '84vh' : '90vh', overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-mut)' }}>Current lane</div>
              <div style={{ fontSize: '0.92rem', color: selectedAgent.accent, fontWeight: 700 }}>{selectedAgent.label}</div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <div ref={templatesRef} style={{ position: 'relative' }}>
                <button
                  type="button"
                  onClick={() => setQuickActionsOpen((prev) => !prev)}
                  aria-expanded={quickActionsOpen}
                  aria-haspopup="dialog"
                  title="Prompt templates and slash commands"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 11px', borderRadius: 999, border: `1px solid ${quickActionsOpen ? 'rgba(77,166,255,0.35)' : 'var(--border)'}`, background: quickActionsOpen ? 'rgba(77,166,255,0.08)' : 'rgba(255,255,255,0.03)', color: quickActionsOpen ? 'var(--txt-pri)' : 'var(--txt-sec)', fontSize: '0.76rem', fontWeight: 600, cursor: 'pointer' }}
                >
                  <Sparkles size={13} /> Templates
                  <ChevronDown size={13} style={{ transition: 'transform 160ms ease', transform: quickActionsOpen ? 'rotate(180deg)' : 'none' }} />
                </button>
                {quickActionsOpen && (
                  <div
                    role="dialog"
                    aria-label="Prompt templates"
                    style={{ position: 'absolute', top: 'calc(100% + 8px)', right: 0, zIndex: 40, width: 'min(560px, 86vw)', maxHeight: '60vh', overflowY: 'auto', padding: 14, borderRadius: 14, border: '1px solid var(--border)', background: 'rgba(10,14,22,0.97)', boxShadow: '0 18px 40px rgba(0,0,0,0.45)', backdropFilter: 'blur(12px)', display: 'grid', gap: 10 }}
                  >
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {SLASH_ACTIONS.map((action) => (
                        <button
                          key={action}
                          onClick={() => { setInput(action); setQuickActionsOpen(false) }}
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
                          onClick={() => { setQuickActionsOpen(false); dispatchQuickAction(card) }}
                          disabled={busy}
                          style={{ textAlign: 'left', padding: '12px 14px', borderRadius: 12, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', cursor: busy ? 'not-allowed' : 'pointer' }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 6 }}>
                            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{card.title}</div>
                            <Workflow size={14} color="var(--txt-mut)" />
                          </div>
                          <div style={{ fontSize: '0.74rem', lineHeight: 1.5 }}>{card.message}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
              <button
                type="button"
                onClick={toggleAgentMode}
                aria-pressed={agentMode}
                title={agentMode ? 'Agent mode: plans, uses tools, and shows a live trace' : 'Classic mode: single-shot chat response'}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 8, border: `1px solid ${agentMode ? 'var(--mm-color-agent-default, #c8794a)' : 'var(--border)'}`, background: agentMode ? 'var(--mm-color-agent-soft, rgba(200,121,74,0.12))' : 'rgba(255,255,255,0.04)', color: agentMode ? 'var(--mm-color-agent-default, #c8794a)' : 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.76rem', fontWeight: 600 }}
              >
                <Workflow size={13} /> {agentMode ? 'Agent' : 'Classic'}
              </button>
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
                onRunDecision={decideRun}
                rating={ratings[messageFeedbackKey(entry)]}
                onRate={rateMessage}
              />
            ))}
            {busy && !history[history.length - 1]?.run && (
              <div style={{ alignSelf: 'flex-start', padding: '10px 12px', borderRadius: 12, background: 'rgba(77,166,255,0.08)', border: '1px solid rgba(77,166,255,0.18)', fontSize: '0.8rem', color: 'var(--txt-sec)', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--cyan)', boxShadow: '0 0 12px rgba(77,166,255,0.6)' }} />
                {streaming ? `MammothOS is ${streamStatus}…` : 'MammothOS is checking the herd…'}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div style={{ padding: 16 }}>
            {error && <div style={{ marginBottom: 10, color: '#f87171', fontSize: '0.78rem' }}>{error}</div>}
            <div aria-label="Message composer" style={{ display: 'grid', gap: 10, minWidth: 0 }}>
              <textarea
                aria-label="Message MammothOS"
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
                  style={{ width: '100%', minWidth: 0, resize: 'vertical', minHeight: 100, maxHeight: 240, overflowY: 'auto', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, color: 'var(--txt-pri)', fontSize: '0.94rem', padding: '14px 16px', lineHeight: 1.6 }}
              />
              <div style={{ minWidth: 0 }}>
                <FileAttachmentPanel
                  compact
                  attached={attachedFiles}
                  onAttach={(f) => setAttachedFiles(prev => [...prev.filter(x => x.file_id !== f.file_id), f])}
                  onRemove={(id) => setAttachedFiles(prev => prev.filter(f => f.file_id !== id))}
                  trailingAction={busy ? (
                  <button
                    onClick={stopActive}
                    aria-label="Stop the current run"
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '12px 14px', borderRadius: 12, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.06)', color: 'var(--txt-pri)', fontWeight: 700, cursor: 'pointer' }}
                  >
                    <Square size={13} /> Stop
                  </button>
                ) : (
                  <button
                    onClick={() => send()}
                    style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '12px 14px', borderRadius: 12, border: 'none', background: 'linear-gradient(90deg,var(--photon),var(--cyan))', color: '#050608', fontWeight: 700, cursor: 'pointer' }}
                  >
                    <Send size={15} /> Send
                  </button>
                )}
                />
              </div>
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

          <RepoSourcesPanel userId={scopeUserId} value={activeRepoValue} onChange={setActiveRepoValue} compact={isShortViewport} />
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
    </div>
  )
}
