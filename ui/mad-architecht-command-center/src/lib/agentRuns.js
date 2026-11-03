import { hydrateRun, readRunEventStream, reduceRunEvent } from '@mammothos/paths'
import { authorizedFetch } from '../api/client'

// Shared with the Mammoth Paths SDK so the app and embedders fold events identically.
export { readRunEventStream, reduceRunEvent }

export async function restoreRecursiveEntries(entries) {
  return Promise.all(entries.map(async entry => {
    if (!entry.run?.recursive || !['running', 'partial', 'awaiting_approval'].includes(entry.run.status)) return entry
    try {
      const saved = await fetchAgentRun(entry.run.id)
      if (!saved) throw new Error('Saved recursive run is unavailable. Open Run Review before deciding.')
      return { ...entry, local_id: entry.local_id || saved.id, run_id: saved.id,
        run: hydrateRun(saved), message: saved.reply || entry.message, stream: false }
    } catch (error) {
      return { ...entry, stream: false, run: { ...entry.run, status: 'failed', approval: null,
        can_continue: false, error: error instanceof Error ? error.message : 'Could not restore recursive run.' } }
    }
  }))
}

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
  await readRunEventStream(response, onEvent, { runId })
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
  await readRunEventStream(response, onEvent, { runId })
}

export async function fetchAgentRun(runId) {
  const response = await authorizedFetch(`/mammoth/runs/${encodeURIComponent(runId)}`)
  if (!response.ok) return null
  const payload = await response.json()
  return payload?.run || null
}
