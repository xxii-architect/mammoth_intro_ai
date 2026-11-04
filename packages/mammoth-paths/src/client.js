/**
 * Mammoth Paths HTTP client. Zero dependencies; uses the platform `fetch`.
 * Every call is scoped server-side to the caller's token.
 */

import { hydrateRun, readRunEventStream, reduceRunEvent } from './runState.js'

export const PATHS_CONTRACT_VERSION = 'mammoth.paths.v1'

export class PathsError extends Error {
  constructor(message, { status = 0, code = '', payload = {} } = {}) {
    super(message)
    this.name = 'PathsError'
    this.status = status
    this.code = code
    this.payload = payload
  }
}

const seg = (value) => encodeURIComponent(String(value))

/**
 * @param {object} options
 * @param {string} options.baseUrl Backend origin, e.g. `https://app.example.com` (`/api` is appended).
 * @param {string} [options.token] Bearer token.
 * @param {() => (string|null|Promise<string|null>)} [options.getToken] Fresh token per request; overrides `token`.
 * @param {typeof fetch} [options.fetch] Custom fetch implementation.
 * @param {(usage: {surface: string, method: string, path: string, status: number, durationMs: number}) => void} [options.usageHook]
 * @param {Record<string, string>} [options.headers] Extra headers.
 */
