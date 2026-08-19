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

## Source-aware quality rules
- Keep runtime payloads structured when an agent is meant to return a real programmatic result.
- Do not let coding/documentation flows invent content from a placeholder target like `unknown`.
- Prefer explicit `mode`, `audience`, and `constraints` for brand-voice rewrites and tutorial output.
- Validate outputs against expected shape before calling a task complete.

## ATLAS FAB + package commercialization rules
- Treat `src/mammoth_os/sdk.py` and `src/mammoth_os/__init__.py` as the public SDK contract for embedders.
- Keep `AtlasFAB` additive: never break existing `ATLASSession` flows while exposing higher-level embed APIs.
- Prefer explicit runtime/state surfaces (`runtime_state`, contract versions, provider labels) so integrators can monitor availability and fallback behavior.
- Keep package metadata (`pyproject.toml`) production-oriented: clear dependencies, public description, and accurate versioning.
- For monetization features, design for future tenant keys and usage metering without hard-coding a single operator identity.

## Production tenant/auth rules
- Treat `.mammoth\supabase_tenant_auth.sql` as the baseline blueprint for tenant ownership, membership, billing usage, and audit trails.
- Do not duplicate existing `atlas` or `mammoth` product tables when adding auth; wrap them with tenant/account ownership and RLS instead.
- Keep public routes and public-schema content separate from tenant-scoped operational data.
- Anonymous visitors should never receive private dashboard, usage, or operator-state payloads.
- Owner/admin controls must be enforced by backend tenant membership checks, not UI-only hiding.
