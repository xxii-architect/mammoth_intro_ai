import { useMemo, useState } from 'react'
import { ChevronDown, ChevronRight, Copy, Check, Square, CircleDashed, CheckSquare2 } from 'lucide-react'
import TraceGlyph from './TraceGlyph'

const MONO = 'var(--mm-font-mono, "JetBrains Mono", monospace)'

function summarizeArgs(tool, args = {}) {
  if (args.path) return String(args.path)
  if (args.query) return `"${String(args.query).slice(0, 80)}"`
  if (args.url) return String(args.url).slice(0, 90)
  if (Array.isArray(args.files)) return args.files.map((f) => f.path).join(', ').slice(0, 120)
  const keys = Object.keys(args)
  return keys.length ? keys.join(', ') : ''
}

function summarizeResult(result = {}) {
  if (result.status === 'error' || result.status === 'rejected') return result.error || result.note || 'Failed'
  if (Array.isArray(result.matches)) return `${result.matches.length} match${result.matches.length === 1 ? '' : 'es'}`
  if (Array.isArray(result.files) && result.path) return `${result.files.length} file${result.files.length === 1 ? '' : 's'}`
  if (result.total_lines) return `lines ${result.start_line}-${result.end_line} of ${result.total_lines}`
  if (result.title) return String(result.title).slice(0, 80)
  return 'Done'
}

function buildSteps(events) {
  const steps = []
  const calls = new Map()
  for (const event of events) {
    const { type, data = {} } = event
    if (type === 'reasoning.summary') {
      steps.push({ key: `r-${event.seq}`, kind: 'reasoned', text: data.text })
    } else if (type === 'tool.call') {
      const step = { key: `t-${data.call_id}`, kind: data.trace_kind || 'tool', tool: data.tool, args: data.args, status: 'running' }
      calls.set(data.call_id, step)
      steps.push(step)
    } else if (type === 'tool.result') {
      const step = calls.get(data.call_id)
      if (step) {
        step.status = data.status === 'ok' ? 'ok' : 'error'
        step.result = data.result
      }
    } else if (type === 'diff.proposed') {
      steps.push({ key: `d-${event.seq}`, kind: 'proposed', diff: data })
    } else if (type === 'approval.resolved') {
      steps.push({ key: `a-${event.seq}`, kind: data.approved ? 'applied' : 'reverted', text: `${data.approved ? 'Approved' : 'Rejected'} ${data.tool}` })
    }
  }
  return steps
}

