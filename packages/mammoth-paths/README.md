# @mammothos/paths

**Mammoth Paths** is the MammothOS workspace SDK. Use it to embed Mammoth Mind agent runs (with visible traces and approvals), bring-your-own repositories, notes, and the build log in your own software.

- Zero dependencies. Uses the platform `fetch` (Node 18+, all modern browsers).
- Versioned contracts: `mammoth.paths.v1` (client) and `mammoth.run.v1` (run events).
- Every call is scoped server-side to the caller's token.

> The package is `private: true` and consumed from source by the MammothOS app. Remove `private` when you are ready to publish.

### Runtime usage controls

`await paths.runtimeUsage()` reads `mammoth.runtime-usage.v1`.
`await paths.setRuntimeTokenLimit(100000)` sets an optional UTC daily ceiling
across the caller's workspace accounts; `0` blocks new covered completion calls,
`null` removes the ceiling. Unknown outcomes keep their full reservations.
Reported tokens, reservations and missing accounting are distinct. No automatic
retry/reset or model call occurs on reading/saving controls.
This shared-disk server ledger is not dollar spend, Copilot credits, invoices,
embedding metering or authoritative multi-member tenant billing. Custom paths,
internal provider-SDK retries and local generation outside hosted requests are
not separately covered. Python has matching `runtime_usage()` and
`set_runtime_token_limit()` methods.

### Applied branch export

`await paths.exportOwnerBranch(id, {repo: 'owner/repo', expectedCommit: commit,
confirmPrivateExport: true})` returns an `export` receipt for the owner-approved
applied commit. Admin/owner/repository checks remain backend-enforced. Both SDKs
share `mammoth.owner-branch-export.v1`; the delta bundle requires the existing
base and never pushes, imports or runs code. Maximum 8 MiB of decoded bytes.
Identity/size/header/SHA-256 checks reject malformed receipts without retry.
Use `await decodeOwnerBranchExport(receipt, {executionId: id, expectedCommit:
commit})` for verified `Uint8Array` bytes. Web Crypto in a secure context is
required; absence raises `verification_unavailable`, never unverified success.
Node embedders whose runtime lacks global Web Crypto must supply it.
Keep source bundles private. Import/verify with a local Git tool and compare
the commit before selecting it in Desktop. GitHub's exact branch fallback link
only works after an explicit push; neither link transfers unpublished work.

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

### Agent Workspace context

```js
const result = await paths.run('Review input validation', {
  surface: 'agent_workspace',
  task: 'analyze_codebase',
  history: [{ role: 'user', text: 'Focus on the selected module' }],
  attachedFileIds: ['your-uploaded-document-id'],
})
```

Python uses the same keys except `attached_file_ids`. All options are additive;
omitting them preserves the previous payload. Workspace runs use bounded supplied
history (last eight turns, 800 characters each), never private Mind history, and
do not append to Mind threads even if `threadId` is supplied. Task keys select
server-owned briefs; unknown keys add no brief. Attachment and repository access
remain backend-controlled. No repo option means no repo context.

`getToken` is evaluated per request, including approval and recovery; the caller
owns token refresh. `PathsError` retains backend status, code and payload for JSON
and streamed denials. These options add no automatic retries or new privileges.

### JSON response guards

JSON methods require object responses, except `listTasks`, `listNotes` and
`listBuildLog`, which require arrays of objects. `getRun` and `listRuns` require
object `run` and array-of-objects `runs` envelope fields. Malformed JSON, empty
successful bodies, null/missing records or wrong containers throw `PathsError`
with code `invalid_response` rather than becoming empty defaults. Valid empty
arrays and extension fields are preserved. Malformed response messages do not
echo raw body text. Usage hooks report HTTP status once, not payload validity.
Most methods use container guards, not full nested schemas; snapshot recovery
and document reviews have the deeper checks described below. No retries,
permission changes or dependency additions.

### Saved document-review evidence

Review methods additionally validate `mammoth.document-review.v1` identity,
source hashes, sequential assessment coverage, safe-integer reported usage,
inflight markers, budget-extension history and hierarchical synthesis traversal/
citation lineage. Get/mutation receipts must match the requested review; create/
list must match the selected file and scope; deletion must name the requested ID.
Malformed evidence throws `PathsError` with `code: 'invalid_response'`, without
echoing the response body or retrying. Valid empty lists, additive fields,
partial/active/blocked states and reported usage over the ceiling are preserved.

Custom transports and the app can share `validateDocumentReview(record,
{ reviewId, fileId, scope })`; it returns the original record or throws an error
with `code: 'invalid_response'`. This is a structural guard, not authorization,
live source-freshness checking, factual verification or a billing ledger.

