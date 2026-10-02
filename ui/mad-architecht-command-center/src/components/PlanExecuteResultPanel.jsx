import { useState } from 'react'
import { CheckCircle, XCircle, Clock, AlertTriangle, ChevronDown, ChevronRight, Cpu, Code2, BookOpen, Search, Zap, FileText, Eye, EyeOff } from 'lucide-react'
import MammothEmpty from './MammothEmpty'

const AGENT_LABELS = {
  curriculum_agent:      { label: 'Curriculum',    icon: BookOpen,  color: '#a78bfa' },
  tutor_agent:           { label: 'Tutor',          icon: BookOpen,  color: '#818cf8' },
  coding_agent:          { label: 'Coding',         icon: Code2,     color: '#22d3ee' },
  research_agent:        { label: 'Research',       icon: Search,    color: '#34d399' },
  plant_the_seed_agent:  { label: 'Plant Seed',     icon: Zap,       color: '#4ade80' },
  orchestrator_agent:    { label: 'Orchestrator',   icon: Cpu,       color: '#fb923c' },
  planner_agent:         { label: 'Planner',        icon: FileText,  color: '#f472b6' },
  brand_voice_agent:     { label: 'Brand Voice',    icon: FileText,  color: '#f472b6' },
  field_ops_agent:       { label: 'Field Ops',      icon: Zap,       color: '#facc15' },
  reflection_agent:      { label: 'Reflection',     icon: BookOpen,  color: '#c4b5fd' },
  market_intel_agent:    { label: 'Market Intel',   icon: Search,    color: '#2dd4bf' },
  browser_agent:         { label: 'Browser',        icon: Search,    color: '#60a5fa' },
  community_engine_agent:{ label: 'Community',      icon: Cpu,       color: '#4ade80' },
}

const STATUS_CONFIG = {
  completed:        { color: '#22c55e', bg: 'rgba(34,197,94,0.10)',   icon: CheckCircle,    label: 'Completed' },
  ok:               { color: '#22c55e', bg: 'rgba(34,197,94,0.10)',   icon: CheckCircle,    label: 'Success' },
  pending_approval: { color: '#f59e0b', bg: 'rgba(245,158,11,0.10)',  icon: AlertTriangle,  label: 'Needs Approval' },
  running:          { color: '#4da6ff', bg: 'rgba(77,166,255,0.10)',  icon: Clock,          label: 'Running' },
  failed:           { color: '#f87171', bg: 'rgba(248,113,113,0.10)', icon: XCircle,        label: 'Failed' },
  error:            { color: '#f87171', bg: 'rgba(248,113,113,0.10)', icon: XCircle,        label: 'Error' },
  skipped:          { color: '#6b7280', bg: 'rgba(107,114,128,0.10)', icon: ChevronRight,   label: 'Skipped' },
}

function statusCfg(status) {
  return STATUS_CONFIG[status] || { color: '#6b7280', bg: 'rgba(107,114,128,0.08)', icon: Clock, label: status || 'Unknown' }
}

function agentCfg(agentId) {
  return AGENT_LABELS[agentId] || { label: agentId?.replace(/_agent$/, '').replace(/_/g, ' '), icon: Cpu, color: '#94a3b8' }
}

// Plan steps carry the agent's artifact at response.result.output (older
// payloads used result/output directly).
export function stepArtifact(step) {
  if (!step || typeof step !== 'object') return null
  const inner = step.response?.result
  const candidates = [inner?.output, inner, step.result?.output, step.result, step.output]
  for (const c of candidates) {
    if (typeof c === 'string' && c.trim()) return c
    if (c && typeof c === 'object' && Object.keys(c).length) return c
  }
  return null
}

const SUMMARY_KEYS = [
  'summary', 'executive_summary', 'market_summary', 'situation_summary', 'reflection_summary',
  'idea_summary', 'output', 'insight', 'message', 'explanation', 'content', 'text', 'response',
]
const HIDDEN_KEYS = new Set([
  ...SUMMARY_KEYS, 'status', 'agent', 'mode', 'artifact_type', 'prompt', 'input', 'topic', 'generated_at', 'timestamp',
  'quality_flags', 'citations', 'references', 'sources', 'ranked_sources', 'source_coverage', 'sources_filtered',
  'sources_retrieved', 'retrieval_errors', 'web_retrieval_errors', 'web_sources_used', 'reasoning_trace',
  'workflow_hints', 'execution_loop', 'runtime_agent', 'confidence', 'signal_confidence', 'intent', 'focus',
  'tone', 'audience', 'lesson_title', 'title', 'progress_score', 'follow_up_tags', 'signals', 'environment', 'equipment',
])

