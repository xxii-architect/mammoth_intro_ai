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
  'run.partial',
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
    let payload = {}
    try {
      const decoded = await response.json()
      if (decoded && typeof decoded === 'object' && !Array.isArray(decoded)) payload = decoded
      detail = payload.error || payload.detail || payload.message || ''
    } catch {
      /* body was not JSON */
    }
    const error = new Error(detail || `Run request failed (${response.status})`)
    error.status = response.status
    error.code = String(payload.code || '')
    error.payload = payload
    throw error
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let terminal = false
  const parser = createSseParser((event) => {
    if (terminal) return
    terminal = TERMINAL_RUN_EVENTS.includes(event.type)
    onEvent(event)
  })
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (value) parser.push(decoder.decode(value, { stream: true }))
      if (terminal) break
      if (done) break
    }
    parser.push(decoder.decode())
    parser.end()
    if (!terminal) throw new Error('The run stream ended before a terminal event. Saved work may still be available; check the run before starting again.')
  } finally {
    try {
      if (terminal) await reader.cancel()
    } finally {
      reader.releaseLock()
    }
  }
}

/** Fold one run event into a compact view-model. Pure; never mutates `run`. */
export function reduceRunEvent(run, event) {
  if (run?.id && event.run_id !== run.id) throw new TypeError('Cannot combine events from different runs')
  if (run && Number.isInteger(event.seq) && event.seq > 0
    && run.events.some(saved => saved.seq === event.seq)) return run
  if (run && Number.isInteger(event.seq) && event.seq > 0
    && run.events.some(saved => saved.seq > event.seq)) throw new TypeError('Run events arrived out of order; recover the saved snapshot')
  const base = run || { id: event.run_id, status: 'running', events: [], plan: [], approval: null, reply: '' }
  const next = { ...base, id: base.id || event.run_id, events: [...base.events, event] }
  const { type, data = {} } = event
  if (data.progress) next.progress = data.progress
  if (data.recursive) next.recursive = data.recursive
  if (type === 'recursive.updated') next.recursive = data
  if (type === 'run.started') { next.repo = data.repo || null; next.tools = data.tools || [] }
  if (type === 'run.continued') { next.status = 'running'; next.reply = ''; next.error = ''; next.can_continue = false; next.failure_code = '' }
  if (type === 'run.recovering') next.recovery = data
  if (type === 'model.completed') { next.diagnostics = [...(next.diagnostics || []), data]; next.recovery = null }
  if (type === 'plan.updated') next.plan = Array.isArray(data.plan) ? data.plan : next.plan
  if (type === 'approval.requested') { next.approval = data; next.status = 'awaiting_approval' }
  if (type === 'approval.resolved') { next.approval = null; next.status = 'running' }
  if (type === 'message.delta') next.reply = (next.reply || '') + String(data.text || '')
  if (type === 'message.completed') next.reply = String(data.text || next.reply || '')
  if (type === 'run.completed') { next.status = 'completed'; next.reply = String(data.reply || next.reply || ''); next.summary = data }
  if (type === 'run.failed' || type === 'run.partial') {
    next.status = type === 'run.partial' ? 'partial' : 'failed'
    next.error = data.error || ''
    next.reply = String(data.reply || next.reply || '')
    next.can_continue = Boolean(data.can_continue)
    next.failure_code = data.code || ''
    next.summary = data
  }
  if (['run.completed', 'run.failed', 'run.partial', 'run.cancelled'].includes(type)) {
    next.approval = null
    if (type === 'run.completed' || type === 'run.cancelled') next.can_continue = false
  }
  if (type === 'run.cancelled') next.status = 'cancelled'
  return next
}

/** Rebuild a full GET snapshot without starting, continuing or approving a run. */
export function hydrateRun(snapshot) {
  if (!snapshot || typeof snapshot.id !== 'string' || !snapshot.id
    || !['running', 'awaiting_approval', 'completed', 'failed', 'cancelled', 'partial'].includes(snapshot.status)
    || !Array.isArray(snapshot.events)
    || (snapshot.plan != null && !Array.isArray(snapshot.plan))
    || (snapshot.diagnostics != null && !Array.isArray(snapshot.diagnostics))
    || (snapshot.reply != null && typeof snapshot.reply !== 'string')
    || (snapshot.progress != null && (typeof snapshot.progress !== 'object' || Array.isArray(snapshot.progress)))
    || (snapshot.pending_approval != null && (typeof snapshot.pending_approval !== 'object' || Array.isArray(snapshot.pending_approval)))) {
    throw new TypeError('Invalid saved run snapshot')
  }
  let state = null
  let previous = 0
  for (const event of snapshot.events) {
    if (!event || event.run_id !== snapshot.id || !Number.isInteger(event.seq) || event.seq !== previous + 1
      || typeof event.type !== 'string' || !event.data || typeof event.data !== 'object' || Array.isArray(event.data)) {
      throw new TypeError('Saved run events must belong to this run and form a complete sequence starting at one')
    }
    previous = event.seq
    state = reduceRunEvent(state, event)
  }
  // Cancellation/restart reconciliation can update saved state without another event.
  return {
    ...(state || { id: snapshot.id, events: [], plan: [], reply: '', approval: null }),
    status: snapshot.status,
    reply: snapshot.reply || '',
    plan: snapshot.plan || [],
    approval: snapshot.status === 'awaiting_approval' ? snapshot.pending_approval || null : null,
    progress: snapshot.progress || null,
    diagnostics: snapshot.diagnostics || [],
    recursive: snapshot.recursive || null,
    failure_code: snapshot.failure_code || '',
    can_continue: ['partial', 'failed'].includes(snapshot.status) && snapshot.can_continue === true,
    error: ['partial', 'failed'].includes(snapshot.status) ? snapshot.reply || '' : '',
    recovery: null,
  }
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
