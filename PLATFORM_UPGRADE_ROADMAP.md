# MammothOS platform reliability and upgrade roadmap

Audit date: 2026-10-05  
Source baseline: `5d7e772` on `main`  
Status: planning only; the fixes below have not been implemented.

## Purpose and boundaries

This is the execution backlog for agents improving MammothOS, Mammoth Mind,
the tutor SDK, and the Mammoth Paths workspace SDK. Prioritize trustworthy
behavior over adding more features.

This is a source-code audit, not a certification of production behavior or a
security penetration test. Findings distinguish confirmed source behavior from
follow-up investigation. Check the current code before starting each item.
Do not treat search keywords, missing route-local auth calls, or an absent
frontend caller as proof of a defect.

### Non-negotiable rules

- Preserve long-form research, document exports, tutor flows, and both SDKs.
- No selected repository means no repository context.
- The platform repository and host remain owner/admin-only.
- Tenant repository changes remain branch-and-patch proposals, never direct
  host writes or pushes on the user's behalf.
- Never send filesystem roots from an untrusted client as an access grant.
- Reasoning traces are short model-written summaries, not hidden reasoning.
- No success-shaped fallbacks, fabricated metrics, or provider errors embedded
  inside generated documents.
- Keep existing contracts and AtlasFAB aliases backward compatible.
- Preserve calm visual design, mobile usability, and collapsible traces.
- Respect provider licenses. Commercial Open-Meteo use requires the appropriate
  subscription/key; retain attribution.
- This roadmap does not establish patent clearance. Use standard documented
  interfaces and independently implemented behavior; obtain qualified legal
  review if a specific licensing or patent concern arises.

## What already works: do not rebuild it

- Coding on the Agent page already uses the repo-grounded agent loop, repository
  selection, read tools, patch proposals, approvals, cancellation, and traces.
- Brave/Tavily search and Open-Meteo weather adapters already exist.
- Feedback ratings already have intake, aggregation, and regression-case export.
  They are not an autonomous training or self-modification pipeline.
- Python and JavaScript Mammoth Paths clients already cover runs, approvals,
  repositories, notes, build logs, and the owner-only terminal.
- JavaScript Paths tests already run in CI.
- Route handlers live in `server_routes/`, loaded into `api_server` globals.
  Many apparent "missing routes" are present there.
- Production auth middleware and request-scoped Atlas state already exist.
  A route without `_require_auth_user` is not automatically public.

## Confirmed findings

| ID | Priority | Evidence | Gap / consequence |
| --- | --- | --- | --- |
| UI-01 | P0 | [FlashcardsPage.jsx](ui/mad-architecht-command-center/src/pages/FlashcardsPage.jsx), `SAMPLE_CARDS`, initial state and load handler | Demo cards remain when the server returns an empty deck or loading fails. An error is recorded, but the visible deck is still sample content. |
| DATA-01 | P0 | [api_server.py](api_server.py), `_read_json`, `_write_json` | Shared writer uses direct file replacement without an atomic write protocol; reader converts all exceptions into defaults, obscuring corruption and permission failures. |
| HEALTH-01 | P1 | [api_server.py](api_server.py), status mapping default and static module manifest; [governance_routes.py](server_routes/governance_routes.py), discovered-module statuses | Unknown statuses can become `ready`; some declarations advertise readiness without proving runtime availability. Audit downstream overrides before changing individual cards. |
| HEALTH-02 | P1 | [agent_registry.py](src/mammoth_os/agent_registry.py), `_auto_register_agents` | Filename discovery creates generic manifests and fresh heartbeat timestamps without importing or executing the agent. Discovery is not a health probe. |
| AGENT-01 | P1 | [main.py](main.py), `fallback_coding_agent`, `fallback_field_ops_agent`, `load_agents` | Legacy entrypoint substitutes echo stubs when registry loading fails. This is not evidence that the web agent loop uses those stubs. |
| AGENT-02 | P1 | [field_ops_agent.py](src/mammoth_os/agents/field_ops_agent.py), mission/checklist/completion construction | Every operational query gets navigation-oriented bearing and landmark fields, even when the request is a business rollout or unrelated mission. |
| TENANT-01 | P1 | [brand_voice_agent.py](src/mammoth_os/agents/brand_voice_agent.py), [field_ops_agent.py](src/mammoth_os/agents/field_ops_agent.py), [market_intel_agent.py](src/mammoth_os/agents/market_intel_agent.py), other specialist prompts | Shared prompts assume True XXII Supply / Boise. Appropriate for the owner's preset, but not a general tenant's default identity. |
| BILL-01 | P1 | [api_server.py](api_server.py), `_current_usage_snapshot_from_state`; [client.py](src/mammoth_os/paths/client.py), `usage_hook` documentation | Usage is aggregated from local `fab_usage_events`; Paths documents client-side metering pending server-side tenant metering. This is real local usage, not proof of fabricated billing, but it is not a complete authoritative all-surface ledger. |
| CI-01 | P1 | [ci.yml](.github/workflows/ci.yml) | Ruff and mypy commands use `|| true`, so those steps cannot block regressions. Sandbox test also permits failure. |
| SDK-01 | P2 | [client.py](src/mammoth_os/paths/client.py), `stream_run`; [client.js](packages/mammoth-paths/src/client.js), `streamRun` | Run clients need a parity check for newer `surface`, `task`, and `history` fields used by Agent Workspace. Do not assume the original method list guarantees newer payload support. |
| CLEAN-01 | P3 | [useGenerate.js](ui/mad-architecht-command-center/src/hooks/useGenerate.js), generated graph/palette components, old Notes pages | Placeholder and duplicate files remain. Prioritize only reachable behavior; unused scaffolding is not a live outage. |

