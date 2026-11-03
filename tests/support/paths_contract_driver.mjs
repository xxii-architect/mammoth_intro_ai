import assert from 'node:assert/strict'
import { createPathsClient, PathsError } from '@mammothos/paths'
let token = 'tenant-a'
const client = createPathsClient({ baseUrl: process.argv[2], getToken: async () => token })
const result = await client.run('Review the context', {
  surface: 'agent_workspace', task: 'analyze_codebase',
  history: [{ role: 'user', text: 'Prior workspace turn' }, { role: 'assistant', message: 'Prior answer' }],
  attachedFileIds: ['fixture-file'], threadId: 'must-not-persist-to-mind',
})
assert.equal(result.status, 'completed')
assert.equal(result.reply, 'Context received.')
assert.equal(result.state.events[0].data.repo, null)
assert.equal((await client.recoverRun(result.runId)).status, 'completed')
token = 'tenant-b'
await assert.rejects(client.getRun(result.runId), error => error instanceof PathsError && error.status === 404)
token = 'tenant-a'
await assert.rejects(client.run('Read platform', { repo: 'platform', surface: 'agent_workspace' }),
  error => error instanceof PathsError && error.status === 403 && error.code === 'repo_access_denied' &&
    error.payload.message === error.message)
const pending = await client.run('Review first', { surface: 'agent_workspace', approvalMode: 'always' })
assert.equal(pending.status, 'awaiting_approval')
const approved = await client.decide(pending.runId, pending.pendingApproval.id, 'approve')
assert.equal(approved.at(-1).type, 'run.completed')
const cancelled = await client.run('Do not execute', { surface: 'agent_workspace', approvalMode: 'always' })
assert.equal(cancelled.status, 'awaiting_approval')
await client.cancelRun(cancelled.runId)
assert.equal((await client.recoverRun(cancelled.runId)).status, 'cancelled')
token = null
await assert.rejects(client.run('Anonymous'), error => error instanceof PathsError && error.status === 401)
console.log(JSON.stringify({ context_run: result.runId, cancelled_run: cancelled.runId }))
