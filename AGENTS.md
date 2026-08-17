# AGENTS.md

Use this file when wiring or extending MammothOS agents.

## Working rules
- Treat `src/mammoth_os/agent_registry.py` as the canonical registry for agent manifests, capabilities, and health state.
- Treat `api_server.py` as the integration surface for UI and workflow wiring. Do not hard-code agent statuses in the frontend when the backend can provide them.
- Keep the plan/execute workflow and the agent registry aligned. If an agent is added to the runtime router, it should also appear in `/api/modules` and `/api/agents` with a meaningful status.
- Keep model routing safe: a cloud provider outage, missing credits, or expired key should degrade to the next available provider instead of crashing the worker.
- Prefer small, testable steps:
  1. Register or discover the agent.
  2. Expose it through the backend module/agent endpoints.
  3. Show it in the UI with a real status and workflow state.
  4. Add coverage for the route or the wiring step.

## Dual-provider runtime contract
- Use DeepSeek cloud for reasoning-heavy tutor / ATLAS flows when `DEEPSEEK_API_KEY` is present.
- Use OpenAI `gpt-4o-mini` for coding-heavy work when `OPENAI_API_KEY` is present.
- Keep the fallback chain additive and conservative: DeepSeek → OpenAI → Ollama → local echo.
- Treat provider errors like `insufficient_quota`, `429`, `401`, `403`, or billing-related responses as non-fatal; the runtime should retry on the next provider instead of throwing a dead-end error into the workflow.

## Delivery checklist for new agent wiring
- Add/confirm the agent class under `src/mammoth_os/agents/`.
- Ensure the agent is discoverable by `agent_registry` or the runtime registry.
- Expose the module through `/api/modules` with `status`, `workflow_ready`, and `workflow_stage`.
- Ensure the Modules page renders the backend state rather than a hard-coded fallback.
- Add or update tests for the backend contract.

## Recommended order of implementation
1. Registry + discovery
2. Backend API exposure
3. UI module card state
4. Workflow integration (plan/execute and task routing)
5. Observability (activity, health, approvals)
