# MammothOS platform reliability and upgrade roadmap

Audit date: 2026-10-05

Source baseline: `5d7e772` on `main`

Status: original audit backlog plus the run-reliability delivery below.
Original audit findings are historical; checked reliability items are separate
from unchecked audit phases.

## Purpose and boundaries

### Reprioritized delivery plan (2026-11-03)

Recent merged passes:

- #16: workspace SDK run/context parity and installed wheel/npm contract tests.
- #17: fail-closed, four-suite Chromium interaction gate.
- #18: bounded Python Paths correctness lint and strict typing gates.
- #19: Python/JS JSON container guards and removal of the dynamic-return exemption.
- #20: strict SSE decoding, run identity/sequence guards and saved recovery checks.
- #21: repository-aware frontend readiness and explicit approval-bound deletion.
- #22: Docker-required legacy smoke, structured execution evidence and read-only
  diagnostics without host fallback or automatic policy PRs.
- #23: retained final overview samples, private document paging across both SDKs
  and UI, recursive role allowances, budget diagnostics and unverified draft
  retention.
- #24: detailed feature handbook, source-grounded Guide responses and per-request
  docs fingerprints/caller-filtered capability snapshots.

These are merged source changes, not proof of deployment or complete production
acceptance. The latest release had nine successful checks and 182 fixture-backed
Chromium scenarios. The real Docker smoke still reported `not_verified` after
namespace/mount startup failure; owner/reviewed-image isolation remains open.

#### Active workstream: document completeness and recursive review reliability

User reports: uploaded files still seem only about two-thirds readable; two
recursive reviews stopped at the token cap. Reproduce against saved receipts and
representative fixtures before assigning either report a single root cause.
Do not silently raise limits, weaken safety, or equate upload success with review.

- [ ] DOC-CONTEXT-01: trace source extraction, indexing, retrieval and actual
  model-visible coverage separately. Current extraction is bounded to 2,000,000
  characters/2,000 units; scans need OCR, which is not enabled. Initial chat
  context includes up to three selected chunks per file and four files. Existing
  Agent document search/paginated reads can inspect more indexed text, but
  availability is not proof that all sections were read.
  Add beginning/middle/end sentinels, late appendices, tables and multi-file
  fixtures; identify the exact stage and reason for omissions.
- [ ] DOC-CONTEXT-02: expose extracted/indexed/selected/reviewed coverage and
  omissions with file/section provenance across backend, chat/workspace and both
  SDKs. Offer an explicit bounded whole-document review using existing paginated
  reads, with resumable section coverage and no false full-review claim.
  Count unique source coverage rather than overlapping chunk bytes. Preserve
  account isolation, deletion, download access and prompt-injection boundaries.
- [ ] REVIEW-BUDGET-01 (RUN-07/10): inspect the two failed run receipts, including
  configured cap, role, actual provider usage, prompt estimate, reservation,
  output allowance and stop reason. Current recursive reservation subtracts
  UTF-8 prompt bytes from a token limit, while charging actual reported tokens
  after each response; this can reserve too conservatively, but is not yet a
  proven explanation for these runs. Use provider-aware counting or explicitly
  labeled conservative estimates; keep estimated/reserved/actual usage distinct.
  Test near-cap boundaries, multilingual text and missing provider usage.
- [ ] REVIEW-BUDGET-02 (RUN-07/10/11): allocate bounded planner/executor/critic/
  synthesis budgets before calls, retain evidence rather than repeating entire
  transcripts, and reserve room for final synthesis. Checkpoint completed work;
  show remaining work and precise cap cause on partial results. Safe explicit
  continuation must not rerun paid completed stages, duplicate tools, or bypass
  approvals. Never present an unfinished review as passed. Preserve long-form
  deliverables and source citations when compacting context.
- [ ] CONTEXT-EVAL-01 (RUN-09): add deterministic adversarial/coverage fixtures
  first, then a small explicitly approved paid evaluation if needed. Measure
  source coverage, false completion, successful review completion, call count,
  input/output/reasoning usage where available, and cost per successful task only
  when authoritative prices/usage exist. Keep failures and unavailable data.