After any timeout or malformed mutation response, call `getDocumentReview(id)`
before deciding what to do next. Never infer that a failed HTTP response means
the provider did no work. Each new paid batch needs explicit confirmation;
reading saved state does not reclaim an active/unknown call. Configure custom
fetch timeouts above the 180-second batch ceiling plus transport overhead when
appropriate. Neither client automatically reconnects/retries these operations.

### Run stream and recovery guards

SSE requires valid UTF-8 and object JSON data (`invalid_stream`); malformed
frames no longer disappear. Comments, BOM, multiline data, CR/LF/CRLF, split
chunks and the existing trailing frame at EOF remain supported. Missing terminal
events report `stream_interrupted`. The reader is cancelled and released on exit,
including invalid data or callback errors.

Envelopes require `mammoth.run.v1`, nonblank `type`/`run_id`/`ts`, positive
safe-integer `seq` and object `data` (`invalid_event`). Unknown event types and
extensions remain supported. Streams reject mixed run IDs, duplicate/backward
sequences and gaps before callbacks; resumed streams may start above one.
Approval/continuation must match the requested ID. Custom readers can pass
`readRunEventStream(response, onEvent, { runId })` to bind that ID too.
The app shares these guards. Reducer replay remains idempotent and permits gaps;
full recovery requires consecutive events starting at one.

`recoverRun` reports malformed saved envelopes/metadata as `invalid_snapshot`
and never executes work. Optional plan/diagnostics are arrays of objects,
recursive/progress/approval are objects (or null), `can_continue` is boolean and
`failure_code` is string when present. Current saved status wins over old events.
These checks do not validate every nested field or parse timestamp dates.
Custom transports must supply complete envelopes, not invented defaults.

### Opt-in RecursiveMAS

```js
const reviewed = await paths.run('Compare these approaches and test your recommendation.', {
  agentId: 'reasoning_agent',
  recursive: { max_iterations: 2, max_tokens: 64000, max_seconds: 180, max_tool_calls: 12 },
  onEvent: (event, state) => render(state),
})
```

Python: `paths.run("Compare these approaches.", agent_id="reasoning_agent", recursive=True)`.
Both clients accept `true`/`True` for server defaults or the same snake-case budget
keys shown above. Supported lanes are Assistant, Reasoning, Research and Coding.
Normal runs remain unchanged. `recursive.updated` events and `state.recursive`
expose stages, pass, budgets and provider-reported usage without changing
`mammoth.run.v1`. Python can inspect event data or the recovered snapshot.

Recursive mode uses extra model credits. Critique is not factual verification.
All existing tool, validation and application approval boundaries remain intact.
`recursive_review` is a human critique gate authorizing synthesis only; it is not
permission to execute tools. Decisions use the existing `decide` method and are
single-use. Saved stages survive approval/restart without re-execution; unknown
interrupted provider/tool outcomes stop rather than being replayed.
Missing provider usage stops recursive mode explicitly. Token counts are not
dollar prices and cannot include unknown unsuccessful-provider request charges.

Both clients finish the current stream at a terminal run event, including
`run.awaiting_approval`, without waiting for the HTTP connection to close.
The app disables approval controls while a request is still in flight; saved
Agent-page approvals survive refresh, but the backend still verifies their
current identity and repository base before allowing any action.

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

Pass `completionGoal: 'proposal' | 'validated' | 'applied' | 'answer'` to
`streamRun` / `run` (Python: `completion_goal`). It is a minimum requested
result, not authorization. Models/tools can raise it, never lower it.
`progress` on the result and reducer state records actual read ranges/hashes,
executions/checks, blockers and branch/commit evidence. Python exposes
`RunResult.progress`. A prose completion claim without the required evidence
ends partial with `missing_evidence`, preserving explicit continuation and both
approval gates. Saved plans remain model-written, not verified evidence.

For managed owner `validated` / `applied` goals, the runtime queues actions from
fresh receipts; the model cannot directly request run/apply tools with guessed
or consumed execution identities. A failed check needs a newly prepared candidate
against committed source, fresh validation approval and separate application
approval. Bounded failure excerpts remain in
`progress.executions[].failure_excerpts`, including truncation flags, for review
and repair. This is control-flow support, not a model-quality guarantee.

Owner `validated` / `applied` decisions with successful readiness and source-read
receipts allow up to 8,192 output tokens so exact edits have room to finish;
ordinary decisions remain capped at 4,096. A truncated decision gets one bounded
repair. A duplicate tool decision is blocked and gets at most one corrective
decision per stream before stopping; the duplicate itself never executes.
Repair markers do not age recent source excerpts into the clipped history
budget. These limits can increase actual model usage; they do not prove that a
provider will produce a valid patch or that the change meets visual acceptance.

