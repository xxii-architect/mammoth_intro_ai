import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  createPathsClient,
  createRunStore,
  createSseParser,
  PathsError,
  reduceRunEvent,
} from '../src/index.js'

const RUN_ID = 'run-0123456789abcdef'
const ev = (seq, type, data = {}) => ({ contract: 'mammoth.run.v1', run_id: RUN_ID, seq, type, ts: 't', data })
const sse = (events) => events.map((e) => `event: ${e.type}\r\ndata: ${JSON.stringify(e)}\r\n\r\n`).join('')

function fakeFetch(routes) {
  const calls = []
  const impl = async (url, init) => {
    const { pathname } = new URL(url)
    calls.push({ url, pathname, init, body: init.body ? JSON.parse(init.body) : undefined })
    const route = routes[`${init.method} ${pathname}`]
    if (!route) return new Response(JSON.stringify({ status: 'error', error: 'nope' }), { status: 404 })
    if (route.sse) {
      const text = sse(route.sse)
      const stream = new ReadableStream({
        start(controller) {
          const bytes = new TextEncoder().encode(text)
          // Split mid-frame to exercise buffering.
          controller.enqueue(bytes.slice(0, 7))
          controller.enqueue(bytes.slice(7))
          controller.close()
        },
      })
      return new Response(stream, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
    }
    return new Response(JSON.stringify(route.body), { status: route.status || 200 })
  }
  return { impl, calls }
}

test('sse parser handles CRLF, split chunks, and multi-line data', () => {
  const out = []
  const parser = createSseParser((d) => out.push(d))
  parser.push('data: {"a":\r\n')
  parser.push('data: 1}\r\n\r\ndata: {"b"')
  parser.push(': 2}')
  parser.end()
  assert.deepEqual(out, [{ a: 1 }, { b: 2 }])
})

test('reducer folds a run without mutating input', () => {
  const s1 = reduceRunEvent(null, ev(1, 'run.started', { tools: ['docs_search'] }))
  const s2 = reduceRunEvent(s1, ev(2, 'plan.updated', { plan: [{ title: 'Look', status: 'pending' }] }))
  const s3 = reduceRunEvent(s2, ev(3, 'run.completed', { reply: 'Done well' }))
  assert.equal(s1.events.length, 1)
  assert.equal(s3.status, 'completed')
  assert.equal(s3.reply, 'Done well')
  assert.deepEqual(s3.tools, ['docs_search'])
})

test('run store notifies subscribers', () => {
  const store = createRunStore()
  let calls = 0
  const off = store.subscribe(() => { calls += 1 })
  store.dispatch(ev(1, 'run.started'))
  off()
  store.dispatch(ev(2, 'run.cancelled'))
  assert.equal(calls, 1)
  assert.equal(store.getSnapshot().status, 'cancelled')
})

test('run completes and sends auth + contract headers', async () => {
  const { impl, calls } = fakeFetch({
    'POST /api/mammoth/runs': { sse: [ev(1, 'run.started'), ev(2, 'tool.call', { tool: 'docs_search', call_id: 'c1' }), ev(3, 'run.completed', { reply: 'Hi' })] },
  })
  const usage = []
  const client = createPathsClient({ baseUrl: 'https://x.test/api/', token: 't1', fetch: impl, usageHook: (u) => usage.push(u) })
  const result = await client.run('hello', { repo: 'owner/repo' })
  assert.equal(result.status, 'completed')
  assert.equal(result.reply, 'Hi')
  assert.equal(result.runId, RUN_ID)
  assert.equal(calls[0].url, 'https://x.test/api/mammoth/runs')
  assert.equal(calls[0].init.headers.Authorization, 'Bearer t1')
  assert.equal(calls[0].init.headers['X-Mammoth-Contract'], 'mammoth.paths.v1')
  assert.deepEqual(calls[0].body, { message: 'hello', agent_id: 'assistant', approval_mode: 'tools', repo_context: { root: 'owner/repo' } })
  assert.equal(usage[0].surface, 'mind')
})

test('run resumes through approval policy', async () => {
  const { impl, calls } = fakeFetch({
    'POST /api/mammoth/runs': { sse: [ev(1, 'approval.requested', { id: 'apr-1', tool: 'x' }), ev(2, 'run.awaiting_approval', { approval_id: 'apr-1' })] },
    [`POST /api/mammoth/runs/${RUN_ID}/approval`]: { sse: [ev(3, 'approval.resolved', {}), ev(4, 'run.completed', { reply: 'ok' })] },
  })
  const client = createPathsClient({ baseUrl: 'https://x.test', fetch: impl })
  const result = await client.run('go', { approve: async (a) => a.tool === 'x' })
  assert.equal(result.status, 'completed')
  assert.deepEqual(calls[1].body, { approval_id: 'apr-1', decision: 'approve', note: '' })
})

test('run without policy stops at approval', async () => {
  const { impl } = fakeFetch({
    'POST /api/mammoth/runs': { sse: [ev(1, 'approval.requested', { id: 'apr-1', tool: 'x' }), ev(2, 'run.awaiting_approval', {})] },
  })
  const result = await createPathsClient({ baseUrl: 'https://x.test', fetch: impl }).run('go')
  assert.equal(result.status, 'awaiting_approval')
  assert.equal(result.pendingApproval.id, 'apr-1')
})

test('errors surface as PathsError with code', async () => {
  const { impl } = fakeFetch({
    'GET /api/buildlog': { status: 403, body: { status: 'error', error: 'Needs pro', code: 'tier_required' } },
    'POST /api/mammoth/repo-sources': { body: { status: 'error', error: 'private', code: 'platform_denied' } },
  })
  const client = createPathsClient({ baseUrl: 'https://x.test', fetch: impl })
  await assert.rejects(client.listBuildLog(), (e) => e instanceof PathsError && e.status === 403 && e.code === 'tier_required')
  await assert.rejects(client.connectRepo('a/b'), (e) => e.code === 'platform_denied')
})

test('path segments are escaped and getToken is used', async () => {
  const { impl, calls } = fakeFetch({ 'DELETE /api/notes/a%2Fb': { body: { status: 'ok' } } })
  const client = createPathsClient({ baseUrl: 'https://x.test', fetch: impl, getToken: async () => 'fresh' })
  await client.deleteNote('a/b')
  assert.equal(calls[0].pathname, '/api/notes/a%2Fb')
  assert.equal(calls[0].init.headers.Authorization, 'Bearer fresh')
})

test('rejects non-http base urls', () => {
  assert.throws(() => createPathsClient({ baseUrl: 'ftp://x' }), TypeError)
})

test('partial and failed outcomes retain continuation state and diagnostics', () => {
  let run = reduceRunEvent(null, ev(1, 'model.completed', { finish_reason: 'length', usage: { total_tokens: 12 } }))
  run = reduceRunEvent(run, ev(2, 'run.partial', { reply: 'Saved', code: 'step_limit', can_continue: true }))
  assert.equal(run.status, 'partial')
  assert.equal(run.can_continue, true)
  assert.equal(run.diagnostics[0].usage.total_tokens, 12)
  run = reduceRunEvent(run, ev(3, 'run.continued'))
  assert.equal(run.status, 'running')
  assert.equal(run.reply, '')
  assert.equal(run.can_continue, false)
  run = reduceRunEvent(run, ev(4, 'run.failed', { error: 'Invalid response', code: 'invalid_response', can_continue: true }))
  assert.equal(run.status, 'failed')
  assert.equal(run.failure_code, 'invalid_response')
})

test('continuation is explicit and partial does not auto-retry or approve', async () => {
  const { impl, calls } = fakeFetch({
    'POST /api/mammoth/runs': { sse: [ev(1, 'run.partial', { reply: 'Saved', can_continue: true })] },
    [`POST /api/mammoth/runs/${RUN_ID}/continue`]: { sse: [ev(2, 'run.continued'), ev(3, 'run.completed', { reply: 'Done' })] },
  })
  const client = createPathsClient({ baseUrl: 'https://x.test', fetch: impl })
  const result = await client.run('go')
  assert.equal(result.status, 'partial')
  assert.equal(calls.length, 1)
  const events = await client.continueRun(RUN_ID)
  assert.equal(events.at(-1).data.reply, 'Done')
  assert.deepEqual(calls[1].body, {})
})

test('premature stream end is explicit rather than a running success result', async () => {
  const { impl } = fakeFetch({
    'POST /api/mammoth/runs': { sse: [ev(1, 'run.started')] },
  })
  const client = createPathsClient({ baseUrl: 'https://x.test', fetch: impl })
  await assert.rejects(client.run('go'), error => error instanceof PathsError && /before a terminal event/.test(error.message))
})