function humanizeKey(key) {
  const text = String(key).replace(/_/g, ' ').trim()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function itemText(item) {
  if (item == null) return ''
  if (typeof item !== 'object') return String(item)
  const values = Object.values(item).filter(v => v != null && typeof v !== 'object' && String(v).trim())
  if (!values.length) return ''
  const [head, ...rest] = values.map(String)
  return rest.length ? `${head} — ${rest.join(' · ')}` : head
}

function artifactSections(artifact) {
  if (typeof artifact === 'string') return { summary: artifact, sections: [] }
  const summaryKey = SUMMARY_KEYS.find(k => typeof artifact[k] === 'string' && artifact[k].trim())
  const sections = []
  for (const [key, value] of Object.entries(artifact)) {
    if (HIDDEN_KEYS.has(key) || value == null) continue
    if (Array.isArray(value)) {
      const items = value.map(itemText).filter(Boolean).slice(0, 12)
      if (items.length) sections.push({ key, title: humanizeKey(key), items })
    } else if (typeof value === 'object') {
      const items = Object.entries(value)
        .filter(([, v]) => v != null && typeof v !== 'object' && String(v).trim())
        .map(([k, v]) => `${humanizeKey(k)}: ${v}`)
        .slice(0, 12)
      if (items.length) sections.push({ key, title: humanizeKey(key), items })
    } else if (typeof value === 'string' && value.trim().length > 2) {
      sections.push({ key, title: humanizeKey(key), text: value.trim() })
    }
  }
  return { summary: summaryKey ? artifact[summaryKey].trim() : '', sections }
}

function StepOutput({ artifact }) {
  const { summary, sections } = artifactSections(artifact)
  if (!summary && !sections.length) return <MammothEmpty context="step_output" compact />
  return (
    <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
      {summary && (
        <p style={{ fontSize: '0.82rem', color: 'var(--txt-pri)', lineHeight: 1.65, margin: 0, whiteSpace: 'pre-wrap' }}>{summary}</p>
      )}
      {sections.map(section => (
        <div key={section.key}>
          <div style={{ fontSize: '0.64rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--txt-mut)', marginBottom: 4 }}>
            {section.title}
          </div>
          {section.text ? (
            <p style={{ fontSize: '0.79rem', color: 'var(--txt-sec)', lineHeight: 1.6, margin: 0, whiteSpace: 'pre-wrap' }}>{section.text}</p>
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--txt-sec)', fontSize: '0.79rem', lineHeight: 1.6 }}>
              {section.items.map((item, i) => <li key={i}>{item}</li>)}
            </ul>
          )}
        </div>
      ))}
    </div>
  )
}