Acceptance: every required sentinel in fully extractable fixtures is recoverable;
an exhaustive review either records every indexed section or clearly remains
partial. Known unextractable content is disclosed. Recursive boundary tests
respect the configured budget without false early completion or duplicate
execution; final output or a resumable partial checkpoint survives a cap stop.
Build, behavior verification and untested production boundaries remain separate.

#### First connected delivery and remaining boundaries

Implemented bounded first batch (not closure of the items above):

- Regression confirmed that chat selected four distributed sections then dropped
  the fourth, losing the final section. Selection now requests three directly.
  Context includes selected/indexed counts.
- Both existing content endpoints, file-library previews and Paths clients offer
  bounded sequential paging with selection metadata; installed-client fixtures
  enumerate all locally indexed source chunks and deny cross-user/scope/anonymous
  reads. Counts describe indexed sections, never original-source character
  coverage or AI review completion. Extraction/OCR limits remain unchanged.
- Recursive planner/critic outputs are capped at 2,048 tokens; existing executor/
  synthesis allowances and overall ceilings stay intact, with bounded synthesis
  headroom. Replanning avoids duplicating the prior draft; the executor retains
  it for revision. Role contexts no longer blindly clip serialized source tails.
  Public budgets distinguish byte-based conservative admission from actual
  reported usage, and failures retain the latest completed executor draft under
  an unverified label.
- Deterministic fixtures cover long source tails, Unicode, replanning, cap-stop
  draft durability, paging/failure/stale-response behavior and SDK parity.
  The two hosted failure receipts/user files were not accessed. Exact provider
  tokenization, automatic exhaustive-review orchestration, resumable coverage
  tracking and explicit budget extension remained open at that release. No paid benchmark or
  quantified credit-saving claim is made.

#### Order after the context/review batch

Delivered in merged #25:

- Admission now runs at each leaf provider attempt, including fallback and
  conversation-background expansion. Known official OpenAI models use local
  tokenizer text counts plus byte allowances for the shared request envelope/
  schema and overhead. Unknown models/endpoints and unavailable tokenizer assets
  use explicit byte fallback. Estimates/reservations remain distinct from actual
  reported usage. This is not exact provider-side chat tokenization or a billing
  guarantee; the original overall recursive caps are unchanged.
- Explicit read-only indexed review persists source-hashed assessments and
  literal quote provenance per section in the private document library. Creation/
  recovery/listing/deletion run no models. Each confirmed advance assesses up to
  three sections within 180 seconds and a lifetime 64,000 reported-token ceiling.
  Reloaded batches resume only known unassessed indices; concurrent work,
  unknown provider outcomes, changed/deleted sources and cap stops block replay.
  Completion requires every indexed section, while extraction warnings remain.
  SDK parity and file-preview controls expose these same limits. Deleting the
  source purges the review; an explicit delete frees the 20-review private quota.
- This is not automatic recursive exhaustive critique or combined cross-section
  synthesis. Unknown active work after a process restart remains blocked, not
  automatically retried. Exact original-source character coverage and
  authoritative charges from failed provider attempts are not invented.

Delivered in merged #26:

- Explicit synthesis after complete indexed assessment, up to three model units
  per confirmed batch, groups of at most eight saved assessments/intermediate
  summaries. Durable nodes preserve input traversal and source-index citation
  lineage without silent truncation. Final traversal must reach every indexed
  assessment. Quotes validate source links, not entailment. Summaries are lossy,
  not full-source rereads or factual verification.
- Synthesis shares review usage and the 180-second batch ceiling. Reopening/
  reloading is model-free; completed units never replay. Unknown provider outcomes,
  invalid responses and source changes remain blocked. Crash-active work is not
  automatically retried.
- Audited, compare-and-set budget extensions deliberately permit a larger review
  total, at most 128,000 reported tokens. Default remains 64,000, usage is never
  reset, and confirmation does not run models. Only known cap stops with no
  uncertain/invalid call may resume. Each subsequent paid batch needs separate
  confirmation. Backend, both Paths SDKs, file-preview controls and Guide/docs
  expose the same behavior; ordinary recursive limits remain unchanged.