The backend routes the Coding lane and proposal/validation/application goals
through its coding workload policy. Default preference is OpenAI, then DeepSeek,
then Ollama/local; operators can choose `MAMMOTH_CODING_LLM_ADAPTER=deepseek`
without changing tutor/general routing. Explicit offline settings still win.
Clients cannot grant themselves providers, tools or repository access. Search
supports an exact relative `path`; after two discovery calls with source matches,
the next coding decision is constrained to use evidence rather than keep
searching/listing/refreshing readiness. Neither a route nor this checkpoint
certifies task completion. Operator CLI smoke comparisons accept
`--provider openai|deepseek|coding` with `--model` consent; inspect actual provider,
source-read counts and independent acceptance, not only prose or build success.

## API

| Method | Surface | Access |
| --- | --- | --- |
| `tools({ repo })` | Tool catalog visible to you | signed in |
| `streamRun(message, opts)` / `run(message, opts)` | Start a Mammoth Mind run | signed in |
| `decide(runId, approvalId, 'approve'\|'reject')` | Resume a paused run | run owner |
| `continueRun(runId, opts)` | Continue partial/recoverable work with bounded additional model usage | run owner |
| `cancelRun`, `getRun(runId, { after })`, `listRuns()` | Run control and replay | run owner |
| `recoverRun(runId)` | Read full saved state without execution or approvals | run owner |
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

## Private indexed document reads

`readDocument(fileId, {scope: 'chat', start: 0, count: 6})` and Python
`read_document(file_id, scope="chat", start=0, count=6)` read a bounded page of
caller-owned indexed text; `scope` may also be `atlas`. The server enforces access
and count 1-10. Follow `next_start` until null to enumerate indexed sections.
`total_chunks` and `selection` distinguish selected sections from the index;
`selection.review_complete` is false because reading a page is not a model review.
Extraction warnings/limits remain relevant even after every indexed section is
retrieved. Requests are read-only and use the `documents` metering surface.

Recursive snapshots also expose additive `budget`, `completed_stages` and
`partial_output` metadata. Input allowances identify local model-text tokenization
plus byte envelopes for supported official models, or conservative byte fallback,
not actual billed usage. A saved draft after failure is unverified;
it must never be treated as a completed recursive review or automatically retried.

### Saved indexed-section review

| Python | JavaScript |
| --- | --- |
| `create_document_review(file_id, goal, scope="chat")` | `createDocumentReview(fileId, goal, {scope: 'chat'})` |
| `list_document_reviews(file_id, scope="chat")` | `listDocumentReviews(fileId, {scope: 'chat'})` |
| `get_document_review(id)` | `getDocumentReview(id)` |
| `advance_document_review(id, confirm_model_usage=True)` | `advanceDocumentReview(id, {confirmModelUsage: true})` |
| `delete_document_review(id)` | `deleteDocumentReview(id)` |
| `synthesize_document_review(id, confirm_model_usage=True)` | `synthesizeDocumentReview(id, {confirmModelUsage: true})` |
| `extend_document_review_budget(id, expected_max_tokens=64000, max_tokens=100000, confirm_budget_extension=True)` | `extendDocumentReviewBudget(id, {expectedMaxTokens: 64000, maxTokens: 100000, confirmBudgetExtension: true})` |

Methods preserve server envelopes (`review` / `reviews`) on the `documents` usage
surface. Create/get/list/delete never invoke models. Advance requires explicit
confirmation for each batch of up to three sections and never retries itself.
Set the Python transport timeout above 180 seconds for a full batch; if a proxy
or client disconnects sooner, reload saved state instead of resending blindly.
The default lifetime ceiling is 64,000 reported tokens, not a per-batch reset.
`mammoth.document-review.v1` stores source-hashed, sequential indexed assessments
with literal quotes, warnings, usage and precise stop status. Completion means
all indexed sections have assessments, not factual verification, original-file
coverage or combined synthesis. Unknown calls, failed outputs and cap stops are
blocked; completed section calls are not replayed. Source deletion removes its
reviews. Up to 20 reviews are retained per private library; delete unused reviews.

Synthesis is separately confirmed after indexed assessment completes. Each batch
performs up to three units, combining groups of at most eight saved assessments/
intermediate summaries into checkpointed nodes. Its final input-traversal coverage
must include every indexed assessment, without truncation. It does not reread
full source; summaries can lose detail. Citations preserve existing source-index
lineage and resolve to literal saved quotes, not verified entailment. Progress is
under `review.synthesis`; `review_complete` still means indexed assessment only.
Synthesis shares cumulative review usage and the 180-second batch limit.

