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
| `listTasks()`, `saveTask(task)` | Backend task state; only manual cards are editable | signed in, own items |
| `listArtifacts()`, `saveArtifact(artifact)` | Saved outputs, metadata and server-assigned revisions | signed in, own items |
| `getArtifactRun(id)` | Read-only associated task / client-supplied saved history | signed in, own items |
| `deleteArtifact(id)`, `clearArtifacts()` | Remove saved outputs, not curricula/notes/flashcards | signed in, own items |
| `listNotes`, `saveNote`, `deleteNote` | Personal notes | Pro tier or above |
| `listBuildLog`, `logBuild` | Personal build log | Pro tier or above |
| `execTerminal(cmd)` | Allow-listed host command | owner/admin only |

Errors throw `PathsError` with `status` and `code` (for example `tier_required` or `platform_denied`).

Task/artifact methods return unmodified backend payloads. Python offers matching
snake-case methods. Saving an existing artifact ID retains up to ten previous
snapshots with server-assigned revision numbers. `origin` and `lineage` record
run/task/repository/base-SHA context only when available. A base SHA identifies
the selected Git ref, not a clean working tree. `quality` and `verification`
do not certify correctness, acceptance-test success, or approval to apply code.
Run lookup returns 404 when unavailable; task edits return 409 for run-backed
records. These additions do not change the `mammoth.paths.v1` contract.

## Owner isolated execution pilot

`ownerExecutionCapabilities(repo)`, `prepareOwnerExecution(repo, changes,
{baseSha, profile})`, `getOwnerExecution(id)`, `approveOwnerExecution(id,
{repo, approvalDigest})`, and `cancelOwnerExecution(id)` preserve backend payloads.
Python has matching snake_case methods. Changes are `{path, content}` full-text
objects. Profiles: `python_unittest`, `python_pytest`, `node_test`.
Owner/admin checks and explicit repository access are backend-enforced;
embedding the SDK does not grant access. The backend pilot is disabled by default.
Approval binds a committed snapshot and image and expires after 15 minutes.
Tests run in offline Docker only, never on the host, with no automatic merge/push.
Query the saved job after a request timeout rather than retrying its approval.
Uncommitted source is not included. Passing a profile is not independent
acceptance evidence or permission to apply the patch. Containers share the host
kernel; see the root README for reviewed-image setup and benchmark limitations.

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