export function createPathsClient(options = {}) {
  let base = String(options.baseUrl || '').trim().replace(/\/+$/, '')
  if (!/^https?:\/\//.test(base)) throw new TypeError('baseUrl must start with http:// or https://')
  base = base.replace(/\/api$/, '')
  const fetchImpl = options.fetch || globalThis.fetch
  if (typeof fetchImpl !== 'function') throw new TypeError('A fetch implementation is required')
  const extraHeaders = { ...(options.headers || {}) }

  const meter = (surface, method, path, status, started) => {
    if (typeof options.usageHook !== 'function') return
    try {
      options.usageHook({ surface, method, path, status, durationMs: Math.round(Date.now() - started) })
    } catch {
      /* metering must never break the caller */
    }
  }

  const send = async (method, path, { body, query, accept = 'application/json', signal } = {}) => {
    const headers = { Accept: accept, 'X-Mammoth-Contract': PATHS_CONTRACT_VERSION, ...extraHeaders }
    const token = options.getToken ? await options.getToken() : options.token
    if (token) headers.Authorization = `Bearer ${token}`
    if (body !== undefined) headers['Content-Type'] = 'application/json'
    const params = new URLSearchParams()
    Object.entries(query || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
    })
    const url = `${base}/api${path}${params.toString() ? `?${params}` : ''}`
    return fetchImpl(url, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), signal })
  }

  const json = async (surface, method, path, init = {}) => {
    const started = Date.now()
    let status = 0
    try {
      const response = await send(method, path, init)
      status = response.status
      const text = await response.text()
      let payload
      try { payload = JSON.parse(text) } catch {
        if (!response.ok) throw new PathsError(`Request failed (${status})`, { status })
        throw new PathsError('Response is not valid JSON', { status, code: 'invalid_response' })
      }
      const failed = !response.ok || (payload && !Array.isArray(payload) && payload.status === 'error')
      if (failed) {
        throw new PathsError(String(payload?.error || payload?.detail || payload?.message || `Request failed (${status})`), {
          status,
          code: String(payload?.code || ''),
          payload,
        })
      }
      const object = value => value !== null && typeof value === 'object' && !Array.isArray(value)
      if (init.listResponse ? !Array.isArray(payload) || !payload.every(object) : !object(payload)) {
        throw new PathsError(init.listResponse ? 'Response must be an array of objects' : 'Response must be a JSON object',
          { status, code: 'invalid_response' })
      }
      if (init.member) {
        const value = payload[init.member]
        if (init.member === 'runs' ? !Array.isArray(value) || !value.every(object) : !object(value)) {
          throw new PathsError(`Response has an invalid ${init.member} field`, { status, code: 'invalid_response' })
        }
      }
      return payload
    } finally {
      meter(surface, method, path, status, started)
    }
  }

  const stream = async (path, body, { onEvent, signal, runId } = {}) => {
    const started = Date.now()
    let status = 0
    const events = []
    try {
      const response = await send('POST', path, { body, accept: 'text/event-stream', signal })
      status = response.status
      try {
        await readRunEventStream(response, (event) => {
          events.push(event)
          if (onEvent) onEvent(event)
        }, { runId })
      } catch (error) {
        if (error instanceof PathsError) throw error
        throw new PathsError(error.message, { status: error.status || status, code: error.code || '', payload: error.payload || {} })
      }
      return events
    } finally {
      meter('mind', 'POST', path, status, started)
    }
  }

  const client = {
    contract: PATHS_CONTRACT_VERSION,

    // ── Mammoth Mind: agent runs ─────────────────────────────────────────
    tools: ({ repo } = {}) => json('mind', 'GET', '/mammoth/tools', { query: { repo } }),

    /** Start a run; resolves with all events once the stream ends. */
    streamRun(message, { agentId = 'assistant', repo, approvalMode = 'tools', completionGoal, threadId, recursive = false,
      surface, task, history, attachedFileIds, onEvent, signal } = {}) {
      if (!['tools', 'always'].includes(approvalMode)) throw new TypeError("approvalMode must be 'tools' or 'always'")
      const body = { message, agent_id: agentId, approval_mode: approvalMode }
      if (surface !== undefined) {
        if (!['mind', 'agent_workspace'].includes(surface)) throw new TypeError("surface must be 'mind' or 'agent_workspace'")
        body.surface = surface
      }
      if (task !== undefined) {
        if (typeof task !== 'string') throw new TypeError('task must be a task key string')
        body.task = task
      }
      if (history !== undefined) {
        if (!Array.isArray(history) || history.some(turn => !turn || typeof turn !== 'object' || Array.isArray(turn))) {
          throw new TypeError('history must be an array of conversation objects')
        }
        body.history = history.map(turn => ({ ...turn }))
      }
      if (attachedFileIds !== undefined) {
        if (!Array.isArray(attachedFileIds) || attachedFileIds.some(id => typeof id !== 'string')) {
          throw new TypeError('attachedFileIds must be an array of strings')
        }
        body.attached_file_ids = [...attachedFileIds]
      }
      if (recursive !== false) {
        if (recursive !== true && (!recursive || typeof recursive !== 'object' || Array.isArray(recursive))) {
          throw new TypeError('recursive must be a boolean or budget object')
        }
        body.recursive = recursive
      }
      if (completionGoal !== undefined) {
        if (!['answer', 'proposal', 'validated', 'applied'].includes(completionGoal)) throw new TypeError('Invalid completionGoal')
        body.completion_goal = completionGoal
      }
      if (repo) body.repo_context = { root: repo }
      if (threadId) body.thread_id = threadId
      return stream('/mammoth/runs', body, { onEvent, signal })
    },

    decide(runId, approvalId, decision, { note = '', onEvent, signal } = {}) {
      if (!['approve', 'reject'].includes(decision)) throw new TypeError("decision must be 'approve' or 'reject'")
      return stream(`/mammoth/runs/${seg(runId)}/approval`, { approval_id: approvalId, decision, note }, { onEvent, signal, runId })
    },

    continueRun: (runId, { onEvent, signal } = {}) =>
      stream(`/mammoth/runs/${seg(runId)}/continue`, {}, { onEvent, signal, runId }),

    /**
     * Drive a run to a terminal state. `approve(approvalData)` may return true/'approve' or false/'reject'.
     * Without it the run stops at the first approval and `pendingApproval` is set.
     */
    async run(message, { approve, maxApprovals = 10, onEvent, ...rest } = {}) {
      let state = null
      const track = (event) => {
        state = reduceRunEvent(state, event)
        if (onEvent) onEvent(event, state)
      }
      await client.streamRun(message, { ...rest, onEvent: track })
      let used = 0
      while (state?.status === 'awaiting_approval' && state.approval && approve && used < maxApprovals) {
        used += 1
        const verdict = await approve(state.approval)
        const decision = verdict === true || verdict === 'approve' ? 'approve' : 'reject'
        await client.decide(state.id, state.approval.id, decision, { onEvent: track, signal: rest.signal })
      }
      return {
        runId: state?.id || '',
        status: state?.status || 'failed',
        reply: state?.reply || '',
        error: state?.error || '',
        pendingApproval: state?.status === 'awaiting_approval' ? state.approval : null,
        progress: state?.progress || null,
        state,
      }
    },

    cancelRun: (runId) => json('mind', 'POST', `/mammoth/runs/${seg(runId)}/cancel`, { body: {} }),
    getRun: async (runId, { after = 0 } = {}) => (await json('mind', 'GET', `/mammoth/runs/${seg(runId)}`, { query: { after: after || undefined }, member: 'run' })).run,
    async recoverRun(runId) {
      const snapshot = await client.getRun(runId)
      if (snapshot?.id !== runId) throw new PathsError('Saved run identity does not match the request', { code: 'invalid_snapshot' })
      try {
        return hydrateRun(snapshot)
      } catch (error) {
        throw new PathsError(error.message, { code: 'invalid_snapshot' })
      }
    },
    listRuns: async () => (await json('mind', 'GET', '/mammoth/runs', { member: 'runs' })).runs,

    // ── Repositories (bring your own) ────────────────────────────────────
    listRepos: () => json('repos', 'GET', '/mammoth/repo-sources'),
    connectRepo: (repo) => json('repos', 'POST', '/mammoth/repo-sources', { body: { repo } }),
    syncRepo: (sourceId) => json('repos', 'POST', `/mammoth/repo-sources/${seg(sourceId)}/sync`, { body: {} }),
    removeRepo: (sourceId) => json('repos', 'DELETE', `/mammoth/repo-sources/${seg(sourceId)}`),
    proposeChange: (sourceId, changes, { title = '' } = {}) =>
      json('repos', 'POST', `/mammoth/repo-sources/${seg(sourceId)}/propose`, { body: { changes, title } }),

    listTasks: () => json('tasks', 'GET', '/tasks', { listResponse: true }),
    saveTask: (task) => json('tasks', 'POST', '/tasks', { body: task }),
    listArtifacts: () => json('artifacts', 'GET', '/workspace/artifacts'),
    saveArtifact: (artifact) => json('artifacts', 'POST', '/workspace/artifacts', { body: artifact }),
    getArtifactRun: (artifactId) => json('artifacts', 'GET', `/workspace/artifacts/${seg(artifactId)}/run`),
    deleteArtifact: (artifactId) => json('artifacts', 'DELETE', `/workspace/artifacts/${seg(artifactId)}`),
    clearArtifacts: () => json('artifacts', 'DELETE', '/workspace/artifacts'),
    readDocument: (fileId, { scope = 'chat', start = 0, count = 6 } = {}) => {
      if (!['chat', 'atlas'].includes(scope)) throw new TypeError('Document scope must be chat or atlas')
      return json('documents', 'GET', `/${scope === 'chat' ? 'mammoth' : 'atlas'}/files/${seg(fileId)}/content`, { query: { start, count } })
    },
    createDocumentReview: (fileId, goal, { scope = 'chat' } = {}) =>
      json('documents', 'POST', '/mammoth/document-reviews', { body: { file_id: fileId, scope, goal } }),
    listDocumentReviews: (fileId, { scope = 'chat' } = {}) =>
      json('documents', 'GET', '/mammoth/document-reviews', { query: { file_id: fileId, scope } }),
    getDocumentReview: (id) => json('documents', 'GET', `/mammoth/document-reviews/${seg(id)}`),
    advanceDocumentReview: (id, { confirmModelUsage = false } = {}) => {
      if (confirmModelUsage !== true) throw new TypeError('Explicit model-usage confirmation is required')
      return json('documents', 'POST', `/mammoth/document-reviews/${seg(id)}/advance`, { body: { confirm_model_usage: true } })
    },
    deleteDocumentReview: (id) => json('documents', 'DELETE', `/mammoth/document-reviews/${seg(id)}`),
    ownerExecutionCapabilities: (repo = '') => json('owner_execution', 'GET', '/owner-executions/capabilities', { query: { repo } }),
    prepareOwnerExecution: (repo, changes, { baseSha, profile, acceptance }) =>
      json('owner_execution', 'POST', '/owner-executions', { body: { repo_context: { root: repo }, changes, base_sha: baseSha, profile,
        ...(acceptance === undefined ? {} : { acceptance }) } }),
    getOwnerExecution: (id) => json('owner_execution', 'GET', `/owner-executions/${seg(id)}`),
    approveOwnerExecution: (id, { repo, approvalDigest }) =>
      json('owner_execution', 'POST', `/owner-executions/${seg(id)}/approve`, { body: { repo_context: { root: repo }, approval_digest: approvalDigest } }),
    cancelOwnerExecution: (id) => json('owner_execution', 'POST', `/owner-executions/${seg(id)}/cancel`, { body: {} }),
    applyOwnerExecution: (id, { repo, approvalDigest }) =>
      json('owner_execution', 'POST', `/owner-executions/${seg(id)}/apply`, { body: { repo_context: { root: repo }, approval_digest: approvalDigest } }),

    // ── Notes ────────────────────────────────────────────────────────────
    listNotes: () => json('notes', 'GET', '/notes', { listResponse: true }),
    saveNote: (content, { title, id, ...fields } = {}) =>
      json('notes', 'POST', '/notes', { body: { ...fields, content, ...(title !== undefined ? { title } : {}), ...(id ? { id } : {}) } }),
    deleteNote: (noteId) => json('notes', 'DELETE', `/notes/${seg(noteId)}`),

    // ── Build log ────────────────────────────────────────────────────────
    listBuildLog: () => json('buildlog', 'GET', '/buildlog', { listResponse: true }),
    logBuild: (title, { description = '', ...fields } = {}) => json('buildlog', 'POST', '/buildlog', { body: { ...fields, title, description } }),

    // ── Terminal (owner/admin only) ──────────────────────────────────────
    execTerminal: (cmd) => json('terminal', 'POST', '/terminal/exec', { body: { cmd } }),
  }
  return client
}