## Follow-up candidates: validate before fixing

These were flagged in the UI/API sweep but require per-flow verification:

- Agent, Diagnostics, Health, Lessons, ATLAS, Build Log, and Log Sale have
  swallowed fetch failures. Establish which are essential vs optional and
  whether another component already surfaces the error.
- PersonalHealth starts with numeric defaults. Verify that they cannot be
  mistaken for saved observations after loading fails.
- Account preferences and onboarding use browser-local storage. Separate
  intentional device preferences from data requiring cross-device persistence.
- Artifact Library has local state plus API operations. Verify cache
  reconciliation and user switching rather than deleting the cache blindly.
- MCP configs use runtime package resolution, including `@latest`; inspect
  actual bridge execution, headless settings, availability probes, and installed
  executables before declaring a server broken.
- Audit/activity/feedback/deletion stores need read-modify-write concurrency
  tests and retention review, not just an atomic writer.
- Run histories and streamed threads need reconnect/replay, tab closing,
  server restart, and account switching coverage.

### Findings intentionally excluded

- Account, flashcard, feedback, and other endpoints reported as missing from
  `api_server.py` are not accepted as missing: search `server_routes/` too.
- Missing route-local auth is not accepted as an auth bypass: examine middleware,
  public-path policy, tenant scoping, and tests together.
- Empty repo context with a "No repository selected" notice is intended.
- Turning exceptions into explicit `run.failed` events is intended. Only
  incorrect terminal states or hidden diagnostics would be defects.
- No frontend caller does not make an API dead: SDKs and integrations may use it.
- Test fixtures, tutorial examples, validation of placeholder input, and
  intentionally labeled demos are not production stubs.

## Execution phases

### Phase 0: reliable inventory and regression baseline

**Dependencies:** none. **Size:** small to medium.

- [ ] BASE-01: inventory every routed page, agent capability, MCP server, SDK
  method, and backing endpoint. Record live/static/demo/disabled/owner-only status.
- [ ] BASE-02: add route-contract tests against the loaded FastAPI app, not text
  searches of one file; cover anonymous, tenant A/B, and owner roles.
- [ ] BASE-03: record baseline tests/builds and existing lint/type errors.

**Acceptance:** every sidebar page has an identified data owner and explicit
empty/error behavior; route inventory includes fragments; no new failures.

### Phase 1: honest output and explicit error states

**Dependencies:** Phase 0. **Size:** medium. Highest visible payoff.

- [ ] UI-01: initialize flashcards empty; show demo cards only via an explicitly
  labeled opt-in demo. Empty data must replace old cards and reset review state.
- [ ] UI-02: implement consistent loading/empty/error/stale states for essential
  API calls. Keep last-good data only with a visible stale label and retry action.
- [ ] UI-03: replace misleading zeros/default measurements with "not recorded"
  or "unavailable"; preserve legitimate observed zero values.
- [ ] AGENT-01: replace legacy stub fallback with a clear unavailable result and
  logged cause; preserve a separately labeled demonstration mode if needed.
- [ ] AGENT-02: make Field Ops output scenario-specific; navigation criteria
  appear only for navigation requests. Verify weather failure remains explicit
  without blocking unrelated operational planning.

**Acceptance:** empty deck, offline backend, malformed response, and provider
failure never display sample content or imply that work succeeded. Test loading
failure and retry on desktop and portrait mobile.

### Phase 2: durable state and evidence-based health

**Dependencies:** Phase 0; coordinate UI states with Phase 1. **Size:** medium to large.

- [ ] DATA-01: introduce a shared persistence abstraction with atomic writes and
  explicit corruption/permission reporting. A missing file may still mean a
  new empty store; other failures must not silently reset data.
- [ ] DATA-02: serialize complete read-modify-write transactions. Define the
  deployment's multi-process behavior; a thread lock alone is not sufficient
  for multiple workers. Add migration/backup and interrupted-write coverage.
