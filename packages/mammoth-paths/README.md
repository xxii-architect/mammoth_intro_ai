# @mammothos/paths

**Mammoth Paths** is the MammothOS workspace SDK. Use it to embed Mammoth Mind agent runs (with visible traces and approvals), bring-your-own repositories, notes, and the build log in your own software.

- Zero dependencies. Uses the platform `fetch` (Node 18+, all modern browsers).
- Versioned contracts: `mammoth.paths.v1` (client) and `mammoth.run.v1` (run events).
- Every call is scoped server-side to the caller's token.

> The package is `private: true` and consumed from source by the MammothOS app. Remove `private` when you are ready to publish.

## Quick start

```js
import { createPathsClient } from '@mammothos/paths'

const paths = createPathsClient({
  baseUrl: 'https://your-mammothos-backend',
  getToken: async () => session.access_token,
  usageHook: (u) => console.debug('[paths]', u.surface, u.status, u.durationMs),
})

await paths.connectRepo('owner/repo')

const result = await paths.run('Where is the session cookie set?', {
  repo: 'owner/repo',
  onEvent: (event, state) => render(state),
  approve: async (approval) => confirm(`Allow ${approval.tool}?`),
})

console.log(result.status, result.reply)
```

Without `approve`, a run that needs approval stops with `status: 'awaiting_approval'` and `pendingApproval` set. Call `paths.decide(runId, approval.id, 'approve' | 'reject')` later.

## React

```jsx
import { useSyncExternalStore, useMemo } from 'react'
import { createRunStore } from '@mammothos/paths'

function useRunStore() {
  const store = useMemo(() => createRunStore(), [])
  const run = useSyncExternalStore(store.subscribe, store.getSnapshot)
  return [run, store]
}

// paths.streamRun(message, { onEvent: store.dispatch })
```

`run` exposes `status`, `plan` (`[{title, status}]`), `approval`, `reply`, `error`, and the raw `events`.

## API

| Method | Surface | Access |
| --- | --- | --- |
| `tools({ repo })` | Tool catalog visible to you | signed in |
| `streamRun(message, opts)` / `run(message, opts)` | Start a Mammoth Mind run | signed in |
| `decide(runId, approvalId, 'approve'\|'reject')` | Resume a paused run | run owner |
| `continueRun(runId, opts)` | Continue partial/recoverable work with bounded additional model usage | run owner |
| `cancelRun`, `getRun(runId, { after })`, `listRuns()` | Run control and replay | run owner |
| `listRepos`, `connectRepo`, `syncRepo`, `removeRepo` | Bring-your-own public GitHub repos | signed in |
| `proposeChange(sourceId, changes, { title })` | Branch plus git patch; never pushed | repo owner |
| `listNotes`, `saveNote`, `deleteNote` | Personal notes | Pro tier or above |
| `listBuildLog`, `logBuild` | Personal build log | Pro tier or above |
| `execTerminal(cmd)` | Allow-listed host command | owner/admin only |

Errors throw `PathsError` with `status` and `code` (for example `tier_required` or `platform_denied`).

## Run events

`run.started`, `plan.updated`, `reasoning.summary`, `tool.call`, `tool.result`, `approval.requested`, `approval.resolved`, `diff.proposed`, `message.delta`, `message.completed`, `run.awaiting_approval`, `run.completed`, `run.failed`, `run.cancelled`, `run.partial`, `run.continued`, `run.recovering`, `model.completed`.

`partial` is terminal for the current stream, not success. The reducer exposes
`can_continue`, `failure_code`, and reported model `diagnostics`. Call
`continueRun` explicitly when appropriate; it may use more credits and retains
the run ID and saved work. Continuation does not bypass access or approvals and
is limited to two continuations. Python offers the matching `continue_run`.
Completion metadata does not certify factual accuracy or task correctness.
An SSE stream ending without a terminal event raises an explicit error. Query
the saved run before retrying; this is not automatic reconnect or background
execution.
Model diagnostics also identify `decision_protocol` (`json_schema`,
`json_object`, or `text`). Only recognized supported models use strict schema
decisions; all paths still use backend argument/access/approval checks.

## Tests

```bash
npm test
```