Budget extension is model-free, explicitly confirmed and audited. It compares
`expected_max_tokens` to the stored ceiling and raises the total to at most
128,000; usage is never reset. A stale request fails with 409. Only known cap
stops without uncertain/invalid calls can be unlocked; no completed unit is
replayed, and a new paid batch needs separate confirmation. An extension receipt
is permission for future usage, not a model call or invoice guarantee. Existing
recursive-run limits are unchanged.

## Owner isolated execution pilot

`ownerExecutionCapabilities(repo)`, `prepareOwnerExecution(repo, changes,
{baseSha, profile, acceptance?})`, `getOwnerExecution(id)`, `approveOwnerExecution(id,
{repo, approvalDigest})`, `cancelOwnerExecution(id)`, and
`applyOwnerExecution(id, {repo, approvalDigest})` preserve backend payloads.
Python has matching snake_case methods. Changes are `{path, content}` full-text
objects or `{path, edits: [{old, new}]}`. Each exact old string must match once
in the frozen committed base, not uncommitted checkout text. New files need
content. Explicit deletion uses `{path, delete: true}` alone and requires a
permitted existing base file. Empty content is not deletion. Removal is visible
in the patch and isolated candidate, with the same separate branch approval.
Optional `acceptance` carries `expected_behavior` and `regression_tests` arrays
in both clients. Profiles: `python_unittest`, `python_pytest`, `node_test`, `ui_build`,
`ui_component`, `ui_browser`. Frontend profiles require a separate operator-reviewed image
with locked UI dependencies. Build compiles the production UI; component checks
render the actual trust row at explicit zero/low/high scores. Neither claims
general acceptance or browser-interaction coverage. Manifest changes require a
reviewed image rebuild, never runtime network/package installation.
Owner/admin checks and explicit repository access are backend-enforced;
embedding the SDK does not grant access. The backend pilot is disabled by default.
Approval binds a committed snapshot and image and expires after 15 minutes.
Tests run in offline Docker only, never on the host, with no automatic merge/push.
Allow at least 420 seconds for synchronous approval. Query the saved job after
a request timeout rather than retrying its approval.
Read `isolation.profiles` in capabilities for tool availability and selected-repo
frontend compatibility; `isolation.profile_reasons` explains mismatches.
The current ui_* profiles target the MammothOS command-center workspace, not
arbitrary Next/Vite apps. Base/candidate manifests must match the reviewed image,
or preparation rejects before freezing an approval. Other apps need compatible
operator-reviewed validation support, not a repository switch or unrelated tests.
`ui_browser` builds and runs the declared workspace browser suites.
Unknown/unavailable profiles are rejected before preparation;
availability is not proof of project dependencies or change coverage.
Uncommitted source is not included. Passing a profile is not independent
acceptance evidence or permission to apply the patch. Containers share the host
kernel; see the root README for reviewed-image setup and benchmark limitations.

Application is a separate approval after successful validation with no observed
regressions. Pass `execution.application.approval_digest`, not the test approval
digest. It creates a commit on a new local owner branch and never changes the
selected checkout/index or pushes/merges/deploys. The approval expires after
15 minutes and is bound to the proposal, image, base and candidate evidence.
Python exposes `apply_owner_execution(id, repo=..., approval_digest=...)`.
Query `getOwnerExecution` after transport/storage errors before taking further
action; restart reconciliation does not automatically retry branch creation.
Tenant application and paid entitlements are not enabled.

## Run events

### Recover without retrying work

```js
const saved = await paths.recoverRun(runId) // one GET; no model credits or tool execution
store.reset(saved)
```

For custom transports, import `hydrateRun(fullSnapshot)` to rebuild a state from
the complete saved run. Do not pass an `after`-filtered suffix. The saved status
and pending approval override historical events, including cancellation saved
without another event. Recovery never continues a run or invokes an approval
policy. Python provides `recover_run(run_id)` returning `RunResult`, including
the full `snapshot` and current `progress`. Backend ownership/expiry rules remain
authoritative for subsequent actions.

The shared reducer ignores duplicate sequence numbers, rejects cross-run events
and rejects new out-of-order events. Recover the full snapshot after a replay
ordering error. This is explicit snapshot recovery, not automatic transport
reconnection or durable background execution. MammothOS exposes the same evidence
under Workspace > Run Review, with explicit JSON download and no action controls.
Exports can contain prompts/source/logs; review before sharing.

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
