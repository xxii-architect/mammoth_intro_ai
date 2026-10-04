# AGENTS.md

Use this file when wiring or extending MammothOS agents.

## Working rules
- Treat `src/mammoth_os/agent_registry.py` as the canonical registry for agent manifests, capabilities, and health state.
- Treat `api_server.py` as the integration surface for UI and workflow wiring. Do not hard-code agent statuses in the frontend when the backend can provide them.
- Keep `api_server.py` as the public FastAPI entrypoint. Route handlers live in `server_routes/` and are executed into `api_server`'s namespace, so existing imports, monkeypatches, and `uvicorn api_server:app` stay stable. Add new routes to the matching `server_routes/*_routes.py` file; keep shared helpers out of those files.
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
- Run model text through `mammoth_os.research_quality` (`strip_reasoning`, `trim_to_last_sentence`, `dedupe_items` / `dedupe_sections`, `filter_relevant_sources`) before it reaches a deliverable. Surface stripped reasoning as a separate trace field, never inline.
- Never splice conversation history or earlier step results into an agent's `prompt`. Pass them as `payload.history` / `payload.background`; `run_agent` scopes them through `llm_client.conversation_context` so only the model sees them.
- Never embed provider error strings in user-facing document content. Mark the unit `status: "failed"` and report it in a `quality` block.

## Mammoth Mind tutor SDK (formerly ATLAS FAB) + package commercialization rules
- Treat `src/mammoth_os/sdk.py` and `src/mammoth_os/__init__.py` as the public SDK contract for embedders.
- `MammothMind*` is the product name; `AtlasFAB*` names are permanent aliases of the same classes. Never rename wire values (`product_surface`, contract versions) as part of branding work.
- Keep `MammothMind` additive: never break existing `ATLASSession` flows while exposing higher-level embed APIs.
- Prefer explicit runtime/state surfaces (`runtime_state`, contract versions, provider labels) so integrators can monitor availability and fallback behavior.
- Keep package metadata (`pyproject.toml`) production-oriented: clear dependencies, public description, and accurate versioning.
- For monetization features, design for future tenant keys and usage metering without hard-coding a single operator identity.

## Tutor delivery rules
- Lesson manifests, stall telemetry, the comprehension gate, and chunk hygiene live in `src/mammoth_os/tutor_delivery.py` as pure functions; the API, `ATLASSession`, and the SDK all call them. Do not fork the logic.
- Manifests must be derived from real lesson/exercise data. Leave a field empty rather than generating filler.
- The gate must always offer an explicit override, and overrides must be audit-logged. SDK `next_lesson()` stays ungated unless `require_mastery=True`.
- Keep `lesson_telemetry` bounded (80 lessons) and clear it on learner reset.

## Mammoth Paths workspace SDK rules
- Python client: `src/mammoth_os/paths/` (stdlib only). JS client: `packages/mammoth-paths/` (zero dependencies). Keep both method sets and the `mammoth.paths.v1` contract in sync, and add tests on both sides.
- The app imports run-state logic from `@mammothos/paths` (Vite alias). Change the reducer there, not in the app.
- Clients never enforce access; the backend does. Workspace surfaces must stay user-scoped, and tier-gated surfaces use `_require_workspace_tier_api`.

## Repo access rules
- `src/mammoth_os/repo_access.py` is the single policy for repository context. Never resolve repo roots anywhere else.
- No repo requested means no repo context. Never add an implicit default repository.
- The platform repo is owner/admin-only. Non-admins only reach repos they connected, by source id or slug, never by filesystem path.
- Writes to user repos are proposal-only (branch + patch). Never push on a user's behalf.
- Agents that execute on or write to the backend host belong in `_PRIVILEGED_AGENT_IDS` in `api_server.py`.
- Shared agents that *can* touch the host get a server-forced sandbox flag in `run_agent`, not a caller-supplied one:
  - CodingAgent: `host_access`.
  - BrowserAgent: `allow_private_network` and `session_scope`.
  Any new agent that reads host files or fetches arbitrary URLs must follow the same pattern and add tests to `tests/test_agent_sandbox.py`.
- Pass user text to git after `-e` / `--` so it cannot be parsed as an option.

## Agent loop + tool rules
- `src/mammoth_os/agent_loop/` owns the Mammoth Mind run loop. Its event contract is `mammoth.run.v1`; add new event types without changing existing payload fields.
- Register tools through `ToolRegistry` with an honest tier: `read`, `network`, `write` (proposal-only), `exec` (approval required). Set `admin_only` / `needs_repo` instead of checking access inside the handler.
- Repo tools must go through `safe_repo_path` and receive the root from `_agent_tool_context` (which uses the repo access policy).
- Every `mcp/*.json` declares `access: admin|tenant`. Admin repo-category servers are only offered with platform scope. Never expose `git_push`.
- Reasoning events carry short model-written summaries only. Do not fabricate progress (for example, marking plan steps done that were never verified).

## Reply rating rules
- `src/mammoth_os/message_feedback.py` (`mammoth.feedback.v1`) is pure; the API owns storage and access. Replay lives in `mammoth_os.feedback_replay` (CLI only, no route).
- Rating excerpts come from the server's stored copy of the requester's own conversation. Never trust client-sent prompt or reply text.
- Ratings are user-scoped; aggregates and regression cases are admin-only.
- Ratings never change model, prompt, or routing behavior automatically. Any future consumer (calibration, critic) is an app-layer bridge, reviewed by a human, and never wired inside `src/mammoth_os/recursive/`.

## Production tenant/auth rules
- Treat `.mammoth\supabase_tenant_auth.sql` as the baseline blueprint for tenant ownership, membership, billing usage, and audit trails.
- Do not duplicate existing `atlas` or `mammoth` product tables when adding auth; wrap them with tenant/account ownership and RLS instead.
- Keep public routes and public-schema content separate from tenant-scoped operational data.
- Anonymous visitors should never receive private dashboard, usage, or operator-state payloads.
- Owner/admin controls must be enforced by backend tenant membership checks, not UI-only hiding.
