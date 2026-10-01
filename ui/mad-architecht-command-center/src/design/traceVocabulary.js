import {
  Eye, FilePen, TerminalSquare, Search, GitPullRequestDraft, CheckCircle2, Undo2, XCircle,
  Hand, ListChecks, Users, Brain, Globe, Plug,
} from 'lucide-react'

/**
 * The MammothOS trace vocabulary. One glyph = one meaning, everywhere
 * (chat, run timeline, logs, diff viewer, SDK embeds).
 *
 * Every entry carries a text label so meaning never depends on colour alone.
 * Tones map to semantic tokens: agent (copper), system (blue), success, warning, danger, info.
 */
export const TRACE_KINDS = {
  read:      { label: 'Read',              Icon: Eye,                 tone: 'info' },
  searched:  { label: 'Searched',          Icon: Search,              tone: 'info' },
  fetched:   { label: 'Fetched',           Icon: Globe,               tone: 'info' },
  planned:   { label: 'Planned',           Icon: ListChecks,          tone: 'system' },
  reasoned:  { label: 'Reasoning',         Icon: Brain,               tone: 'system' },
  ran:       { label: 'Ran',               Icon: TerminalSquare,      tone: 'agent' },
  tool:      { label: 'Tool',              Icon: Plug,                tone: 'agent' },
  delegated: { label: 'Delegated',         Icon: Users,               tone: 'agent' },
  wrote:     { label: 'Wrote',             Icon: FilePen,             tone: 'agent' },
  proposed:  { label: 'Proposed',          Icon: GitPullRequestDraft, tone: 'agent' },
  awaiting:  { label: 'Awaiting approval', Icon: Hand,                tone: 'warning' },
  applied:   { label: 'Applied',           Icon: CheckCircle2,        tone: 'success' },
  reverted:  { label: 'Reverted',          Icon: Undo2,               tone: 'warning' },
  failed:    { label: 'Failed',            Icon: XCircle,             tone: 'danger' },
}

export const TONE_VARS = {
  info:    { fg: 'var(--mm-color-text-secondary)', bg: 'rgba(255,255,255,0.04)' },
  system:  { fg: 'var(--mm-color-system-default)', bg: 'var(--mm-color-system-soft)' },
  agent:   { fg: 'var(--mm-color-agent-default)', bg: 'var(--mm-color-agent-soft)' },
  success: { fg: 'var(--mm-color-status-success)', bg: 'rgba(52,211,153,0.10)' },
  warning: { fg: 'var(--mm-color-status-warning)', bg: 'rgba(245,185,66,0.10)' },
  danger:  { fg: 'var(--mm-color-status-danger)', bg: 'rgba(248,113,113,0.10)' },
}

/** Map a tool name / run-event to a trace kind. Unknown tools fall back to "tool". */
export function traceKindForTool(toolName = '', status = '') {
  const name = String(toolName || '').toLowerCase()
  const st = String(status || '').toLowerCase()
  if (st === 'failed' || st === 'error') return 'failed'
  if (st === 'awaiting_approval' || st === 'pending_approval') return 'awaiting'
  if (/(^|_)(read|view|open|cat)(_|$)/.test(name) || name.startsWith('repo.read')) return 'read'
  if (/(search|grep|find|query)/.test(name)) return 'searched'
  if (/(fetch|http|web|browse)/.test(name)) return 'fetched'
  if (/(write|edit|create|patch)/.test(name)) return 'proposed'
  if (/(shell|exec|run|terminal)/.test(name)) return 'ran'
  if (/(plan|todo)/.test(name)) return 'planned'
  if (/(agent|delegate|lane)/.test(name)) return 'delegated'
  return 'tool'
}
