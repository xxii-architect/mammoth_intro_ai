import { authorizedFetch } from '../api/client'

/**
 * Client for the Mammoth Mind run API (contract `mammoth.run.v1`).
 * Every callback receives one typed run event: { run_id, seq, type, ts, data }.
 */

export async function readRunEventStream(response, onEvent) {
  if (!response.ok || !response.body) {
    let detail = ''
    try { detail = (await response.json())?.message || '' } catch { /* not JSON */ }
    throw new Error(detail || `Run request failed (${response.status})`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const flush = (block) => {
    const data = block.split(/\r?\n/).filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim()).join('')
    if (!data) return
    try {
      onEvent(JSON.parse(data))
    } catch { /* ignore malformed frames */ }
  }
  for (;;) {
    const { value, done } = await reader.read()
    if (value) {
      buffer += decoder.decode(value, { stream: true })
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        flush(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        boundary = buffer.indexOf('\n\n')
      }
    }
    if (done) break
  }
  if (buffer.trim()) flush(buffer)
}

export async function startAgentRun(body, { signal, onEvent }) {
  const response = await authorizedFetch('/mammoth/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  })
  await readRunEventStream(response, onEvent)
}

export async function resolveRunApproval(runId, approvalId, decision, { signal, onEvent, note = '' }) {
  const response = await authorizedFetch(`/mammoth/runs/${encodeURIComponent(runId)}/approval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approval_id: approvalId, decision, note }),
    signal,
  })
  await readRunEventStream(response, onEvent)
}

export async function cancelAgentRun(runId) {
  if (!runId) return
  try {
    await authorizedFetch(`/mammoth/runs/${encodeURIComponent(runId)}/cancel`, { method: 'POST' })
  } catch { /* best effort */ }
}

export async function fetchAgentRun(runId) {
  const response = await authorizedFetch(`/mammoth/runs/${encodeURIComponent(runId)}`)
  if (!response.ok) return null
  const payload = await response.json()
  return payload?.run || null
}

/** Fold a run event into the compact view-model the timeline renders. */
export function reduceRunEvent(run, event) {
  const base = run || { id: event.run_id, status: 'running', events: [], plan: [], approval: null, reply: '' }
  const next = { ...base, id: base.id || event.run_id, events: [...base.events, event] }
  const { type, data = {} } = event
  if (type === 'plan.updated') next.plan = Array.isArray(data.plan) ? data.plan : next.plan
  if (type === 'approval.requested') { next.approval = data; next.status = 'awaiting_approval' }
  if (type === 'approval.resolved') { next.approval = null; next.status = 'running' }
  if (type === 'message.delta') next.reply = (next.reply || '') + String(data.text || '')
  if (type === 'run.completed') { next.status = 'completed'; next.reply = String(data.reply || next.reply || ''); next.summary = data }
  if (type === 'run.failed') { next.status = 'failed'; next.error = data.error }
  if (type === 'run.cancelled') next.status = 'cancelled'
  if (type === 'run.started') { next.repo = data.repo || null; next.tools = data.tools || [] }
  return next
}
