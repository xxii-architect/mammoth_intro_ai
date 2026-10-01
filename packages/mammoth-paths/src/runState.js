/**
 * Mammoth Mind run state (contract `mammoth.run.v1`).
 * Framework-agnostic: a pure reducer plus a tiny store compatible with
 * React's `useSyncExternalStore`.
 */

export const RUN_CONTRACT_VERSION = 'mammoth.run.v1'

export const TERMINAL_RUN_EVENTS = Object.freeze([
  'run.completed',
  'run.failed',
  'run.cancelled',
  'run.awaiting_approval',
])

/**
 * Parse Server-Sent Events from a stream of text chunks.
 * Returns a push-style parser: call `push(chunk)` as data arrives and `end()` once done.
 */
export function createSseParser(onData) {
  let buffer = ''
  const flush = (block) => {
    const data = block
      .split(/\r?\n/)
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''))
      .join('\n')
    if (!data) return
    let parsed
    try {
      parsed = JSON.parse(data)
    } catch {
      return
    }
    if (parsed && typeof parsed === 'object') onData(parsed)
  }
  return {
    push(chunk) {
      buffer += chunk
      buffer = buffer.replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        flush(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        boundary = buffer.indexOf('\n\n')
      }
    },
    end() {
      if (buffer.trim()) flush(buffer)
      buffer = ''
    },
  }
}

/** Read a fetch `Response` body as run events. Throws on non-2xx responses. */
export async function readRunEventStream(response, onEvent) {
  if (!response.ok || !response.body) {
    let detail = ''
    try {
      const payload = await response.json()
      detail = payload?.error || payload?.message || ''
    } catch {
      /* body was not JSON */
    }
    const error = new Error(detail || `Run request failed (${response.status})`)
    error.status = response.status
    throw error
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = createSseParser(onEvent)
  for (;;) {
    const { value, done } = await reader.read()
    if (value) parser.push(decoder.decode(value, { stream: true }))
    if (done) break
  }
  parser.push(decoder.decode())
  parser.end()
}

/** Fold one run event into a compact view-model. Pure; never mutates `run`. */
export function reduceRunEvent(run, event) {
  const base = run || { id: event.run_id, status: 'running', events: [], plan: [], approval: null, reply: '' }
  const next = { ...base, id: base.id || event.run_id, events: [...base.events, event] }
  const { type, data = {} } = event
  if (type === 'run.started') { next.repo = data.repo || null; next.tools = data.tools || [] }
  if (type === 'plan.updated') next.plan = Array.isArray(data.plan) ? data.plan : next.plan
  if (type === 'approval.requested') { next.approval = data; next.status = 'awaiting_approval' }
  if (type === 'approval.resolved') { next.approval = null; next.status = 'running' }
  if (type === 'message.delta') next.reply = (next.reply || '') + String(data.text || '')
  if (type === 'run.completed') { next.status = 'completed'; next.reply = String(data.reply || next.reply || ''); next.summary = data }
  if (type === 'run.failed') { next.status = 'failed'; next.error = data.error }
  if (type === 'run.cancelled') next.status = 'cancelled'
  return next
}

/**
 * Minimal observable run store.
 * React: `const run = useSyncExternalStore(store.subscribe, store.getSnapshot)`.
 */
export function createRunStore(initial = null) {
  let state = initial
  const listeners = new Set()
  return {
    getSnapshot: () => state,
    subscribe(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    dispatch(event) {
      state = reduceRunEvent(state, event)
      listeners.forEach((listener) => listener())
      return state
    },
    reset(value = null) {
      state = value
      listeners.forEach((listener) => listener())
    },
  }
}
