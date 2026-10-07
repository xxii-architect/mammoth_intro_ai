import { readRunEventStream, reduceRunEvent } from '@mammothos/paths'
import { authorizedFetch } from '../api/client'

// Shared with the Mammoth Paths SDK so the app and embedders fold events identically.
export { readRunEventStream, reduceRunEvent }

/**
 * Client for the Mammoth Mind run API (contract `mammoth.run.v1`).
 * Every callback receives one typed run event: { run_id, seq, type, ts, data }.
 */

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

export async function continueAgentRun(runId, { signal, onEvent }) {
  const response = await authorizedFetch(`/mammoth/runs/${encodeURIComponent(runId)}/continue`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
    signal,
  })
  await readRunEventStream(response, onEvent)
}

export async function fetchAgentRun(runId) {
  const response = await authorizedFetch(`/mammoth/runs/${encodeURIComponent(runId)}`)
  if (!response.ok) return null
  const payload = await response.json()
  return payload?.run || null
}