function DiffBlock({ diff }) {
  const [copied, setCopied] = useState(false)
  const text = diff.patch || diff.diff || ''
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1400)
    } catch { /* clipboard unavailable */ }
  }
  return (
    <div style={{ border: '1px solid var(--mm-color-border-subtle, var(--border))', borderRadius: 'var(--mm-radius-md, 10px)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, padding: '6px 10px', background: 'rgba(255,255,255,0.03)' }}>
        <span style={{ fontSize: '0.74rem', color: 'var(--txt-sec)' }}>
          {diff.title || 'Proposed change'} · {(diff.files || []).length} file{(diff.files || []).length === 1 ? '' : 's'}{diff.branch ? ` · ${diff.branch}` : ''}
        </span>
        <button type="button" onClick={copy} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.7rem', background: 'none', border: 'none', color: 'var(--txt-sec)', cursor: 'pointer' }}>
          {copied ? <Check size={12} /> : <Copy size={12} />} {diff.patch ? 'Copy patch' : 'Copy diff'}
        </button>
      </div>
      <pre style={{ margin: 0, padding: 10, maxHeight: 280, overflow: 'auto', fontFamily: MONO, fontSize: '0.72rem', lineHeight: 1.5 }}>
        {(diff.diff || '').split('\n').slice(0, 400).map((line, idx) => {
          const color = line.startsWith('+') && !line.startsWith('+++') ? 'var(--mm-color-status-success, #34d399)'
            : line.startsWith('-') && !line.startsWith('---') ? 'var(--mm-color-status-danger, #f87171)'
              : line.startsWith('@@') ? 'var(--mm-color-system-default, #4da6ff)' : 'var(--txt-sec)'
          return <div key={idx} style={{ color, whiteSpace: 'pre' }}>{line || ' '}</div>
        })}
      </pre>
      {diff.next_step && <div style={{ padding: '6px 10px', fontSize: '0.72rem', color: 'var(--txt-mut)' }}>{diff.next_step}</div>}
    </div>
  )
}

function ToolRow({ step }) {
  const [open, setOpen] = useState(false)
  const kind = step.status === 'error' ? 'failed' : step.kind
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', textAlign: 'left', background: 'none', border: 'none', padding: '3px 0', color: 'var(--txt-sec)', cursor: 'pointer', minWidth: 0 }}
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <TraceGlyph kind={kind} />
        <span style={{ fontFamily: MONO, fontSize: '0.74rem', color: 'var(--txt-pri)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {summarizeArgs(step.tool, step.args) || step.tool}
        </span>
        <span style={{ marginLeft: 'auto', fontSize: '0.7rem', color: 'var(--txt-mut)', whiteSpace: 'nowrap' }}>
          {step.status === 'running' ? 'running…' : summarizeResult(step.result)}
        </span>
      </button>
      {open && (
        <pre style={{ margin: '4px 0 6px 20px', padding: 8, borderRadius: 8, background: 'rgba(0,0,0,0.25)', maxHeight: 240, overflow: 'auto', fontFamily: MONO, fontSize: '0.7rem', color: 'var(--txt-sec)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {`${step.tool}(${JSON.stringify(step.args || {}, null, 2)})\n\n${JSON.stringify(step.result || {}, null, 2).slice(0, 6000)}`}
        </pre>
      )}
    </div>
  )
}

function PlanList({ plan }) {
  if (!plan?.length) return null
  return (
    <div style={{ display: 'grid', gap: 2, padding: '4px 0 6px' }}>
      {plan.map((item, idx) => {
        const Icon = item.status === 'done' ? CheckSquare2 : item.status === 'in_progress' ? CircleDashed : Square
        return (
          <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.76rem', color: item.status === 'done' ? 'var(--txt-mut)' : 'var(--txt-sec)' }}>
            <Icon size={12} aria-hidden="true" />
            <span style={{ textDecoration: item.status === 'done' ? 'line-through' : 'none' }}>{item.title}</span>
          </div>
        )
      })}
    </div>
  )
}

export default function RunTimeline({ run, onApprove, onReject, onContinue, busy }) {
  const steps = useMemo(() => buildSteps(run?.events || []), [run?.events])
  const finished = ['completed', 'failed', 'cancelled', 'partial'].includes(run?.status)
  const [expanded, setExpanded] = useState(null)
  const isOpen = expanded ?? !finished
  if (!run) return null
  const toolCalls = steps.filter((s) => s.tool).length
  const done = (run.plan || []).filter((p) => p.status === 'done').length
  const header = finished
    ? `${run.status === 'completed' ? 'Worked' : run.status === 'failed' ? 'Failed' : run.status === 'partial' ? 'Incomplete' : 'Stopped'} · ${toolCalls} tool call${toolCalls === 1 ? '' : 's'}${run.plan?.length ? ` · plan ${done}/${run.plan.length}` : ''}`
    : run.status === 'awaiting_approval' ? 'Waiting for your approval' : 'Working…'

  return (
    <div style={{ marginBottom: run.reply ? 10 : 0, display: 'grid', gap: 6 }} aria-live="polite">
      {(steps.length > 0 || run.plan?.length > 0 || !finished || run.status !== 'completed') && (
        <button
          type="button"
          onClick={() => setExpanded(!isOpen)}
          aria-expanded={isOpen}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, justifySelf: 'start', background: 'none', border: 'none', padding: 0, color: 'var(--txt-mut)', fontSize: '0.74rem', cursor: 'pointer' }}
        >
          {isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
          {header}
        </button>
      )}
      {run.recovery && !finished && <div role="status" style={{ color: 'var(--txt-sec)', fontSize: '0.76rem' }}>{run.recovery.text}</div>}
      {finished && run.can_continue && onContinue && (
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
          <button type="button" disabled={busy} onClick={onContinue}>Continue task</button>
          <span style={{ color: 'var(--txt-mut)', fontSize: '0.72rem' }}>Keeps saved progress. Uses additional model credits; up to two continuations.</span>
        </div>
      )}
      {isOpen && (
        <div style={{ borderLeft: '1px solid var(--mm-color-border-subtle, var(--border))', paddingLeft: 10, display: 'grid', gap: 2 }}>
          <PlanList plan={run.plan} />
          {run.diagnostics?.length > 0 && (
            <details style={{ color: 'var(--txt-mut)', fontSize: '0.72rem' }}>
              <summary>Model call diagnostics</summary>
              {run.diagnostics.map((call, idx) => (
                <div key={idx} style={{ padding: '4px 0', overflowWrap: 'anywhere' }}>
                  {call.provider || 'Provider unavailable'} / {call.model || 'Model unavailable'} · {call.phase || 'response'} · finish: {call.finish_reason || 'not reported'}
                  {Number.isFinite(call.usage?.total_tokens) ? ` · ${call.usage.total_tokens} tokens` : ' · token usage not reported'}
                </div>
              ))}
            </details>
          )}
          {steps.map((step) => {
            if (step.tool) return <ToolRow key={step.key} step={step} />
            if (step.diff) return <DiffBlock key={step.key} diff={step.diff} />
            return (
              <div key={step.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '3px 0' }}>
                <TraceGlyph kind={step.kind} compact />
                <span style={{ fontSize: '0.76rem', color: 'var(--txt-mut)', lineHeight: 1.5 }}>{step.text}</span>
              </div>
            )
          })}
        </div>
      )}
      {run.approval && (
        <div role="group" aria-label="Approval required" style={{ border: '1px solid var(--mm-color-status-warning, #f5b942)', borderRadius: 'var(--mm-radius-md, 10px)', padding: 10, display: 'grid', gap: 8, background: 'rgba(245,185,66,0.06)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <TraceGlyph kind="awaiting" />
            <span style={{ fontFamily: MONO, fontSize: '0.76rem', color: 'var(--txt-pri)' }}>{run.approval.tool}</span>
            <span style={{ fontSize: '0.7rem', color: 'var(--txt-mut)' }}>tier: {run.approval.tier}</span>
          </div>
          {run.approval.reason && <div style={{ fontSize: '0.76rem', color: 'var(--txt-sec)' }}>{run.approval.reason}</div>}
          <pre style={{ margin: 0, padding: 8, borderRadius: 8, background: 'rgba(0,0,0,0.25)', fontFamily: MONO, fontSize: '0.7rem', color: 'var(--txt-sec)', maxHeight: 160, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(run.approval.args || {}, null, 2)}
          </pre>
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" disabled={busy} onClick={onApprove} style={{ padding: '6px 12px', borderRadius: 8, border: 'none', background: 'var(--mm-color-status-success, #34d399)', color: '#04110b', fontWeight: 700, fontSize: '0.76rem', cursor: busy ? 'not-allowed' : 'pointer' }}>Approve</button>
            <button type="button" disabled={busy} onClick={onReject} style={{ padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'transparent', color: 'var(--txt-sec)', fontSize: '0.76rem', cursor: busy ? 'not-allowed' : 'pointer' }}>Reject</button>
          </div>
        </div>
      )}
      {run.status === 'failed' && run.error && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.76rem', color: 'var(--mm-color-status-danger, #f87171)' }}>
          <TraceGlyph kind="failed" compact /> {run.error}
        </div>
      )}
    </div>
  )
}
