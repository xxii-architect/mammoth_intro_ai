# RecursiveMAS

RecursiveMAS is an additive, dependency-injected orchestration primitive. It does not register itself as a runtime agent or expose an API route; applications opt in by constructing `RecursiveMASRunner` with role callbacks.

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
