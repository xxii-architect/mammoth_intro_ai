# RecursiveMAS

RecursiveMAS has an additive, dependency-injected orchestration core and an
opt-in Mammoth Mind production integration. Embedders can construct
`RecursiveMASRunner` with callbacks, or use the authenticated Paths run API.

## Execution Contract

A run follows `Planner -> Executor -> Critic -> Router`. A passing critique routes to synthesis. A failing critique returns to planning until the iteration budget is reached. An uncertain low-confidence critique routes to the human gate. Human rejection stops the run; approval continues at synthesis and does not replay planning or execution.

The runner accepts synchronous and asynchronous callbacks. Role adapters move synchronous calls to worker threads so they do not block the event loop. A timed-out synchronous function cannot be forcibly terminated by Python and may continue in its worker thread; callbacks with side effects should therefore be idempotent and should use their own operation-level cancellation/timeout controls.

## Limits and Failure Behavior

`Budget` bounds depth, planning iterations, reported token use, wall-clock seconds, and reported tool calls. The leash is checked before the first stage and after each role callback, so reaching a hard limit prevents the next callback from starting. Each callback also receives a wall-clock timeout based on remaining seconds. Cost reports are validated, and elapsed callback time is charged as at least the observed wall time.

Callback failures return a `failed` node and a redacted trace entry. Task cancellation marks the node stopped and is re-raised. The runner does not execute shell commands or perform provider, filesystem, or network access itself; those capabilities belong to injected role agents.

## Human Review and Resume

If no human handler is configured, the runner returns `awaiting_human` with a `RunnerCheckpoint`. A handler may return `pause`, `approve`, or `reject`. An external application can pass an authorized decision to `runner.resume(checkpoint, decision)`. Resume validates the trace, goal, and iteration, is single-use, and requires the application to authenticate and authorize the reviewer. Checkpoints are in-memory Python objects; applications that persist them must serialize artifacts safely and version their own persistence format.

## Minimal Wiring

```python
from mammoth_os.recursive import RecursiveMASRunner, RecursiveNode, RunnerConfig
from mammoth_os.recursive.adapter_bindings import build_runner_deps

runner = RecursiveMASRunner(
    build_runner_deps(planner, executor, critic, synthesizer, human_gate),
    RunnerConfig(),
)
result = await runner.run(
    RecursiveNode(id="run-1", trace_id="trace-1", role="root", goal="Complete a bounded task")
)
```

Role agents must implement the contracts in `mammoth_os.agents.adapters` and return the corresponding `Plan`, `Execution`, `Critique`, or `Synthesis` value object. The scaffold intentionally does not adapt current MammothOS agents whose input/output contracts differ; that integration belongs in explicit, tested adapters.

## Production integration

`runtime.py` connects real provider-backed planner, critic and synthesizer roles
to the existing `AgentRunner` executor, including its tool catalog, MCP access,
source observations and completion-evidence checks. It calls the same bounded
core, not a separate recursive algorithm. Failed critiques inform the next plan.
Normal runs and tutor SDK behavior are unchanged.

Enable **Recursive review** under Mammoth Mind's **More chat options** in Agent
mode. Supported lanes: Assistant, Reasoning, Research and Coding. It is off by
default and not implicitly enabled by selecting Reasoning. Python Paths accepts
`recursive=True`; JavaScript Paths accepts `recursive: true`. Both accept a budget
object with the wire keys below. `GET /api/mammoth/tools` advertises the capability;
agent manifests and module/agent endpoints advertise it as `opt_in`.

| Limit | Default | Server maximum |
| --- | ---: | ---: |
| `max_iterations` | 2 | 3 |
| `max_tokens` | 64000 | 128000 |
| `max_seconds` | 180 | 300 |
| `max_tool_calls` | 12 | 20 |

These are ceilings, not reservations or a dollar-price guarantee. Tokens are
provider-reported completion usage (input plus output), not estimates presented
as actual spend. Missing usage stops the run explicitly. Unknown interrupted
provider charges and unsuccessful fallback-attempt charges cannot be inferred;
consult provider billing. A conservative input/output allowance can stop a call
before the token ceiling. Active runtime time excludes time waiting for human
review. Tool counts record attempted invocations, including denied/failed ones.
Normal one-pass success uses at least four model completions; tools and retries
add calls. Recursive mode can therefore cost materially more than a normal run.

Planner and critic output limits are 2,048 tokens each; executor decisions retain
their normal allowances and synthesis retains its 8,192-token allowance, subject
to remaining budget. Non-synthesis calls retain headroom of the smaller of 4,096
tokens or one-eighth of the overall cap. This headroom is a target, not a guarantee
that a future synthesis prompt fits. Overall configured limits are unchanged.

`budget` in public snapshots/events records the latest call's role, remaining
tokens before admission, conservative input bound, overhead allowance, output
limit, synthesis headroom, current reservation and reported call usage when known.
Admission is recalculated at each actual leaf provider attempt, including fallback
and conversation-background expansion. Known official OpenAI models use local
`tiktoken` text counts and a byte bound for the actual shared request envelope/
schema, plus overhead. `model_tokenizer_with_byte_envelope` labels this hybrid,
not exact server chat tokenization. Compatible endpoints, unrecognized models and
missing tokenizer assets retain `utf8_byte_upper_bound`. Neither is billed usage.
Admission can stop below the reported-token ceiling and records
`stop_detail: insufficient_call_allowance`. Missing provider usage still fails
closed. Failed/fallback-attempt charges remain unknown unless reported.

Planner revisions receive earlier execution evidence but not a duplicate draft;
the executor still receives that draft for revision. Role source/draft contexts
are serialized without the previous blind 32,000-character tail clipping.
Contexts that cannot fit stop rather than silently dropping source conclusions.
`completed_stages` records cached stages. On failure, `partial_output` retains the
latest completed executor draft and the timeline labels it unverified; it is not
a passed critique, synthesis, application receipt or automatic retry.
Cap stops do not gain additional allowance or a continuation button. Explicit
recursive-run budget extensions remain future work. The separate explicit indexed-
document workflow checkpoints section assessments and synthesis in the private
document library and can deliberately extend its own ceiling up to 128,000.
It does not make recursive runs exhaustive or resume their cap stops.

Runs, cached typed role outputs and human checkpoints use the existing user-scoped
RunStore. A nonblocking OS lease prevents competing consumers across workers and
is released on process exit. Approval decisions are audited and consumed before
streaming. Refresh/restart can recover an awaiting approval without replaying
completed roles. Interrupted stages can resume from saved outputs only when no
provider request or tool has an unknown outcome; unknown work fails closed rather
than replaying a potentially side-effecting operation.
Mammoth Mind saves paused recursive exchanges to chat/thread history. Opening
that history reloads the authoritative run with GET only before restoring its
controls, so stale approval buttons do not survive a saved cancellation. History
recovery never approves a decision or spends model credits automatically.

All tools still pass through `ToolRegistry` with freshly resolved repository access.
No selected repository means no repository context. Tenant repositories remain
proposal-only. Owner isolated validation and local-branch application retain
their separate approval gates; RecursiveMAS never grants push/deploy access.
The uncertain-critique review is an additional gate permitting **synthesis only**,
not tool execution. Critic confidence is a routing signal, not truth probability.

The existing `mammoth.run.v1` envelope is preserved. Additive `recursive.updated`
events carry stage, pass, limits and reported usage; public snapshots omit private
role caches and checkpoints. Only the reviewed synthesis emits final completion.
The UI shows concise stage summaries, not private chain-of-thought. A successful
critique does not independently verify factual claims or application quality.