Remaining context work:

1. Evaluate supported model/envelope admission against real reported usage; do
   not substitute a chars-per-token guess for unsupported provider tokenization.
2. Measure cross-section retention and source entailment with reviewed evaluation
   sets before claiming semantic completeness; indexed input traversal alone
   cannot establish it or make an extraction-limited original file complete.
3. Use authorized saved receipts to reproduce the two hosted failures when
   available; they remain uninspected, not implicitly fixed by local fixtures.

Guide/explanation companion slice: a public feature handbook, query-selected
source excerpts passed into Guide responses, and per-request documentation
fingerprints/caller-filtered capability snapshots. Snapshots distinguish configured
availability from verified health; no private operator diagnostics or autonomous
platform checkout/sync. Deployment remains necessary. This does not close the
tokenization, exhaustive-review or container-evidence work.

Subsequent infrastructure/platform gates:

Merged container evidence slice (#27; all nine checks passed):

- Separate strict operator acceptance command runs bundled trusted Python
  fixtures through the actual owner executor. Observes non-root test-process
  identity, capabilities/seccomp/no-new-privileges, mounts/storage/network
  interfaces and resource limits, plus negative-test rejection, timeout and
  named-container removal. No image pulls, host fallback, policy changes,
  production enablement, user code or tenant access.
- Manual workflow has a digest-only operator input and separate explicit image
  pull option (default off); strict failed/not_verified exits and receipt upload.
  Adding a workflow does not constitute a hosted run or production acceptance.
- Local fixture acceptance passed on 2026-11-03 for the existing Python digest
  `db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93`
  and Docker Engine 29.6.2. This is a bounded host/image/Python-profile observation,
  not hostile-code, frontend, repository-dependency or deployed-infrastructure
  acceptance. The hosted legacy diagnostic still lacks runtime evidence.
- Missing-runtime receipts now classify namespace/mount startup separately from
  daemon/image/timeout failures. Seccomp diagnostics no longer guess relaxations
  from startup/generic permission errors; only recognized named denials with a
  bounded runtime receipt are manual review candidates. No automatic policy edits.

Connected SDK/recovery slice (bounded local checks; final release evidence in PR):

- Python/zero-dependency JavaScript review methods validate nested saved evidence:
  identity/file/scope, source hashes and sequential coverage, safe-integer usage,
  inflight markers, compare-and-set budget history and hierarchical synthesis
  traversal/citation lineage. Preserve additive fields and legitimate active,
  blocked and over-ceiling states; malformed receipts never authorize replay.
- The preview reuses the JavaScript guard, retains its last valid record and
  requires a model-free reload after failed/malformed evidence. Invalid initial
  lists expose a free reload instead of allowing replacement creation.
- A common malformed-state matrix checks both clients. Real hierarchical service
  checkpoints exercise the guard at writes. Installed-client loopback tests use
  real socket timeouts and killed/restarted SQLite workers with offline models:
  unknown assessment work stays blocked, GET never spends, explicit continuation
  of a known partial checkpoint starts at the next section.
- Bounded evidence only: not production proxy/provider behavior, synthesis wire
  disconnects, general agent SSE restart or full nested SDK certification.
  No new provider spend, dependencies, permissions or automatic retries.

Remaining infrastructure/platform gates:

Desktop handoff refinement:

- Applied coding result/pilot cards can explicitly reread the caller-authorized
  execution, download its recorded patch and launch a recorded GitHub repository
  in Desktop. No launch occurs on rendering, recovery or approval.
- Branch-specific launching requires the user's local/published-branch
  acknowledgment, not a fabricated check of their computer. Missing/ambiguous
  GitHub identity never falls back to the platform repository.
- Backend-only unpublished branches still need operator-assisted transfer.
  Automatic remote-to-local branch transport/local helper distribution is not
  implemented; patch download is not branch import. Push, PR and merge remain
  explicit user operations. Browser protocol-handler links are covered by
  fixture tests, not certified against an installed Desktop app.

1. Establish reviewed owner-container infrastructure evidence and compatible
   per-repository validators (CI-03); a green diagnostics job is insufficient.
2. Expand nested SDK domains and deployed/general agent SSE disconnect/restart
   coverage (SDK-01/02, RUN-11), beyond the bounded saved-review work above.
3. Address shared persistence transactions and observed provider/agent health
   (DATA-01/02, HEALTH-01/02); do not infer availability from discovery alone.
4. Establish authoritative tenant usage/spend controls and measured escalation
   (BILL-01/02, RUN-09/10), then broaden optional product features.
   Existing personal-health consent/design prerequisites remain unchanged.

Credit-efficient delivery here: group related backend/SDK/UI/docs/tests into
substantial coherent passes; inspect once, reuse evidence and run targeted tests
before the final full gate. Avoid redundant model reviews and paid benchmarks
without a concrete question and spend approval. Do not trade away coverage,
privacy or correctness for fewer calls. No percentage saving is claimed for
Copilot credits; this repository cannot authoritatively measure that balance.

### Personal Health direction (requested 2026-11-02; not implemented)

The Health destination is a private personal-health dashboard with an AI
assistant, not just an owner/operator health console. Keep existing owner-only
tools restricted until a separate user-scoped surface is implemented and tested.

- [ ] PERSONAL-HEALTH-01: design explicit consent, per-user storage and access,
  export/deletion/retention, minimal necessary collection, and clear provenance.
  Do not reuse operator defaults or expose another account's records.
- [ ] PERSONAL-HEALTH-02: implement a private dashboard with manual entries and
  a clearly labeled **Personal Health Assistant** for educational explanations,
  organizing records/questions, and descriptive trends. Missing data stays empty.
  Do not imply a licensed physician assistant/associate or clinician, diagnose,
  prescribe, promise clinical accuracy, or offer emergency monitoring.
- [ ] PERSONAL-HEALTH-03: feasibility/privacy/platform review for Apple
  Health/Watch and Android Health Connect/Wear OS. Phone-native permission and
  background-sync requirements need review before choosing native wrappers.
  No device connector or provider is selected or enabled yet.
- [ ] PERSONAL-HEALTH-04: opt-in, read-only steps/heart-rate/activity imports,
  device/timezone/unit attribution, duplicate handling, gaps and sync failures.
  Never invent continuous readings or medical conclusions from wearable data.
- [ ] PERSONAL-HEALTH-05: verify cross-account isolation, revocation/deletion,
  safe model context, accessible mobile delivery and appropriate health-data
  regulatory/security review before production collection or integrations.

The first proposed milestone is consent/privacy plus manual dashboard and
educational assistance; device integrations follow. This sequencing is a
conservative implementation assumption, not user approval of a health-data
provider or unresolved retention/clinical decisions. Complete the active ATLAS
learning upgrades first; obtain those decisions before collecting health data.

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
  - Implemented bounded SDK-01/02 run-contract coverage: matching surface, task,
    history and attachment fields; unchanged defaults; approval/resume;
    cancellation/recovery; per-request token changes; explicit backend errors.
    Installed wheel and npm-tarball fixtures exercise loaded routes with actual
    runner/store/ownership checks and scripted auth, document context and models.
    CI requires Node/npm and checks public run-option types. The bridge buffers
    SSE: live proxy timing/disconnects, paid providers, real attachment retrieval,
    and wider endpoint/release coverage remain open. These items stay unchecked
    until their broader acceptance is met.
  - Three follow-up slices harden SSE decoding, live event envelopes/identity/
    sequence, and saved recovery metadata in both clients and the app's shared
    run-state path. Invalid data fails explicitly before callbacks; readers close/
    cancel on failure; full snapshots require complete envelopes/history.
    Unknown event types/extensions and valid resumed sequences remain supported.
    Regression tests cover malformed data, cleanup, metadata, read-only recovery
    and visible app failure without false completion/retry. These are bounded
    checks, not full nested schemas or production proxy/disconnect validation.
- [ ] CI-01: establish a lint/type baseline and fail on newly introduced
  violations; expand enforcement incrementally instead of turning on an
  unmanageable legacy-wide gate without triage.
  - Added fail-closed `paths-sdk-quality` with pinned Ruff/mypy and a clean
    baseline for the Python Paths package. Correctness lint and bounded strict
    typing run without success-forcing fallbacks; nine actual-tool probes
    verify failing regressions and the clean baseline. External import bodies
    are skipped. A follow-up added Python/JS JSON container guards and removed
    the client's prior `no-any-return` exemption. Invalid JSON, empty success
    bodies, wrong containers and invalid run envelopes fail explicitly; valid
    empty lists/extensions survive. Full nested domain schemas and broader
    legacy baseline/enforcement remain open. Legacy
    diagnostics are labeled non-blocking; branch rules must require the new
    job separately.
- [ ] CI-02: add explicit frontend build and targeted interaction tests to PR
  validation; retain existing JavaScript SDK tests and release guardrails.
  - Added an independent `ui-interactions` job alongside build/type checks for
    every main-targeting PR and main push, without path filters that omit
    test-only edits. All four fixture-backed Chromium workspace suites are
    mandatory; skips, focused tests, missing suites, retries and expected
    failures cannot yield behavior verification. JSON/HTML/failure traces are
    retained for seven days. Unit and actual-Playwright CLI probes verify
    fail-closed exit codes. Branch protection must separately require this
    check; production auth/providers/proxies and other browsers remain outside
    this bounded gate.
- [ ] CI-03: classify sandbox failures as release-blocking vs environment
  diagnostics; pin MCP package versions and document verified launch commands.
  - Owner readiness now separates runtime tools from selected-repository frontend
    compatibility. Locked ui_* profiles remain MammothOS-workspace-specific;
    incompatible base/candidate manifests are rejected before freezing approval,
    with reasons exposed through API, tools and UI. Explicit delete:true proposals
    retain preview, isolated validation and separate branch-application approval.
    Arbitrary Next/Vite app images, reviewed per-repository validators and wider
    sandbox/environment classification remain open; this is not field-guide
    build validation or a generic execution rollout.
  - Legacy sandbox smoke now has explicit Docker-required/no-host-fallback
    execution, structured verified/failed/not_verified receipts, actual CLI exit
    regression tests and an honestly named sandbox-diagnostics job. Infrastructure
    evidence may remain not_verified in diagnostic mode; actual smoke/hardening
    failures block that job. Runtime logs and review-only tuner artifacts are
    retained; automatic suggested-policy PR creation is removed. This does not
    establish owner-image, non-root test-process or production isolation
    acceptance. Generic reviewed validators and MCP pinning remain open.

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

## Mammoth Mind run reliability (2026-10-06)

The reported "cut off" message was also used for malformed JSON/DSML. The
original runtime could mark that apology completed, used formatting retries as
task steps, and discarded provider finish reason/usage. These are confirmed
source findings, not identification of a particular production run's cause.

### Delivery checklist

- [x] RUN-01: preserve cloud/local completion metadata additively; keep
  `generate()` returning text. Report missing metadata rather than inventing it.
- [x] RUN-02: validate decision types/exclusivity; use supported JSON mode,
  explicit output allowances, and one bounded repair that does not spend a task
  step. Never execute a response reported as length-limited.
- [x] RUN-03: use failed/partial states for invalid/offline/budget-limited work;
  keep completion reasons distinct and expose calm, collapsed diagnostics.
- [x] RUN-04: owner-only explicit continuation from saved transcript, with
  refreshed repository access, approval checks, no duplicate chat exchange, and
  at most two additional eight-step segments. Wire UI and both SDKs.
- [x] RUN-05: regression coverage for real length cutoff versus malformed
  protocol, disk reload, bounded recovery, continuation race/ownership/access,
  approval/cancel preservation, SDK parity, and mobile recovery UX.

Validation: 167 focused backend/SDK/adapter/learning/sandbox tests, 12 JS SDK
tests, 16 workspace browser scenarios, focused Python lint and UI production
build. SDKs also reject streams ending without a terminal event rather than
returning a misleading running result. No paid model calls were made. These
tests use fixtures; production success-rate/latency/cost targets remain RUN-09.

### Follow-up delivery: schema-constrained decisions

RUN-06 implements the schema-constrained alternative, not provider-native
function/tool-call execution. Recognized official OpenAI GPT-4o/4.1 models use a
strict decision envelope listing the current user's authorized tool names.
Open-ended tool arguments are encoded as JSON text and validated against the
registry's original schema before approval or execution. Malformed strict
output never becomes a prose fallback. Final prose remains unconstrained.

DeepSeek/Ollama/custom adapters retain their existing validated compatibility
formats; the actual protocol travels through provider fallback in completion
metadata and is visible in diagnostics. No model defaults or paid calls change.
Adapter config `structured_decisions=False` explicitly selects the old JSON
mode on eligible OpenAI models; schema errors are explicit rather than silently
downgraded. Native tool-call handling on additional providers can be added later
with tested capabilities; it is not claimed by this slice.

Validation: 169 targeted backend/adapter/approval/sandbox/tutor/Paths tests,
two browser checks for protocol diagnostics and same-message continuation,
focused Python lint, and the UI production build passed. Coverage includes
invalid action combinations, malformed/duplicate/non-finite argument JSON,
hidden tools, registry-schema failures before approval, output limits,
explicit schema API errors, and fallback in both strict/compatibility
directions. These are fixture-based contract checks, not paid-model benchmarks.

### Remaining slices

- [x] RUN-06: native provider tool calls / schema-constrained decisions, with
  adapter capability negotiation and tested compatibility fallbacks. JSON mode
  alone does not enforce the decision schema.
- [ ] RUN-07: token-aware context budgets and checkpointed subtasks; preserve
  source provenance and long-form deliverables, not blind character clipping.
- [ ] RUN-08: deliverable-specific completion checks backed by actual evidence;
  never mark plan steps done solely because the model asserted completion.
- [ ] RUN-09: representative opt-in model evaluation: end-to-end task success,
  protocol failure rate, continuation success, false completion, p95 latency,
  total cost per successful task, and tenant/access regressions. Establish a
  measured baseline before setting targets or claiming parity.
- [ ] RUN-10: spend/time limits and selective quality/model escalation. Keep
  existing provider defaults and outage fallback until measured changes pass.
- [ ] RUN-11: transport disconnect/reconnect and restart recovery; explicit
  continuation is not durable background execution or automatic SSE reconnect.

### Current reliability baseline and next delivery slices (2026-11-01)

- Shipped through `5f225a2`: small committed-source edits, goal/evidence-derived
  completion, isolated owner validation and separately approved local-branch
  application; receipt-driven approval transitions/completion, bounded failure
  excerpts and output repair; nullable unassessed reply confidence.
- RUN-08 has owner coding evidence coverage, not universal deliverable-specific
  verification. It remains open for other outputs.
- RUN-09 has an opt-in real-loop measurement harness. Latest pre-recovery
  OpenAI smoke: 2/3 fixed Python tasks succeeded, below the minimum 20 samples
  and 90% target. Failed validation recovery remains weak. Earlier failed
  measurements are retained; this is not proof of hosted DeepSeek reliability.
- RUN-11 first slice: full saved snapshot recovery in Python/JS, shared
  idempotent event replay and read-only Run Review navigation/export. Saved
  cancellation state overrides historical approval events. Account changes
  clear visible evidence. GET recovery never retries execution or approvals.
  Automatic reconnect, durable background jobs and restart reconciliation
  beyond existing backend behavior remain open.

Current next order is the document/recursive context batch above (RUN-07/10),
followed by reviewed isolated execution and the remaining SDK/state/usage work.
Continue preserving failed-validation repair with fresh frozen jobs and both
approvals. Representative provider-specific RUN-09 measurements must use reported
usage (never invented prices). Tenant paid execution
requires stronger isolation, authoritative metering and representative evidence;
it is not enabled by these SDK/UI additions. No new setting can grant repository,
host, tool or approval privileges.

The failed-validation recovery slice now retains bounded failure excerpts in
saved progress and reserves managed run/apply transitions for fresh receipts,
not model-guessed or consumed execution identities. Scripted failed-then-fixed
coverage verifies new job/digest creation, a second validation approval and
separate application approval, with the original checkout unchanged. Actual
model repair competence remains unproven; the prior 2/3 measurement is not a
measurement of this candidate. No production deployment is implied by this log.

### Coding routing and discovery correction (2026-11-02 UTC)

- Coding-agent generation/advice/refactoring and run goals proposal/validated/
  applied now explicitly request the coding workload. The default coding order
  is OpenAI → DeepSeek → Ollama → local; the operator can independently prefer
  DeepSeek with `MAMMOTH_CODING_LLM_ADAPTER=deepseek`. General/tutor defaults,
  explicit per-call adapters and process-wide offline settings are preserved.
- `repo_search` accepts an exact relative file/directory `path`, enforced by the
  same repository policy. A discovery checkpoint temporarily removes additional
  search/list/readiness calls after two discovery calls with source matches.
  The existing task-step budget and both execution approvals are unchanged.
- Proposed-code smoke, same three fixed Python fixtures, one attempt per
  provider: DeepSeek 3/3 (11 calls, 37,253 reported tokens, p95 23.937s);
  OpenAI gpt-4o-mini 2/3 (15 calls, 69,507 tokens, p95 24.163s).
  OpenAI's unique-values candidate mishandled unhashable list elements and did
  not repair it. Both reports are retained:
  `workflow-da9c0d9f6744460ca630cc39` and
  `workflow-4d6dacc930014abe98a1b28c`.
- Six fixture runs are below the 20-sample threshold, not a causal A/B study or
  evidence for real UI edits. No prices are inferred from token counts. The
  conservative production preference remains DeepSeek while coding routes
  become explicit; OpenAI is not promoted as a measured improvement.
  Representative JSX/layout acceptance and model-driven failed-check repair
  remain open. No tenant execution, wider autonomy or bypassed approvals.

Local validation for these slices: 235 related Python tests passed (three
real-container tests not opted in), 18 zero-dependency JS SDK tests passed,
51 workspace browser tests passed, then 17 focused browser checks passed on
the final candidate. Python lint/type checks, JS declaration type checking and
the production UI build passed. No paid model calls were made for this delivery.
Publication is intentionally held while the operator's separate header-edit
workflow may still have HEAD-bound approvals in flight.

### Model shortlist: official published rates checked 2026-10-06

USD per million standard uncached input / output tokens, excluding tool fees,
cache writes, regional charges and reasoning overhead. These are evaluation
candidates, not routing changes or measured MammothOS performance.

| Model | Input / output | Evaluation role |
| --- | --- | --- |
| `gpt-4o-mini` (current OpenAI default) | $0.15 / $0.60 | Baseline; fix orchestration before attributing all failures to it |
| `gpt-6-luna` | $0.10 / $0.50 for short context | Budget-first candidate; API/reasoning compatibility work required, not a drop-in default swap |
| `gpt-4.1-mini` | $0.40 / $1.60 | Straightforward Chat Completions candidate for instruction following and tool use |
| `gpt-5-mini` | $0.25 / $2.00 | Selective reasoning escalation; account for reasoning tokens and parameter differences |
| `deepseek-flash` | $0.15 / $0.60 off-peak; $0.30 / $1.20 peak | Existing DeepSeek-compatible candidate; validate current model naming/behavior before replacing the `deepseek-chat` configuration |

Sources: [OpenAI pricing](https://developers.openai.com/api/docs/pricing),
[GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna),
[GPT-4.1 Mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini),
[GPT-5 Mini](https://developers.openai.com/api/docs/models/gpt-5-mini),
[DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing).
No paid evaluation calls or provider-default changes are part of this delivery.