function StepCard({ step, idx }) {
  const [open, setOpen] = useState(false)
  const sc = statusCfg(step.status)
  const ac = agentCfg(step.agent_id)
  const StatusIcon = sc.icon
  const AgentIcon = ac.icon
  const artifact = stepArtifact(step)
  const errorText = step.error || step.failure_reason || (step.status === 'failed' ? step.response?.result?.error || step.response?.error : '')
  const hasDrilldown = Boolean(artifact || errorText)
  const toggle = () => hasDrilldown && setOpen(o => !o)

  return (
    <div style={{
      border: `1px solid ${sc.color}28`,
      borderLeft: `3px solid ${sc.color}`,
      borderRadius: 8,
      background: sc.bg,
      marginBottom: 8,
      overflow: 'hidden',
    }}>
      <div
        onClick={toggle}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle() } }}
        role={hasDrilldown ? 'button' : undefined}
        tabIndex={hasDrilldown ? 0 : undefined}
        aria-expanded={hasDrilldown ? open : undefined}
        style={{
          padding: '10px 12px',
          cursor: hasDrilldown ? 'pointer' : 'default',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 10,
        }}
      >
        <div style={{ paddingTop: 2 }}>
          <StatusIcon size={14} color={sc.color} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.84rem', color: 'var(--txt-pri)', fontWeight: 600 }}>
              {idx + 1}. {step.title || step.agent_id}
            </span>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              fontSize: '0.68rem', color: ac.color,
              background: `${ac.color}18`, borderRadius: 12, padding: '2px 8px',
            }}>
              <AgentIcon size={10} />
              {ac.label}
            </span>
            <span style={{
              fontSize: '0.66rem', textTransform: 'uppercase',
              color: sc.color, fontFamily: 'JetBrains Mono,monospace',
              letterSpacing: '0.08em',
            }}>
              {sc.label}
            </span>
          </div>
          {step.intent && (
            <div style={{ color: 'var(--txt-mut)', fontSize: '0.68rem', marginTop: 3 }}>
              Intent: {step.intent.replace(/_/g, ' ')}
              {step.duration_ms > 0 && ` · ${(step.duration_ms / 1000).toFixed(1)}s`}
            </div>
          )}
        </div>
        {hasDrilldown && (
          <div style={{ flexShrink: 0, color: 'var(--txt-mut)', marginTop: 2 }}>
            {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
          </div>
        )}
      </div>

      {open && hasDrilldown && (
        <div style={{ padding: '0 12px 12px 12px', borderTop: `1px solid ${sc.color}20` }}>
          {artifact && <StepOutput artifact={artifact} />}
          {artifact?.quality_flags?.length > 0 && (
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginTop: 8 }}>
              {artifact.quality_flags.map(f => (
                <span key={f} style={{ fontSize: '0.63rem', background: 'rgba(77,166,255,0.12)', color: 'var(--photon)', borderRadius: 10, padding: '2px 7px' }}>
                  {f.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          )}
          {errorText && (
            <div style={{ fontSize: '0.76rem', color: '#f87171', marginTop: 8, fontFamily: 'JetBrains Mono,monospace' }}>
              ⚠ {String(errorText)}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const PLAN_PROFILE_LABELS = {
  atlas: 'ATLAS-First',
  coding: 'ATLAS + Coding',
  coding_only: 'Coding Agent',
  balanced: 'Balanced',
  autonomous: 'Autonomous Prep',
}

export default function PlanExecuteResultPanel({ planRun, rawJson }) {
  const [showRaw, setShowRaw] = useState(false)

  if (!planRun) return null

  const sc = statusCfg(planRun.plan_status || planRun.status)
  const StatusIcon = sc.icon
  const steps = planRun.plan_steps || []
  const progress = planRun.progress || {}
  const total = progress.total || steps.length || 0
  const completed = progress.completed || 0
  const pct = total > 0 ? Math.round((completed / total) * 100) : (planRun.plan_status === 'completed' ? 100 : 0)
  const overallSummary = planRun.summary || planRun.objective

  return (
    <div>
      {/* Header + raw toggle */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <StatusIcon size={16} color={sc.color} />
          <span style={{ fontSize: '0.88rem', fontWeight: 700, color: 'var(--txt-pri)' }}>
            Plan + Execute
          </span>
          <span style={{
            fontSize: '0.66rem', textTransform: 'uppercase',
            background: sc.bg, color: sc.color, borderRadius: 12,
            padding: '2px 10px', fontFamily: 'JetBrains Mono,monospace',
            letterSpacing: '0.08em',
          }}>
            {sc.label}
          </span>
        </div>
        <button
          onClick={() => setShowRaw(r => !r)}
          style={{
            display: 'flex', alignItems: 'center', gap: 5,
            fontSize: '0.7rem', color: 'var(--txt-mut)',
            background: 'none', border: '1px solid var(--border)',
            borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
          }}
        >
          {showRaw ? <Eye size={11} /> : <EyeOff size={11} />}
          {showRaw ? 'Human view' : 'Raw JSON'}
        </button>
      </div>

      {showRaw ? (
        <pre style={{ fontSize: '0.76rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', whiteSpace: 'pre-wrap', lineHeight: 1.6, maxHeight: 400, overflowY: 'auto' }}>
          {rawJson || JSON.stringify(planRun, null, 2)}
        </pre>
      ) : (
        <>
          {/* Objective */}
          {planRun.objective && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 4 }}>Objective</div>
              <p style={{ fontSize: '0.85rem', color: 'var(--txt-pri)', lineHeight: 1.55, margin: 0 }}>
                {planRun.objective}
              </p>
            </div>
          )}

          {/* Meta row */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
            {planRun.plan_profile && (
              <span style={{ fontSize: '0.68rem', background: 'rgba(167,139,250,0.12)', color: '#a78bfa', borderRadius: 10, padding: '2px 10px' }}>
                {PLAN_PROFILE_LABELS[planRun.plan_profile] || planRun.plan_profile}
              </span>
            )}
            {planRun.coding_intent && (
              <span style={{ fontSize: '0.68rem', background: 'rgba(34,211,238,0.10)', color: '#22d3ee', borderRadius: 10, padding: '2px 10px' }}>
                {planRun.coding_intent.replace(/_/g, ' ')}
              </span>
            )}
            {total > 0 && (
              <span style={{ fontSize: '0.68rem', background: 'rgba(255,255,255,0.06)', color: 'var(--txt-sec)', borderRadius: 10, padding: '2px 10px' }}>
                {completed}/{total} steps done
              </span>
            )}
            {progress.failed > 0 && (
              <span style={{ fontSize: '0.68rem', background: 'rgba(248,113,113,0.10)', color: '#f87171', borderRadius: 10, padding: '2px 10px' }}>
                {progress.failed} failed
              </span>
            )}
            {progress.pending_approval > 0 && (
              <span style={{ fontSize: '0.68rem', background: 'rgba(245,158,11,0.10)', color: '#f59e0b', borderRadius: 10, padding: '2px 10px' }}>
                {progress.pending_approval} awaiting approval
              </span>
            )}
          </div>

          {/* Progress bar */}
          {total > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                <div style={{
                  height: '100%',
                  width: `${pct}%`,
                  background: planRun.plan_status === 'completed' ? '#22c55e'
                    : planRun.plan_status === 'failed' ? '#f87171'
                    : planRun.plan_status === 'pending_approval' ? '#f59e0b'
                    : 'var(--photon)',
                  borderRadius: 999,
                  transition: 'width 0.3s ease',
                }} />
              </div>
              <div style={{ fontSize: '0.64rem', color: 'var(--txt-mut)', marginTop: 4, fontFamily: 'JetBrains Mono,monospace' }}>
                {pct}% complete
              </div>
            </div>
          )}

          {/* Overall summary */}
          {overallSummary && planRun.plan_status !== 'running' && (
            <div style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px', marginBottom: 14 }}>
              <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 5 }}>Summary</div>
              <p style={{ fontSize: '0.82rem', color: 'var(--txt-sec)', lineHeight: 1.65, margin: 0 }}>{overallSummary}</p>
            </div>
          )}

          {/* Error */}
          {planRun.error && (
            <div style={{ background: 'rgba(248,113,113,0.08)', border: '1px solid rgba(248,113,113,0.2)', borderRadius: 8, padding: '10px 14px', marginBottom: 14 }}>
              <div style={{ fontSize: '0.75rem', color: '#f87171', fontFamily: 'JetBrains Mono,monospace' }}>⚠ {planRun.error}</div>
            </div>
          )}

          {/* Steps */}
          {steps.length > 0 && (
            <div>
              <div style={{ fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', marginBottom: 10 }}>
                Steps — click to expand
              </div>
              {steps.map((step, idx) => (
                <StepCard key={step.id || `step-${idx}`} step={step} idx={idx} />
              ))}
            </div>
          )}

          {steps.length === 0 && planRun.plan_status === 'running' && (
            <div style={{ color: 'var(--txt-sec)', fontSize: '0.8rem', padding: '16px 0' }}>
              Agents are working… steps will appear here as they complete.
            </div>
          )}
          {steps.length === 0 && planRun.plan_status !== 'running' && (
            <MammothEmpty context="plan_steps" />
          )}
        </>
      )}
    </div>
  )
}