- [ ] HEALTH-01: separate `discovered`, `configured`, `available`, and observed
  health; add last-check time and failure reason. Unknown is never ready.
- [ ] HEALTH-02: align runtime router, canonical registry, `/api/modules`, and
  `/api/agents`; retain compatibility adapters instead of deleting registries
  without tracing their consumers.
- [ ] RUN-01: verify SSE replay/cancellation/reconnect and bounded retention;
  make terminal status and timestamps authoritative.

**Acceptance:** concurrent updates survive without lost entries; interrupted
writes preserve last-good data; unplugged providers and failed imports show
degraded status consistently in API, UI, and SDK.

### Phase 3: tenant-aware agents and authoritative usage

**Dependencies:** Phases 1 and 2. **Size:** large; split into small reviewed increments.

- [ ] TENANT-01: move owner identity/region/brand into scoped configuration;
  retain True XXII as the owner's preset. Use neutral behavior when absent.
- [ ] BILL-01: establish a server-side usage event contract covering tutor,
  agent runs, research, search, and other paid calls. Separate estimates from
  provider-reported usage, retries, cache hits, and billable units.
- [ ] BILL-02: persist idempotent tenant/account usage events; reconcile totals,
  enforce plan gates, and label unavailable provider costs honestly.
- [ ] BILL-03: review the tenant SQL blueprint against implemented membership,
  entitlement, audit, and deletion flows before migrating stores. Preserve
  product tables and enforce ownership in the backend.
- [ ] STATE-01: synchronize account-level preferences and onboarding where
  required; leave intentional device settings local and document the boundary.

**Acceptance:** two tenants have independent identities and ledgers; owner
defaults never leak into another tenant's content; retried requests do not
double bill; anonymous users receive no private usage data.

### Phase 4: SDK contract coverage and enforceable release gates

**Dependencies:** Phase 0; integrate new contracts after Phases 2/3. **Size:** medium.

- [ ] SDK-01: keep Python/JS run payloads in parity, including Agent Workspace
  context; test additive fields, approvals, cancellation, auth refresh, and errors.
- [ ] SDK-02: verify SDK behavior against server contract fixtures and packaged
  installs, not only independently mocked client responses.
- [ ] CI-01: establish a lint/type baseline and fail on newly introduced
  violations; expand enforcement incrementally instead of turning on an
  unmanageable legacy-wide gate without triage.
- [ ] CI-02: add explicit frontend build and targeted interaction tests to PR
  validation; retain existing JavaScript SDK tests and release guardrails.
- [ ] CI-03: classify sandbox failures as release-blocking vs environment
  diagnostics; pin MCP package versions and document verified launch commands.

**Acceptance:** breaking SDK payloads or UI builds fail before release; no new
dependencies in the stdlib-only Python Paths / zero-dependency JS clients.

### Phase 5: source-aware improvement, cleanup, and documentation

**Dependencies:** reliable state, usage, and release gates. **Size:** medium, ongoing.

- [ ] EVAL-01: turn existing feedback regression exports into a repeatable
  evaluation workflow with reviewed fixtures, baseline/candidate comparison,
  and explicit human approval. Do not claim ratings retrain the model.
- [ ] EVAL-02: preserve research provenance, reasoning separation, relevant
  sources, long-form completeness, and authenticated document downloads in tests.
- [ ] CLEAN-01: trace imports/routes before removing old Notes pages and
  generated scaffolding; label intentional examples instead of deleting them.
- [ ] DOC-01: reconcile old roadmaps/manuals with actual shipped behavior; keep
  this backlog, README, AGENTS, and the in-app Manual aligned after each phase.

**Acceptance:** evaluations distinguish quality regressions from formatting
changes; exports remain authenticated and usable; no reachable dead controls.

## Agent execution protocol

1. Pick a single unchecked ID and inspect its current source and consumers.
2. Confirm the finding and record the baseline failure before editing.
3. Implement the smallest complete vertical slice, preserving contracts and
   access boundaries. Add focused tests including failure behavior.
4. Run targeted tests/builds. Documentation-only tasks need no code test run.
5. Record changed files, exact validation results, remaining limitations, and
   commit reference under the completion log; only then check the item off.
6. Never mark a phase complete from green CI alone: verify its acceptance
   criteria. Do not fabricate runtime health or progress.
7. Publish only through the operator's authorized workflow. Reading this
   roadmap grants no repo, terminal, production, or push permissions.

## Recommended first delivery batch

BASE-01/02, then UI-01/02/03 and AGENT-02, then DATA-01/02 and HEALTH-01/02.
Avoid starting with new agents, autonomous self-improvement, or mass deletion.
These would build on the current reliability gaps rather than close them.

## Completion log

- 2026-10-05: source audit consolidated; preliminary false-positive route/auth
  claims excluded; roadmap created. No runtime fixes implemented by this document.
