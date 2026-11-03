# MammothOS — Quick Operations Guide

This repo contains the ATLAS CLI, FastAPI backend, and the Mad Architecht Command Center UI.

The current agent-readable reliability backlog is
[Platform upgrade roadmap](PLATFORM_UPGRADE_ROADMAP.md). It separates confirmed
gaps from investigation candidates and defines phased acceptance criteria.

ATLAS now combines the lesson/practice renderer and tutor in a learning workspace.
Use **Lesson & practice**, **ATLAS Tutor**, or **Learning agents** without leaving
the page; the optional desktop tutor pane sits alongside the lesson. The old
`lessons` page key opens the same workspace. Advanced tutor tools remain available.
The signed-in `/api/atlas/agents` catalog exposes only education agents and no host
endpoints. Research supports existing long-form reports and authenticated DOCX
downloads; it remains supplemental to the active lesson.

### Workspace reliability and learning resources

Under Edit learning profile, **Learning privacy & costs** exports the current
account's saved learning JSON without model calls. Retained conversations,
lessons/exercises/cards, owned linked notes and confirmed recovery are also added
to Account's existing export. The additive `learner_adaptation` block includes
supported fields of the actual saved tenant/account-scoped model, or
`status: "not_saved"` with `model: null` if no private model exists. Export does
not create a default model or trim retained outcomes. This excludes unsaved tab edits, uploads, other
accounts, unverified legacy models, unknown learner extension fields, telemetry, Artifacts, Mammoth Mind
threads and external/provider/backups; it is not a full archive. Corrupt storage
fails explicitly, and exports over 8 MiB are rejected rather than shortened.
The panel explains count-based retention, unavailable price estimates, and
existing Notes/Account deletion controls. Resets are not privacy wipes and
deletion requests are not verified erasure. The panel now also offers optional
per-user daily ATLAS HTTP-request caps (uncapped by default), durable request
records, cooperative cancellation and reviewed, typed-confirmation deletion of
the active saved lesson session/recovery. Caps count admitted requests, not model
calls or dollars. Non-streaming Learning-panel agent requests now share this cap
through `POST /api/atlas/agents/run`; the backend enforces the six-agent catalog.
General workspace runs, repository/tool-loop runs, Mammoth Mind and SDK/local
calls remain outside its scope; this is not a platform-wide spending limit.
Cancellation reaches worker-thread model/fallback and response boundaries, can wait for already-sent
provider work, which may be billable; completed side effects are not undone.
Scoped deletion verifies canonical session/recovery removal and blocks stale
state saves, but retains notes, uploads, saved curricula, learner models/context,
telemetry, artifacts/plans, other accounts and external copies. Full LEARN-06
controls remain open. See [the manual](ATLAS_MANUAL.md#learning-export-privacy-and-spending).

Hosted learner adaptation now uses a hashed signed-in-user + learning-account
storage scope, including onboarding, mastery, confidence and memory graphs.
Unverified shared legacy models and cached adaptation are not imported; legacy
files remain untouched and existing lessons/conversations are preserved. Learners
can re-enter starting preferences; old mastery is not assigned to a tenant by
guessing. Corrupt/mismatched storage fails explicitly rather than silently
resetting. Writes are atomic, assessment/onboarding updates are serialized,
and evaluation probes use temporary storage. Saved private adaptation is now
exported. A separate reviewed deletion action now erases the active account's
private model and four adaptation caches; unverified legacy ownership recovery
remains open. Exporting is not erasure.

Learning privacy also offers **Review private adaptation deletion scope**.
The authenticated, no-store `/api/atlas/learner/privacy-review` endpoint reports
saved field names and record counts for the active account, or explicit
`not_saved`. It returns no lesson/model content and creates no default model.
This is a read-only review, not a deletion preview authorizing execution:
`deletion_available` is false for this read-only endpoint.
No cancellation, deletion or receipt occurs; legacy models, other accounts and
external copies remain outside scope. Counts are not mastery verification.

**Preview private adaptation deletion** is a separate authenticated action.
Review `/api/atlas/learner/deletion-preview`, then type
`DELETE PRIVATE ADAPTATION` for `DELETE /api/atlas/learner/adaptation`.
The preview binds to actual model/cache contents, owner, account and deletion
generation. The verified receipt covers only active storage: lessons,
conversations, drafts, notes, other accounts, legacy files and external copies
remain. Unknown model extension fields block deletion for review. A durable
pending/complete fence prevents older hosted model/state writes or approvals
from restoring erased adaptation; interrupted deletion blocks hydration/writes
until explicitly retried. Read-only review/export remain available and report
`pending_deletion`, not a receipt. Fresh activity may create new adaptation. Tracked
account requests receive cooperative cancellation, not a provider stop or refund.
Old unbound learner approvals must be requested again. Local SDK storage APIs
are unchanged; this is a hosted API safeguard, not a filesystem-wide erasure API.

ATLAS reading preferences (text size, spacing, focused mode) survive same-tab
page navigation and clear on signed-in account changes; they do not persist
through refresh. Headings, code and tables scale with text size. Read/Practice
move keyboard focus to their content, focused-mode controls retain reachable
focus, and wide code/table content is keyboard scrollable. These are targeted
accessibility improvements, not a compliance certification.

Workspace pages now retain full working state during in-app navigation, scoped
to the signed-in account: Agent conversations/results and team previews/follow-ups,
Mammoth Mind history/composer/repository/attachments, Notes drafts and Build Log
form/filter. Inactive pages still unmount and stop polling; returning does not
repeat model calls or approvals. Sign-out/account changes clear page memory.
This tab-lifetime memory is not a replacement for saved private Artifacts or exports
and does not guarantee a live streaming run continues after leaving its page.

The unified ATLAS workspace also autosaves its current exercise responses,
checklist, unsent tutor message, mode and selected view to private server storage.
Wait for **Workspace saved** for refresh-safe recovery. Failures retain local edits
and offer retry; revisions and exercise/reset identity reject stale writes.
Atomic sidecar files prevent a slow lesson request from erasing a newer draft.
Recovery reuses saved lesson/chat history without model calls or mastery changes.
Each response/message is limited to 100,000 characters, the combined values to
600,000 JSON bytes, and the checklist to 12 items. Only the current exercise is
recovered; reset clears its saved draft. Unsaved keystrokes and other pages'
unsubmitted drafts are not guaranteed after browser close or refresh. See the
[ATLAS manual](ATLAS_MANUAL.md) for recovery controls and remaining roadmap work.

ATLAS also offers on-demand **Study selection**, **Explain instructions** and
**Work on feedback**. The server validates the selected lesson quotation;
only **Ask tutor** uses model credits. Smaller explanations, examples, practice
questions and feedback-grounded hints never submit or replace the exercise or
establish mastery. Reviewed linked notes use existing private Notes and its Pro
gate. Recall-card previews use teaching text without a model call, and never
invent a missing answer. Saved notes/cards display lesson/section/quote/authorship
provenance and recorded source links, not a fact-verification badge. Study drafts
and pending help survive page navigation in the same account/tab, not refresh.
Failed saves keep the draft and require explicit retry; ambiguous retries can
duplicate a saved item. See the [ATLAS manual](ATLAS_MANUAL.md) for the API shapes.

The lecture foundation is read-only: signed-in `GET /api/atlas/lecture`,
`ATLASSession.lesson_lecture()` and `MammothMind.lesson_lecture()` return the shared
`mammoth.lesson_lecture.v1` transcript/section contract. Stable section IDs and a
whole-lesson revision support future commands. No audio or voice provider is
enabled, all playback timing is null, and reading the contract makes no model
call or mastery change. See the [ATLAS manual](ATLAS_MANUAL.md) for identity and
duplicate-section limitations. Existing `AtlasFAB` aliases remain unchanged.

Idea Shaper assesses the supplied idea and context without assuming the owner's
brand, industry, or location. Structured output is checked before success:
invalid or cut-off assessments receive at most one corrective model call, which
can add cost and latency. Repeated failure reports no verdict and does not embed
raw model JSON or provider errors in the assessment. Structural checks do not
verify factual accuracy; `confidence` is `null` rather than an invented numerical
certainty score. The lesson-scoped seed recommendation path remains unchanged.

HTML API errors now include HTTP status and request path. Gateway errors
(502/503/504) are distinguished from routing/content-type failures; neither
proves a missing frontend environment variable. Do not automatically replay a
failed agent POST: the backend may still have performed billable work. Check
server/proxy logs before retrying. Same-origin deployments can leave the
frontend API-origin variables unset when `/api` is correctly proxied.

Coding answers explicitly advice-only questions (such as "what are your
suggestions?") as advice, without requiring fabricated code blocks or claiming
file edits. Implementation/patch requests keep their existing source and
validation requirements. Advice is not factual verification or a code proposal.
Agent failures show the returned summary, failed validation checks, and warnings
rather than only a generic `status=error`.

Startup, session-check, and page-render failures now show recovery controls
instead of an empty screen. Sign-in checks time out after 15 seconds and can be
retried without treating an authentication failure as a signed-out session.
Frontend deployments retain previous hashed assets and publish the HTML entry
last, so older tabs can still load their page chunks. Retained assets need
operator-reviewed disk housekeeping; deployments do not purge them.
Deployment also validates the required public Supabase configuration before
building and publishing, rather than deploying a UI that cannot initialize auth.

Shared controls use the platform theme, including native selects and file
pickers. The command library uses actual CSS rather than unavailable utility
classes. Appearance is dark-only for now: sidebar/Settings theme toggles are
removed, saved Aurora/legacy preferences migrate to Dark, and prior inline
theme colors are cleared so text stays readable. Native controls follow Dark.
The shared palette uses dark neutral layers and grey/white text, warm
brass/copper for primary actions and agent identity, and blue for keyboard focus,
links, and secondary interactions. Decorative purple/pink/teal accents and
rainbow primary-button gradients are removed. Runtime/health success, warning,
and failure colors remain semantic; destructive controls remain red. Disabled
primary workspace controls are neutral, not red. Emojis and logo artwork are
unchanged. The Mammoth Mind lane and task selectors use labeled dark controls
with keyboard focus styling and retain their existing choices.
Design tokens live in the UI's `src/design/tokens.json`; run `npm run tokens`
after changing them. Muted text and accent text are checked at 4.5:1 against
all opaque dark token surfaces, and filled brass actions use dark text.
Mammoth Mind's chat fills the screen height. The toolbar is one row: chat-history
toggle, title (hidden on phones), Agent/Classic, Lane, New Chat, and a **⋯** menu
with **Show repo & run details** (repo context, routing, thought trail, task cards)
and **Delete Chat**. The composer is one box: a full-width message field that
grows as you type (up to about 8 lines), with Attach, Manage saved files (which
also shows upload limits), Prompt templates and Send/Stop in a single row below
it. Typing `/` at the start of a message opens the slash-command and template
picker, filtered as you type. Upload progress, warnings, cancellation and retry
appear above the composer only while relevant.

Lesson Notes uses `GET /api/atlas/lesson-notes`, which rebuilds lesson-matched
resources and excludes operational plans and unrelated recent-note fallbacks.
Other workspace notes and run artifacts are retained in their own libraries.
Flashcards prefer saved, answered Q/A cards for the active lesson, preserving
sources. Fallback recall cards use existing teaching content or public exercise
assertions, never objectives as answers. Legacy objective-only cards are ignored,
and missing content produces an honest empty deck rather than demo cards.

The owner/admin Modules page refreshes backend snapshots every 30 seconds and
reports registry/bridge failures explicitly. Catalog-only agents are `unknown`,
source-only agents are `discovered`, and built-in wiring is `integrated`, not
claimed live health. MCP states distinguish `configured` (launcher present),
`needs_setup`, `needs_context`, and `connected` (a live initialized client in
the current context). Listing bridges does not start servers or verify package,
browser, credential, or network availability. Repository selection and approval
rules remain enforced by the backend; `git_push` is never exposed.

### Learning profile and curriculum handoff

ATLAS exposes onboarding in the workspace: starting level (beginner through
expert study), pacing, learning preference, goals, and focus areas. Learners can
defer it or edit it later. Pacing does not imply mastery. Practice evidence for
the current topic can adjust difficulty; the recommendation includes its reason.
Expert study is not professional certification.

The Curriculum learning agent now renders modules and lesson previews, not just
metadata. Review the output, **Save to my curricula**, then **Start this
curriculum**. **My curricula** holds private saved course snapshots. Starting
begins at the first lesson and replaces the active course; use **Lesson &
practice** to continue the current course. Saved courses are scoped to the
authenticated learner; caller-supplied user IDs do not select their owner.

Generation failures leave explicit drafts, not substitute teaching material.
Whole-course readiness requires all lessons to pass automated content checks,
including minimum teaching depth, worked examples, unique IDs, and distinct
content. These checks do not establish factual accuracy. Drafts can be saved
and exported but cannot be started; regenerate inadequate drafts with the
Curriculum agent. Existing saved conversations can still contain older outputs.
Lesson authoring makes at most two model calls per lesson: one initial attempt
and one correction for invalid JSON/schema or failed teaching checks. Provider
exceptions use the existing provider fallback chain, not another authoring
retry. Safe generation diagnostics distinguish those failure classes without
embedding raw provider errors. Duration checks use a 200-word/minute reading
floor plus the declared practice estimate, not characters as minutes; module
and course estimates are recalculated from lesson estimates. A corrected attempt
can add latency and cost. Existing failed drafts are not silently rewritten.

New template courses first make one bounded outline call to assign distinct
subject-specific subtopics, objectives, and earlier-only prerequisites. A failed
outline leaves a draft without spending on nine lesson authors. Every author
receives the real ordered sequence; next-lesson navigation comes from that
manifest, not an invented promise. Numerical study examples without exact
supplied grounding must be explicitly hypothetical. Structural checks do not
independently verify factual accuracy or completeness of subject coverage.

Written practice uses lesson-grounded AI rubric feedback (concepts, application,
reasoning) when available. If assessment fails, the UI labels the local fallback
as coverage-only: it does not increase mastery or justify a difficulty increase.
The existing navigation gate and explicit audited override remain available.
New lessons and exercises use the learner profile; profile edits do not silently
rewrite existing course content. Preset modules use the same authoring path.
Lesson bodies and curriculum previews use a shared sanitized Markdown reader:
headings, separate paragraphs, lists, emphasis, code blocks, and tables retain
their structure. Standalone standard teaching headings also work in older
plain-text lessons. The lesson pane offers section jumps when there are at least
three headings, with a bounded reading width and mobile wrapping. Presentation
does not regenerate stored teaching content, execute embedded HTML, or load
embedded images; assessments, drafts, and navigation gates remain unchanged.

API: `GET/POST /api/atlas/curricula`, `POST /api/atlas/curricula/start` with
`curriculum_id`, and the existing `POST /api/atlas/onboard`.
SDK: `MammothMind.start_curriculum(curriculum, difficulty="beginner",
learner_context=...)` starts a reviewed snapshot additively; AtlasFAB aliases and
ungated `next_lesson()` defaults remain unchanged.

Lecture mode is not implemented yet. Its tracked delivery plan is
[ATLAS workspace and lecture backlog](ATLAS_WORKSPACE_ROADMAP.md).

## Current upgrade wave (SDK optimization + Mammoth Mind)

| Phase | What shipped |
|---|---|
| 0–1 | Repo lockdown: no repo selected → no repo context; platform repo owner-only; users connect their own repos (tenant repo sources) |
| 2 | Design tokens, trace vocabulary, public user guide docs |
| 3 | Mammoth Mind agent loop (`mammoth.run.v1`): plan, MCP-style tools, approvals, reasoning/run traces; header pill replaces the floating FAB |
| 4 | Mammoth Paths workspace SDK (Python `MammothPaths`, JS `@mammothos/paths`), server-side tier gates, per-user build log; tutor SDK renamed Mammoth Mind |
| 5 | Tutor delivery: lesson manifests, stall telemetry, comprehension gate with override, retrieval dedupe |
| 6 | Research hygiene: reasoning stripped to traces, relevance/disambiguation filtering, dedupe, truncation repair |

Details for each are in the sections below and in `ATLAS_MANUAL.md`.

## Phase 3/4 productization highlights

- UI story surfaces are now workflow-first:
  - Artifact Library with type categories, search, agent/status/date filters,
    full-text previews and exports, linked private ATLAS curricula, recorded
    run/task/repository provenance, and ten previous revision snapshots
  - Task Inbox for queued workflow cards with backend-authoritative loading, explicit failure alerts, and read-only status for run-backed tasks
  - Structured Coding Artifact panel in Agent Console (overview/code/tests/docs/diff)
- Observability surfaces are now tighter:
  - Run History replay keeps task metadata (`task_id`, `trace_id`) and runtime adapter/model context
  - Coding patch apply status is reflected in both artifact detail and run history markers
  - Internet command runs (`/research`, `/web`) are persisted as structured chat events with evidence metadata
  - Chat trust surfaces now consume dynamic backend metadata (`confidence`, `trust_metadata`, `evidence_items`) rather than static UI defaults.
- UX consistency updates now live:
  - Appearance is **Dark-only** while the platform is being polished; saved Aurora, `darker`, and `midnight` preferences migrate to Dark, with no inactive theme toggles
  - Mammoth Mind reply depth adapts to the ask: brief, conversational replies for simple questions and useful structure for complex work
  - Runtime health is a color-coded header pill beside Mammoth Mind; press it to expand provider and fallback details without taking space from page content
  - The chat feed flows directly into the composer without a separating rule


## Repo access model (Mammoth Mind, ATLAS, Workspace)

Enforced server-side in `src/mammoth_os/repo_access.py` (not by UI hiding):

- **No repo selected → no repo context.** There is no implicit default repository.
- **Platform repo is owner/admin-only.** `platform`, `xxii-architect/mammoth_intro_ai`, the backend's own path, and forks of it are rejected for everyone else. Add more private slugs with `MAMMOTH_PLATFORM_REPOS=owner/repo,...`.
- **Users bring their own repos.** `POST /api/mammoth/repo-sources {"repo": "owner/repo"}` clones a public GitHub repo into a per-user sandbox (`MAMMOTH_TENANT_REPO_DIR`, default `.mammoth/tenant_repos/`). Users address it by source id or slug, never by filesystem path. Limit: 5 per user.
- **Writes are proposal-only.** `POST /api/mammoth/repo-sources/{id}/propose` writes on a fresh local branch and returns a git patch. Nothing is pushed. Private repos need the MammothOS GitHub App (not yet registered).
- **Guide uses published docs.** `/guide` answers from `docs/public/` + product guides, not live source.
- **Host-executing agents are admin-only** (shell, filesystem, deploy, build, executor, ui_builder, database, custodial), including the `/agent/*` HTTP routes.
- **Shared agents are sandboxed for non-admins.** The server forces these flags on every run, overriding anything the caller sends:
  - CodingAgent (`host_access=false`): no host file reads, no codebase scans, no host test runs, no shared vector-store lookups. On `/api/run` it only works on code the caller pastes. For real files, use a connected repository (see Agent Workspace → Coding with a repository).
  - SearchAgent (`host_access=false`): no workspace/codebase search of the host. Only the owner/admin can search the platform source.
  - BrowserAgent (`allow_private_network=false`): only public http(s) addresses, checked on every redirect hop. No loopback, LAN, or cloud-metadata addresses, and no Lighthouse/Playwright subprocesses.
  - BrowserAgent (`session_scope`): browser sessions and replays are scoped per user.
- Production must run with `MAMMOTH_REQUIRE_AUTH=1`; with auth off every request is treated as the local owner.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/mammoth/repo-sources` | List your sources + picker options (platform option only for admin) |
| `POST /api/mammoth/repo-sources` | Connect `owner/repo` |
| `POST /api/mammoth/repo-sources/{id}/sync` | Re-clone latest default branch |
| `DELETE /api/mammoth/repo-sources/{id}` | Remove source and sandbox clone |
| `POST /api/mammoth/repo-sources/{id}/propose` | Branch + patch proposal (never pushed) |
| `POST /api/mammoth/repo-context` | Snapshot for a selected source (403 when denied) |

## Design tokens + trace vocabulary

- Tokens live in `ui/mad-architecht-command-center/src/design/tokens.json` (W3C DTCG format) and compile to `tokens.css` via `npm run tokens` (runs automatically before `npm run build`).
- One agent accent (copper `--mm-color-agent-default`) for agent activity and pending approvals; blue for system state; red only for failures/irreversible actions. Motion tokens drop to 0ms under `prefers-reduced-motion`.
- Trace glyphs (`src/design/traceVocabulary.js`, `TraceGlyph.jsx`): read, searched, fetched, planned, reasoning, ran, tool, delegated, wrote, proposed, awaiting approval, applied, reverted, failed. Every glyph carries a text label; meaning never depends on colour alone.

## Mammoth Mind agent runs (`mammoth.run.v1`)

Mammoth Mind's **Agent** mode (default; toggle to **Classic** in the chat header) runs a plan → tool → observe loop in `src/mammoth_os/agent_loop/` and streams every step as Server-Sent Events. The UI renders them as a collapsible timeline: plan checklist, one-line reasoning summaries, tool rows, proposed diffs, and inline approval cards. Slash commands and attachments still use the classic chat path.

### Reasoning, reflection and evidence

The **Reasoning Agent** lane analyzes the supplied situation: assumptions, a
competing interpretation, tradeoffs, practical checks and a concrete next step.
Its guidance applies in both the Agent loop and Classic runtime. Classic analysis
is validated structured model output, not a canned tutor paragraph or an echoed
prompt. Invalid/offline output is reported as failed, not a successful insight.
Abstract models, analogies, counterfactuals and speculative ideas remain welcome:
brainstorming is not restricted to published sources. Hypotheses must be labeled,
with assumptions and a way to test them; factual claims still need evidence.
Explicit tutor-hint/coaching modes retain Socratic questions, error-pattern hints
and micro-lessons; rule-based help remains labeled when model enrichment fails.

The separate Reflection agent preserves learner signals and follow-up tags, but
its displayed summary now includes the generated insight, question and action.
User input and derived hints are not external evidence or 100% citation coverage.
Neither analysis agent assigns an uncalibrated correctness percentage.

Research favors relevant government and institutional sources, without a closed
website allowlist. Source authority is a retrieval preference, never a truth
guarantee; the correct subject, jurisdiction, date and supporting passage still
matter. **Interpretation** means analysis; **Source-linked** means excerpt links
were checked, not fact-verified; **Unverified** means the required support is not
established. Search snippets and domain names alone do not verify a claim.
The source catalog covers fish/wildlife agencies for all 50 US states, with
directory provenance and exact-host exceptions for official non-government
domains. It prioritizes relevant, matching-jurisdiction sources rather than
letting an unrelated official page outrank useful evidence. Institutional
`.edu` content is distinguished from identifiable personal/student pages.
These are hostname and relevance heuristics, not universal ownership checks;
unlisted credible sites remain eligible. The directory check found an Ohio
endpoint returning 404 and a Mississippi TLS validation failure: catalog
membership does not imply a live or successfully retrieved page.

Recursive multi-agent orchestration is available as an **opt-in** Agent-mode
feature: **More chat options → Recursive review**. It connects a real planner,
the existing tool executor, a critic and a synthesizer, with up to two passes by
default. Existing validation/application approvals and repository isolation remain
mandatory. Python Paths accepts `recursive=True`; JavaScript accepts
`recursive: true`, or a bounded budget object. Saved runs support approval/resume
without replaying completed roles; unknown interrupted provider/tool outcomes
fail closed. Stage events and provider-reported token/tool usage are visible in
the run trace. This uses additional model credits and does not make critique a
factual-verification guarantee. Limits and accounting caveats are documented in
[`src/mammoth_os/recursive/README.md`](src/mammoth_os/recursive/README.md).

A clean recursive pass normally requires four model-role calls (planner, executor,
critic, synthesizer); one revision normally brings that to seven, before extra
tool-loop/repair calls. This is not a fixed credit multiplier: billing depends on
the provider and actual input/output tokens. The default 64,000-token ceiling is
a limit, not a reservation or an upfront charge.

### Specialist output quality

Market Intel handles product-buying questions as well as market analysis. It uses
the shared bounded research retrieval pipeline by default, prefers relevant primary
source material, and requires matching excerpt-linked findings for its factual
answer. Supplied `sources` avoid network retrieval; `allow_web_lookup: false`
disables automatic lookup. Exact variants, package sizes and current availability
must be supported rather than inferred. Tradeoffs and analyst interpretation are
separate from findings; citation linkage is not independent factual verification.
Missing evidence produces `insufficient_evidence`, not an invented market report.

Brand Voice, Field Ops and Community also require complete structured generation:
invalid, truncated or unavailable model output returns an explicit failure, never
canned copy disguised as completed work. Field Ops retains weather/hazard handling
and navigation contracts; Community retains deterministic reward and review policy.
The Agent panel and team-run drilldowns show Market Intel sources and evidence.
These checks improve output contracts; they are not a guarantee of model accuracy.

### Saved results, team follow-ups and document access

- Specialist `/api/run` outputs and `/api/plan-execute` team results are archived
  with a complete structured `snapshot` (`mammoth.artifact.v1`) and readable Markdown.
  Team archives include individual step outputs and synthesis. Responses report
  `artifact_save.status: saved|failed`; a run can finish while archival saving fails.
  Export before leaving if saving fails. Snapshots over 4 MB are rejected explicitly,
  never silently shortened. The existing library retains up to 120 outputs and ten
  prior revisions per output; export important work for an independent archive.
- Agent replies and team results offer save, Markdown export and complete JSON export.
  Mammoth Mind exposes these under **Save / export output**. The Artifact library
  reopens saved results without executing agents or charging model credits.
  Older flattened artifacts remain readable but cannot recover omitted fields.
- **Prepare follow-up plan** creates an explicitly reviewed new team execution.
  `parent_artifact_id` references an accessible saved team result, not a filesystem
  path or approval. Prior context is bounded to 16,000 characters, with a shortening
  notice; the archive remains complete. New execution uses additional model credits.
- Uploaded documents are indexed within the existing extraction limits (2 million
  characters, 2,000 units). The initial chat context contains selected excerpts, not
  the entire file. Agent-mode `document_list`, `document_search` and `document_read`
  can inspect the caller's indexed chat/ATLAS documents without repository access.
  Read offsets allow sequential inspection beyond search matches. Indexing is not
  proof of a whole-document review. Classic chat still receives selected excerpts.
  Scans/images need OCR, which is not enabled; legacy preview-only uploads need
  re-uploading. Extraction warnings remain visible and are passed to the agent.
- Notes and Build Log are in Workspace navigation, with unchanged routes and SDK
  access. Notes supports searching, editing, export and confirmed deletion; Build Log
  exposes load/save errors and exports real session records. ATLAS preserves the
  exercise draft on a failed lesson start and surfaces unavailable supporting data.
- ATLAS is content-first on phones: compact Lesson/Tutor/Agents/Curricula tabs,
  an on-demand module browser and learning profile, Read/Practice jumps, and
  collapsible outline/progress. Reading options adjusts text size/spacing and
  enables focused reading. Phone landscape uses the compact layout too.
  Reading and layout changes never satisfy mastery or trigger model calls.
  Drafts survive view changes, not a browser refresh; durable recovery remains
  on the ATLAS roadmap. Retention/time-to-competency is not inferred from counts.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/mammoth/tools?repo=` | Tool catalog visible to *you* for that repo selection |
| `POST /api/mammoth/runs` | Start a run (SSE). Body: `message`, `agent_id`, `repo_context.root`, `approval_mode` (`tools`\|`always`), `thread_id`, optional `recursive` (`true` or budget object) |
| `GET /api/mammoth/runs` / `GET /api/mammoth/runs/{id}?after=` | Your recent runs / replay events after a sequence number |
| `POST /api/mammoth/runs/{id}/approval` | `{approval_id, decision: approve\|reject, note}` → resumes the stream (audited) |
| `POST /api/mammoth/runs/{id}/cancel` | Stop a run |
| `POST /api/mammoth/runs/{id}/continue` | Continue saved partial/recoverable work (SSE, owner only, bounded additional usage) |

Event types: `run.started`, `plan.updated`, `reasoning.summary`, `tool.call`, `tool.result`, `approval.requested`, `approval.resolved`, `diff.proposed`, `message.delta`, `message.completed`, `run.awaiting_approval`, `run.completed`, `run.failed`, `run.cancelled`, `run.partial`, `run.continued`, `run.recovering`, `model.completed`. Each event carries `contract`, `run_id`, `seq`, `ts`.

Rules the loop enforces:

- **Tool tiers:** `read`, `network`, `write` (proposal-only, never touches the checkout), `exec` (always needs approval). MCP tools whose names look mutating also need approval; `git_push` is never exposed.
- **Repo tools follow the repo access model.** No repo selected → no repo tools. Paths are repo-relative; `..`, absolute paths, `.git`, symlinks, and secret files are refused.
- **Patches are edit-first.** `repo_propose_patch` takes either full `content` (new or small files) or `edits` (exact `old` → `new` snippets, each matching once) per file, so the model never has to re-send a large file. A missed edit reports the line(s) where its first line appears. The connected repo is named in every prompt.
- **Large files:** `repo_read_file` can reach any line of files up to 5 MB (400 lines / 20 KB per call, with `total_lines` and `next_start_line`). The newest three tool results are shown to the model in full (24K chars) as raw text, and older ones are condensed. Clipped excerpts always state the last line shown, so the model never edits text it hasn't seen. DeepSeek's native tool-call markup is parsed as a real tool call.
- **MCP access:** each `mcp/*.json` declares `access: admin|tenant`. Admin repo servers (filesystem, git) are only offered to the owner with the platform repo selected; tenant servers run with the user's sandbox clone as cwd.
- **Honest output:** reasoning lines are short model-written summaries (no hidden chain-of-thought). Malformed decisions, empty responses, confirmed output limits, refusals, and offline responses are distinguished; none is marked completed. Exhausted step budgets or repeated tools produce a partial summary, not a success claim. This is runtime validation, not certification of a model's factual or task-completion claims.
- **Bounded recovery:** invalid decisions retry once without spending a task step or rerunning saved tools. Cloud decisions request JSON mode on recognized supported endpoints; compatible/custom endpoints retain the validated text protocol. Ordinary decisions allow 4,096 output tokens; source-backed owner validation/application decisions and separate prose finalization allow 8,192. Provider finish reason, model and reported usage are saved and available in collapsed diagnostics; private reasoning is never substituted for a missing answer.
- **Schema-constrained decisions:** recognized GPT-4o/4.1 models on the official OpenAI endpoint now use strict `json_schema` output. The schema lists only tools authorized for the current context and distinguishes tool / answer / separate-finalization actions. Open-ended tool arguments remain JSON-encoded inside the envelope and are checked against the canonical registry schema before approval or execution. DeepSeek retains JSON mode, Ollama retains its JSON format, and custom/text adapters retain the validated compatibility path. Protocol selection is reported in diagnostics; it does not claim all providers have strict schemas or certify tool results. SDK `generate()` remains text-only. Adapter config `structured_decisions=False` explicitly selects the legacy JSON-mode path; schema API errors are surfaced, not silently downgraded or billed through additional retries.
- **Continue task:** partial/recoverable runs retain their transcript and original request. The owner can continue up to twice, with eight additional task steps per continuation by default. The backend rebuilds repository access, preserves approvals, and rejects concurrent/already-finished continuations. Both SDKs expose explicit continuation (`continue_run` / `continueRun`); neither automatically spends more credits.
- Runs are stored per user under `.mammoth/agent_runs/` (last 50); other users get 404.
- `/api/internet/*` fetches refuse private, loopback, and link-local targets, including on redirects (SSRF guard).

## Web search (`mammoth.websearch.v1`)

`src/mammoth_os/web_search.py` is the single licensed web-search client (stdlib only).

| Env var | Purpose |
| --- | --- |
| `BRAVE_SEARCH_API_KEY` | Brave Search API key |
| `TAVILY_API_KEY` | Tavily Search API key |
| `MAMMOTH_WEB_SEARCH_PROVIDER` | `auto` (default: Brave, then Tavily), `brave`, or `tavily` |
| `MAMMOTH_WEB_SEARCH_DAILY_LIMIT` | Upstream calls per day per process (default `1000`) |

- **Agent mode** gets a network-tier `web_search` tool, but only when a key is configured (restart after changing `.env`). `GET /api/mammoth/tools` reports `web_search.configured` and `web_search.provider`.
- **ResearchAgent** spends one API call per request, on the primary query. When it returns hits, DuckDuckGo scraping is skipped. Wikipedia always runs.
- **SearchAgent** includes web results by default. Pass `allow_web: false` to skip them. With no key it returns no web results and adds the `web_search_not_configured` flag instead of a placeholder.
- Bounds: 8 s timeout, a 10-minute cache (128 queries), at least 1 s between upstream calls, and the daily cap. Errors are coded `not_configured`, `empty_query`, `daily_limit`, `rate_limited`, `auth_failed`, `provider_error`, or `unreachable`. Keys never appear in results or errors.
- Shared retrieval hygiene removes off-topic results, documentation-intent mismatches,
  duplicate URLs (ignoring tracking parameters/fragments), disambiguation pages, and
  obvious source instructions before caching or model delivery. Subject matches in
  titles/URLs rank above snippet-only matches; generic words such as "API" or "docs"
  do not establish relevance to a named product. Research fallback sources use the
  same rules. Supplied sources remain exempt from topical pruning, not instruction checks.
- Search responses and Mammoth Mind tool traces include a `quality` block with
  retained/dropped counts and reason counts. A successful provider request with no
  usable results returns `results: []` and `quality.evidence_status: "insufficient_evidence"`.
  SearchAgent exposes these diagnostics as `web_search_quality`. Filtering adds no
  provider/model calls and does not verify domain ownership, factual accuracy, or
  claim entailment; instruction detection is heuristic, not comprehensive protection.
  Research briefs and long-form quality blocks expose `retrieval_filtering` for
  the post-retrieval evidence pool (separate from provider-side filtering counts);
  excluded instruction snippets are never copied into those diagnostics.

## Weather (`mammoth.weather.v1`)

`src/mammoth_os/weather.py` wraps [Open-Meteo](https://open-meteo.com) (stdlib only). It handles geocoding, current conditions, a forecast of up to 7 days, and fixed-threshold hazard flags. Hazards cover thunderstorms, freezing precipitation, snow, fog, gusts of 35 mph or more, heat of 95 °F or more, cold of 20 °F or less, heavy precipitation, and UV of 8 or higher. No model is involved.

| Env var | Purpose |
| --- | --- |
| `OPEN_METEO_API_KEY` | **Required for commercial use.** Open-Meteo's free API is non-commercial only. Setting a key switches to the customer endpoints. |
| `MAMMOTH_WEATHER_UNITS` | `imperial` (default) or `metric` |
| `MAMMOTH_WEATHER_ENABLED` | `0` turns weather off everywhere |

- **Field Ops** looks up weather only when the request names a place. That means a `location` field, `latitude`/`longitude`, or a capitalized place after "in / near / at / around" (for example "near Stanley, Idaho"). It never geocodes common words like "forest". The forecast is given to the model, weather hazards count toward `risk_level` and `safety_notes`, and the result carries `forecast` and `weather` (or a coded error with the `weather_unavailable` flag). A failed lookup never fails the mission.
- **Agent mode** gets a network-tier `weather_forecast` tool.
- Results are cached for 15 minutes. Every result carries the CC BY 4.0 attribution "Weather data by Open-Meteo.com", and it is shown wherever the forecast is.

## Reply ratings (`mammoth.feedback.v1`)

Every stored Mammoth Mind reply shows 👍 / 👎 next to Copy. Clicking the active thumb again clears it, and a thumbs-down can add an optional reason (`incorrect`, `incomplete`, `off_topic`, `unsafe`, `formatting`, `too_long`, `other`) and a short comment.

| Endpoint | Who | Purpose |
| --- | --- | --- |
| `GET /api/message-feedback` | signed-in user | Your own ratings (no excerpts) |
| `POST /api/message-feedback` | signed-in user | `{run_id \| created_at, direction: up\|down\|none, reason, comment, thread_id}` |
| `GET /api/message-feedback/summary` | owner/admin | Totals and approval by provider/model and agent, plus down-vote reasons |
| `GET /api/message-feedback/regression-cases?limit=` | owner/admin | Thumbs-downs deduped by prompt (`mammoth.feedback.regression.v1`) |

- **Rate only your own replies.** The server finds the message in *your* threads or chat history (404 otherwise), and takes the prompt and reply excerpts from its own copy. Client-sent text is ignored. There is one rating per user per message, and the store keeps the latest 5,000 ratings in `.mammoth/message_feedback.json`.
- **Ratings are signal, not self-modification.** Nothing retrains or reroutes the model automatically. Owners see the aggregate and the regression cases under **Beta Feedback → Reply ratings**. Download the cases JSON and replay it for side-by-side human review:
  `python -m mammoth_os.feedback_replay --input cases.json --out replay.md` (add `--no-replay` to only list the cases). The replay never grades on its own.
- Ratings are included in the account data export.

The owner/admin Reply ratings panel supports agent and inclusive UTC date-range
filters. Dates use the rating's latest update, not the reply's creation date.
Both admin endpoints accept `agent_id`, `date_from`, and `date_to` (`YYYY-MM-DD`);
invalid date ranges return HTTP 400. Filtering happens before aggregation and
regression-case deduplication, so Cases JSON matches the selected scope.

## MCP Browser Bridge + Repo Access

MammothOS now ships three MCP server configs in `mcp/` that give Mammoth Mind real browser automation, repo read/write access, and git awareness.

## Repo-context quick prompting (Mammoth Mind + ATLAS)

If you want the chat assistant to read file contents (not just repo names), include at least one of:

- a filename (`api_server.py`, `DiagnosticsPage.jsx`)
- a relative path (`src/mammoth_os/atlas_session.py`)

A repository must be selected in the Repo Context panel first (see the repo access model above).

What now happens automatically:

- filename/path hints in natural language are resolved to real tracked files when possible
- repo context falls back to token-based search when full-query grep returns no hits
- chat evidence now includes repo snippet/search signals so trust badges can reflect real context use
- the chat response reports `repo_scope` (`none`, `tenant`, `platform`, `public_docs`) and a `repo_access_notice` when a request was denied

### Quick start

```bash
# Start the browser bridge (headed mode for first auth)
bash scripts/start-browser-mcp.sh        # Linux/macOS
.\scripts\start-browser-mcp.ps1          # Windows
```

Linux fallback for non-interactive audits:

```bash
MCP_BROWSER_MODE=system-headless bash scripts/start-browser-mcp.sh
```

If needed, point at a specific browser:

```bash
MCP_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium MCP_BROWSER_MODE=system-headless bash scripts/start-browser-mcp.sh
```

### MCP servers

| Server | Config | What it does |
|---|---|---|
| **Browser (Playwright)** | `mcp/playwright.json` | Headed Chromium automation — navigate, click, fill, screenshot, Lighthouse audit |
| **Filesystem** | `mcp/filesystem.json` | Read/write repo files (secrets denied) |
| **Git** | `mcp/git.json` | status, diff, log, branch; commit/push require approval |

### Site audit intent

In Agent Console, use intent `site_audit` to run a full browser + Lighthouse audit against any URL. Results include heading structure, nav/CTA extraction, performance score, SEO score, accessibility score, and top 10 fix opportunities.

### MCP status in UI

The **Modules page** shows a **MCP Tool Bridges** panel with live ready/needs_setup/disabled status for each bridge.

## 8 → 9 upgrade phases (completed)

All four phases of the 8 → 9 pass are now done:

1. **Execution quality loop ✓** — plan → act → verify → retry with explicit success checks; structured agent responses in place.
2. **Browser automation layer ✓** — stateful navigation, form filling, and replayable browser actions.
3. **Agent memory + evals ✓** — durable `MemoryEngine` records ATLAS lesson outcomes; `/api/memory` and `/api/atlas/evals` expose history; eval observability is wired.
4. **UI / manual / docs refresh ✓** — `ATLAS_MANUAL.md`, the in-app Manual page, `LandingPage` doc links, and this README are now in sync.

## 9.5 hardening pass (completed)

- Runtime reliability is now fail-closed for fallback conditions so degraded provider states are explicit.
- `/api/health` now emits a `health_gate` snapshot that combines runtime, env, venv, and repo readiness.
- `/api/release-readiness` now emits both `release_gate` and `eval_gate` snapshots and blocks release readiness when eval history is absent or below threshold.
- ATLAS learner context now includes `outcome_summary`, `learning_signal`, and `progress_score` for measurable tutoring outcomes.
- `AtlasFAB.snapshot()` now includes explicit `contract_version`, `product_surface`, tenant binding state, and usage policy metadata.
- Billing warning behavior is available through `GET /api/billing/usage/current` with preview-safe metering labels and warning levels.

## Product docs

- `docs\atlas_fab_product_guide.md` - Mammoth Mind tutor SDK (formerly ATLAS FAB) positioning, workflow diagram, and pricing skeleton
- `docs\public\mammoth_mind_user_guide.md` - end-user guide for Mammoth Mind (agent mode, traces, repo context, tutor)
- `docs\public\mammoth_paths_sdk_guide.md` - Mammoth Paths workspace SDK guide (Python + JS)
- `packages\mammoth-paths\README.md` - JS client package reference
- `docs\mammoth_os_package_offering.md` - package offering, install tiers, and commercialization framing
- `ATLAS_MANUAL.md` - operator/CLI playbook and phased upgrade notes
- `ui\mad-architecht-command-center\src\pages\ManualPage.jsx` - in-app UI manual

## Deploy to DigitalOcean droplet (live site)

This repo now includes `.github/workflows/deploy-digitalocean.yml` for push-to-`main` and manual deploys.
Every push to `main` auto-deploys to the live server at `165.227.80.86`.
The deploy workflow now runs release guardrail tests first and only deploys when they pass.

### Mandatory release gate workflow

`.github/workflows/release-guardrails.yml` enforces the reliability/eval/tutor/SDK gate suite on:
- pull requests targeting `main`
- pushes to `main`
- manual workflow dispatch

Recommended branch protection policy:
- require `Release Guardrails / guardrails` to pass before merge
- require `CI / tests` to pass before merge

### GitHub repository secrets (set once under Settings → Environments → production)

Required:

| Secret | Value |
|---|---|
| `DO_SSH_PRIVATE_KEY_B64` | **base64-encoded** deploy private key (preferred — avoids multiline secret corruption) |
| `DO_HOST` | `165.227.80.86` |
| `DO_USER` | `root` |
| `DO_APP_PATH` | `/opt/mammothos/mammoth_intro_ai` |
| `DO_DEPLOY_COMMAND` | `bash /opt/mammothos/mammoth_intro_ai/scripts/deploy-droplet.sh` |

Optional:

| Secret | Default |
|---|---|
| `DO_SSH_PRIVATE_KEY` | Fallback plain-text key (use B64 instead whenever possible) |
| `DO_PORT` | `22` |
| `DO_BRANCH` | `main` |
| `DO_KNOWN_HOSTS` | Auto-scanned via `ssh-keyscan` if omitted |

### Generating the base64 deploy key (one-time setup)

```bash
# On your local machine — encode the existing deploy key
base64 -w 0 ~/.ssh/mammoth_deploy_ed25519
# Paste the output as DO_SSH_PRIVATE_KEY_B64 in GitHub secrets
```

### Backend restart (on droplet)

Always use systemd — **never** start uvicorn manually on the server:

```bash
sudo systemctl restart mammothos   # restart backend
sudo systemctl status mammothos    # check health
sudo journalctl -u mammothos -n 50 # tail logs
```

The service runs: `python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8000`

### Manual deploy (without GitHub Actions)

```bash
ssh root@165.227.80.86
bash /opt/mammothos/mammoth_intro_ai/scripts/deploy-droplet.sh
```

## SDKs at a glance

| SDK | What it embeds | Python | JavaScript |
| --- | --- | --- | --- |
| **Mammoth Mind** (tutor; formerly ATLAS FAB) | Adaptive lessons, submissions, progress, runtime state | `from mammoth_os import MammothMind` | (UI pill in the app) |
| **Mammoth Paths** (workspace) | Mammoth Mind agent runs + approvals, bring-your-own repos, notes, build log, owner terminal | `from mammoth_os import MammothPaths` | `@mammothos/paths` in `packages/mammoth-paths/` |

The `AtlasFAB*` names are permanent aliases for `MammothMind*` (same classes), and wire values such as `product_surface: "atlas_fab"` are unchanged, so existing integrations keep working.

## Mammoth Paths workspace SDK

### Agent Workspace payload parity

Python and JavaScript now expose matching `surface`, `task`, `history`, and
attachment options (`attached_file_ids` / `attachedFileIds`) on run/stream calls.
Use `surface="agent_workspace"` / `surface: 'agent_workspace'` for bounded supplied
history without importing or appending to Mind threads. Omitted fields preserve
existing requests; no selected repo still means no repo context. Task briefs and
document access remain server-controlled. See the
[workspace SDK guide](docs/public/mammoth_paths_sdk_guide.md#agent-workspace-context).

Contract coverage builds and installs a wheel and npm tarball into temporary
locations, then exercises both against the loaded backend routes: workspace
context, approval/resume, cancellation/recovery, per-request token changes,
cross-user denial, platform-repo denial and anonymous rejection. Auth, document
context and providers/tools use isolated fixtures; SSE responses are buffered by
the test bridge. This does not test paid providers, real document retrieval,
production proxy timing/disconnects or hostile-code isolation. CI requires these
package tests rather than silently skipping missing Node/npm, and checks the
public JavaScript run-option types.

### Saved-run recovery and review

**Workspace > Run Review** lists the current account's saved runs and reopens
their plans, tool traces, diagnostics, blockers, checks and branch receipts.
It is deliberately read-only: refresh is GET-only and never starts a model,
continues a task, approves a tool, or syncs a repository. The saved list is bounded
by server retention, not a permanent archive. Downloads are explicit JSON
snapshots; they may contain prompts, source excerpts, tool arguments and logs,
so review them before sharing. They do not certify correctness.

Python `paths.recover_run(run_id)` returns `RunResult` with the authoritative
saved status, pending approval, events and `snapshot`. JavaScript
`paths.recoverRun(runId)` returns a reducer-compatible `RunState`;
`hydrateRun(fullSnapshot)` provides the same pure hydration for custom transports.
These read the full snapshot, not an `after`-filtered event suffix. Saved
cancellation/restart state takes precedence over historical approval events.
Duplicate streamed sequence numbers are ignored; new out-of-order or cross-run
events raise an error instead of corrupting the visible result.

No automatic retry, reconnect loop, durable background execution, or new
permissions/settings are introduced. After a disconnect, recover saved evidence
before deciding whether to explicitly continue or resolve an approval. Expiry,
repository access and both owner approval gates still apply on the backend.

Mammoth Paths is a thin, versioned client (`mammoth.paths.v1`) over the backend. Every call is scoped server-side to the caller's token, so an embedder can never read another user's runs, repos, notes, or build log, or the platform repository.

```python
from mammoth_os import MammothPaths

paths = MammothPaths("https://your-backend", token=user_access_token, usage_hook=print)
paths.connect_repo("owner/repo")                       # public GitHub repo -> private sandbox
result = paths.run(
    "Find where auth tokens are validated",
    repo="owner/repo",
    on_event=lambda e: print(e.type),                 # mammoth.run.v1 events
    approve=lambda e: e.data["tool"].startswith("repo_"),  # optional approval policy
)
print(result.status, result.reply, result.diffs)
paths.save_note("Follow up on token expiry", title="Auth")
paths.log_build("Shipped token validation fix")
```

```js
import { createPathsClient, createRunStore } from '@mammothos/paths'

const paths = createPathsClient({ baseUrl: 'https://your-backend', getToken: () => session.access_token })
const store = createRunStore()                   // React: useSyncExternalStore(store.subscribe, store.getSnapshot)
const result = await paths.run('Summarize the README', { repo: 'owner/repo', onEvent: store.dispatch })
```

Surface access:

| Surface | Who |
| --- | --- |
| Agent runs, tools, repo sources | Any signed-in user (own data only) |
| Agent Workbench page | Pro / Enterprise / developer access; shared agents run sandboxed for non-admins (no host files, tests, private-network fetches, or other users' sessions) |
| Task Inbox, run feeds, artifacts | Any signed-in user, own items only. Platform activity, approvals, snapshots, and pre-scoping tasks without an owner stay owner-only |
| Notes, build log | Pro / Enterprise / developer access, enforced server-side (`tier_required` 403 otherwise); entries are per user, and pre-scoping build-log entries stay owner-only |
| Terminal | Owner/admin only |

`usage_hook` / `usageHook` receives `{surface, method, path, status, duration}` for every call. Use it for client-side metering until server-side tenant metering ships. The JS package is `private: true` until you decide to publish it. The app consumes it from source (Vite alias) so the UI and embedders fold run events identically.

The workspace clients also expose `list_tasks` / `listTasks`, `save_task` /
`saveTask`, `list_artifacts` / `listArtifacts`, `save_artifact` / `saveArtifact`,
`get_artifact_run` / `getArtifactRun`, `delete_artifact` / `deleteArtifact`, and
`clear_artifacts` / `clearArtifacts`. Responses preserve the backend payloads.
Updating a saved artifact ID retains up to ten previous snapshots; revision
numbers are server-assigned. Recorded repository/base-SHA metadata stays empty
when unavailable. A base SHA identifies the observed selected Git ref, not a
claim that every source snippet came from a clean working tree.
Run lookup is account-scoped and read-only; saved history is explicitly
client-supplied. Output-contract and syntax checks do not establish acceptance
test success, factual accuracy, review approval, or safe-to-apply code.

## Owner isolated coding validation pilot

This is **opt-in validation and separately approved local-branch application,
not autonomous repository editing**. Owner/admin
authorization and an explicitly selected repository are checked by the backend.
Tenants cannot use these routes or tools. Existing tenant edits remain proposals.
No repository selected means no repository context.

- Frozen proposals bind the repository, committed HEAD, full text changes, fixed
  test profile, snapshot digest and immutable container image to one approval.
  Approval expires after 15 minutes; reuse, changed HEAD or mismatched inputs fail.
- Preparation accepts `{path, content}` or `{path, edits: [{old, new}]}`.
  Exact edits are ordered, must each match once, and resolve against the frozen
  committed snapshot, not the dirty checkout. Use full content for new files.
  Large existing files no longer need to fit entirely in a model response.
- A detached disposable worktree holds the candidate. Uncommitted checkout files
  are neither included nor overwritten. No checkout hooks/filters/submodules run.
- Baseline and candidate checks run offline in a non-root Linux Docker container:
  read-only root and input, no capabilities, no Docker socket or host environment
  credentials, bounded tmpfs, 256 MB memory, one CPU and 64 processes. There is
  **no host execution fallback**, dependency installation, automatic merge or push.
- Containers share the host kernel. This is not a hostile-code VM or a security
  certification. Use only reviewed repositories/images; never bake secrets into
  source or the image. Known secret paths and Git metadata are excluded.
- Cancellation stops only the job's container. Interrupted jobs are not resumed;
  restart recovery cleans their worktrees/containers. A cleanup failure blocks
  further execution without preventing the rest of the platform from starting.
- The resulting draft patch, run-backed task and baseline/candidate evidence are
  saved for review through both the direct API and Mammoth Mind tool flow.
  Passing repository tests is **not independent acceptance verification**.
- After successful validation without observed regressions, a **second approval**
  can create a commit on `mammoth/owner/<execution-id>` in the selected repository.
  The selected checkout, HEAD, staged index and uncommitted files stay unchanged.
  The application uses a private Git index and create-only branch ref, not checkout
  hooks or repository programs. No merge, push or deployment is performed.
  The application digest is different from the validation digest and expires
  after 15 minutes. Changed HEAD/image, modified proposals and reused approvals
  fail closed. Restart recovery reconciles a recorded branch/commit intent; it
  never silently retries application or overwrites an existing branch.
- Mammoth Mind **Agent mode** exposes `owner_execution_status`, `prepare`, `run`
  and `apply` tools (the latter three use the `owner_execution_` prefix).
  Ask it to inspect a selected repo, prepare changes, run checks, then apply to a
  new local branch. Testing and application each pause at their own approval.
  The approval card loads the full recorded patch and test evidence; unavailable
  evidence disables approval. Evidence that does not load within 20 seconds
  shows a **Retry loading evidence** action; nothing is approved meanwhile.
  Loaded evidence shows when the approval window closes. When it closes (or
  the evidence arrives after it closed), the card says the approval expired,
  disables Approve, offers no retry and asks you to reject it and start a new
  run; nothing is approved or applied.
  After you click Approve/Reject, the card shows "Approval sent" and the run
  shows a live activity line derived from recorded events (for example
  "Validating in isolation…" during `owner_execution_run`, or "Considering the
  next step…" between tool calls). The Coding workspace also has a direct second
  approval button. Application results record branch and commit in artifacts,
  tasks and activity; a passed test profile never means automatic approval.

Operator setup (backend host, disabled by default):

```powershell
$env:MAMMOTH_OWNER_EXEC_ENABLED = '1'
$env:MAMMOTH_OWNER_EXEC_IMAGE = 'your-reviewed-image@sha256:<64-character-digest>'
python api_server.py
```

Install the pinned image yourself first; the service never pulls it. The image
must contain Python 3.11.8+ for the trusted archive launcher. The fixed profiles are
`python_unittest`, `python_pytest` and `node_test`; pytest/Node must already exist
in the image when those profiles are chosen. Network access is disabled, so
dependencies must be supplied by the reviewed image. Snapshot limits: 32 MB /
3000 files; proposals: 1-20 text files / 500 KB; rendered patch: 1 MB;
each phase: 60 seconds; logs:
16 KB. Excluded directories (including `venv`, `.venv`, `node_modules` and build
outputs) are omitted before Git entry-type validation. Source symlinks and
submodules outside those directories remain rejected, with their path and Git
mode in the error; they are never followed. The Coding workspace exposes live
readiness, HEAD, preview, explicit approval, cancellation and recorded evidence.

Readiness runs a bounded, offline, non-root probe of the pinned image.
`isolation.profiles` reports available tools for each configured profile;
unavailable profiles are disabled in the picker and rejected before freezing a
proposal and again before container execution. A plain Python image typically
supports `python_unittest`, not pytest or Node. Tool availability does not prove
that a repository's dependencies are installed or that its tests cover an edit.
The three generic profiles do not run `npm run build` or validate GitHub Actions
YAML. Optional `ui_build`, `ui_component` and `ui_browser` profiles use a separate frontend image.

The standalone **UI Build** workflow runs `npm ci` and `npm run build` with Node
22 using the versioned command-center lockfile on relevant PRs, pushes to `main`,
and manual dispatch. Keep that lockfile synchronized when changing UI
dependencies; a local-only ignored lockfile cannot support clean CI installs.
Triggers include the
command-center UI, `packages/mammoth-paths` (imported by Vite), and the workflow
itself. It is post-publication CI, not a pre-application owner validation profile.
Making it a required merge check is a separate GitHub branch-protection setting.
For isolated pre-application frontend checks, build the reviewed image with
immutable Node 22.12+ and Python 3.11.8+ base references:

```powershell
docker build --file scripts\owner-ui\Dockerfile --build-arg NODE_IMAGE=node@sha256:<reviewed-digest> --build-arg PYTHON_IMAGE=python@sha256:<reviewed-digest> --tag mammoth-owner-ui:reviewed .
docker image inspect mammoth-owner-ui:reviewed --format '{{.Id}}'
$env:MAMMOTH_OWNER_UI_IMAGE = 'sha256:<image-id-from-inspect>'
```

Set the optional image variable persistently on the backend host and restart the
service. Both repo@sha256 references and immutable local image IDs are accepted.
Install that image on the backend yourself; runtime never pulls it. The
Dockerfile-specific allowlist sends only UI/root test manifests and lockfiles,
the trusted validator and the image-owned browser configuration to the build.
Playwright and Chromium are installed into the reviewed image. Dependencies are installed from the versioned lockfile
at image-build time, never during execution. Manifest-data changes fail closed
until the image is reviewed and rebuilt; newline/formatting changes are ignored.
`frontend_isolation` reports the separate image probe; `isolation.profiles`
combines both images' actual availability.

`ui_build` runs the real token generation and Vite production build.
`ui_component` loads the actual React trust row through Vite and renders explicit
0%, 30% and 91% confidence values, checking that the provider remains visible.
This is a fixed, narrow rendering check, **not** browser interaction, visual
coverage, calibrated-confidence verification or general acceptance coverage.
These profiles are separate: choose the relevant one and review its evidence.
Frontend phases allow 120 seconds, 768 MB memory, one CPU, 192 processes, 128 MB
work tmpfs and 128 MB temporary tmpfs. Ordinary profile limits are unchanged.
Offline networking, read-only dependencies/root, non-root execution, capability
removal and no-new-privileges remain enforced.

`ui_browser` additionally runs all four workspace browser suites using one
worker, no retries, a frozen configuration and local baked Monaco assets.
Empty/skipped/flaky/failing tests never yield a passing browser marker. Browser
results retain stable hashed test identities so previously passing tests cannot
silently disappear without blocking branch application.
Browser phases use 600 seconds, 1024 MB memory, 256 PIDs, 256 MB each for work/tmp storage,
and a 64 MB per-file limit for Chromium shared-memory buffers. This additive
profile uses Chromium's container-compatible non-sandboxed mode **inside the
unchanged outer Docker isolation**, not an extra browser sandbox or hostile-code
VM. It grants no additional container privileges, mounts or network access.
Existing images report `ui_browser` unavailable until reviewed/rebuilt.

UI JSX/TSX/CSS changes conservatively require `acceptance.expected_behavior`
and `acceptance.regression_tests` arrays, plus a regression-test edit in a named
workspace suite file. Read the tests and preserve their assertions; generated
test changes still require independent review. Example:

```json
{
  "expected_behavior": ["Not now closes the profile without saving or losing unsaved edits."],
  "regression_tests": ["tests/atlas-workspace.spec.js"]
}
```

Approval evidence and handoffs report separate build `passed|failed|not_tested`
and browser behavior `verified|failed|not_tested`. A browser failure can coexist
with a passed build. "Verified" covers recorded tests, not independent acceptance
or certification. Build-only proposals remain possible with behavior explicitly
`not_tested`; no host fallback fills missing browser coverage. Legacy evidence
defaults to `not_tested`. The optional `VITE_MONACO_BASE_URL` points the editor
loader to an operator-hosted `vs` directory; the isolated profile sets it to
baked assets served by Vite. Unset production behavior is unchanged.

**What HEAD refresh means:** the panel reads the selected backend checkout's
current committed HEAD and probes installed image profiles. New runs can obtain
fresh evidence through `owner_execution_status` without clicking the panel.
Refresh does not fetch/pull GitHub, switch branches, include dirty files, or
update your laptop. Connected clones use their separate Sync action. Existing
frozen approvals never move to a newer HEAD: a changed base requires a new
proposal and approval. A completed owner application creates a new local branch;
the selected checkout remains on its original HEAD until you explicitly choose
to integrate that branch. Prefer the run's recorded base/profile receipts to a
model's prose recollection of an older run.

Run recovery now permits the exact reread required after `edit_mismatch`, without
allowing a successful application to repeat. A truncated 4096-token decision can
retry once with an 8192-token ceiling and small-edit guidance; source-backed owner
validation/application decisions also allow 8192, while ordinary decisions stay
capped at 4096. Repair markers do not age recent source excerpts into the clipped
history budget. A duplicate tool decision is blocked and gets one corrective
decision per stream, never duplicate execution. Model diagnostics record the actual output limit. Supported
strict-schema providers receive typed argument objects for closed tool catalogs,
not JSON embedded in a string. Open-ended MCP catalogs retain encoded arguments
without losing freeform keys. Legacy envelopes remain accepted and all arguments still undergo registry
validation before approvals or execution. After verified application, the runner
emits a deterministic branch/commit/check receipt instead of asking the model to
execute again. Neither approval gate is bypassed.
When the requested goal includes validation/application, a successful frozen
preparation directly queues the normal validation approval; successful validation
directly queues the separate branch approval. These transitions use recorded
digests, not model-generated guesses, and do not spend another model decision.
Rejection, failure and cancellation never trigger the next phase. No action
executes merely because an approval was queued.
Owner runs requiring validation/application exclude the proposal-only tool from
model decisions; ordinary proposal-only and tenant workflows retain it. Managed
validation/application also reserves run/apply actions for the receipt-driven
runtime, not model-guessed execution identities. A failed validation requires a
corrected candidate prepared against committed source as a new frozen job, with
fresh validation approval and a separate application approval after passing.
Bounded failure excerpts persist in `progress.executions[].failure_excerpts`
even after recent observations are clipped. Scripted regression coverage proves
this control flow, not that a model will reliably produce the correct repair.
Failed
checks include bounded failure excerpts and a full-evidence endpoint, so repair
decisions can inspect real errors without truncating approval identity.

Chat/tutor reply `confidence` is now `null` with
`trust_metadata.confidence_status: "not_assessed"` when correctness is unmeasured.
Provider health, response length and citation counts never manufacture a
correctness probability. Old unlabelled heuristic scores render as **Not
assessed**; explicit scores in shared trust components are labelled **Reported
score (uncalibrated)**. Missing or invalid inputs are not converted to zero;
explicit zero remains zero. Sources without quality assessments show a source
count, not an invented grade. Learner exercise/mastery scores remain separate.

Coding runs can require `answer`, `proposal`, `validated` or `applied` via the
**Required result** selector or SDK `completion_goal` / `completionGoal`.
Models may raise but never lower that goal. The run's `progress` inventory records
inspected file ranges/hashes, frozen executions/checks, blockers, and actual
branch/commit evidence. The inventory survives continuation and restart.
Same-run `repo_recall_observation` retrieves a saved read only if the accessible
file's hash is unchanged. Prose alone cannot satisfy validation/application:
missing evidence ends as partial/incomplete, not successful work. Ordinary
answers say **Answered**, not **Worked**. Plan ticks remain model-written, not
independently verified. Existing decision and continuation limits stay unchanged.

Mammoth Paths exposes matching owner-only methods:
`owner_execution_capabilities` / `ownerExecutionCapabilities`,
`prepare_owner_execution` / `prepareOwnerExecution`,
`get_owner_execution` / `getOwnerExecution`,
`approve_owner_execution` / `approveOwnerExecution`,
`cancel_owner_execution` / `cancelOwnerExecution`, and
`apply_owner_execution` / `applyOwnerExecution`.
Application accepts `{repo, approvalDigest}` in JS, or keyword `repo` and
`approval_digest` in Python; use `execution.application.approval_digest`, not
`execution.approval_digest`. Its `/api/owner-executions/{id}/apply` endpoint is
owner/admin-only and returns the saved execution, including application state.
Existing clients and `mammoth.paths.v1` remain compatible. Tenant application and
paid access are not enabled; future monetization must enforce access on the backend.
Use a client timeout of at least 420 seconds for the synchronous approval request;
after a transport timeout, query the saved execution rather than reapprove it.

### Coding benchmark evidence

The real run-loop benchmark additionally measures inspection, proposal preparation,
both approval gates, validation, branch application and independent fixed
acceptance on disposable fixture repositories:

```powershell
python -m mammoth_os.workflow_benchmark --model --output-dir .mammoth\owner_benchmarks
```

Use `--provider openai` or `--provider deepseek` for explicit-provider smoke
comparisons, or `--provider coding` to measure the configured coding route.
Reports retain actual provider/model, usage, source-read/discovery counts,
recovery events, both approvals and independent acceptance. Provider preference
does not disable outage fallback; inspect the reported provider before comparing.
Three Python fixtures are not a representative UI benchmark or a reliability certification.

`--model` explicitly opts into provider credits; one repetition runs three tasks.
Only fixture `app.py` changes and the two scoped owner approvals can be approved
by this harness, never edits to acceptance tests or real repositories. Reports
persist statuses, blockers, branch/check evidence, model/tool call counts,
reported tokens, elapsed time and checkout preservation. Missing billing data
stays `null`, not an invented cost. This is measurement, not permission to enable
unattended execution. Fewer than 20 samples cannot satisfy reliability thresholds;
three small Python tasks do not establish UI or arbitrary-repository reliability.

```powershell
# No model credits: calibrates the real Docker harness with known solutions.
python -m mammoth_os.coding_benchmark --output-dir .mammoth\owner_benchmarks
# Opt-in model calls: three synthetic tasks per repetition; consumes provider credits.
python -m mammoth_os.coding_benchmark --model --repetitions 7 --output-dir .mammoth\owner_benchmarks
```

Reports identify their fixed source/prompt/test corpus with a SHA-256 fingerprint,
and persist baseline/candidate outcomes,
preservation-test regressions, success rate and p95 end-to-end latency. Models
receive source and task text, never the reference solutions or acceptance tests.
Missing/invalid/no-op proposals count as failures. Provider/model/usage/cost are
recorded only when actually reported; absent cost remains null.
The measured coding threshold is at least 20 samples across all three task types,
90% success, zero observed regressions and p95 at most 120 seconds. Reference mode
never qualifies as model reliability. Three synthetic Python cases are not
evidence for arbitrary repositories, and no report enables autonomous execution.
Isolation/approval/cancellation/recovery tests are separate safety evidence.

## Mammoth Mind tutor SDK (formerly ATLAS FAB)

MammothOS exposes an embeddable Python SDK surface for the tutor so it can be positioned as a standalone product inside another app, workflow, or developer tool.

### Install

```bash
pip install mammoth-os
```

For the FastAPI backend / UI stack:

```bash
pip install mammoth-os[server]
```

Core public imports:

```python
from mammoth_os import MammothMind, MammothMindConfig, ATLASSession
# Legacy names still work: AtlasFAB, AtlasFABConfig, AtlasFABError
```

Example embedding flow:

```python
from mammoth_os import MammothMind, MammothMindConfig

fab = MammothMind(
    MammothMindConfig(
        user_id="workspace:customer-123",
        adapter="openai",
        audience="developer",
        mode="tutor",
        metadata={
            "learner_context": {
                "goals": ["Ship a safer integration"],
                "preferred_pacing": "steady",
            }
        },
    )
)

lesson = fab.start_lesson("FastAPI authentication basics", difficulty="beginner")
result = fab.submit(solution_code="def solution(token):\n    return bool(token)\n")
runtime = fab.runtime_state()
```

Embeddable monetization strengths now present:
- clear SDK entry point (`MammothMind`, alias `AtlasFAB`)
- workspace-scoped learner identity support
- structured runtime-state surface for provider health/fallback visibility
- lesson, submit, next-lesson, and code-gen loops exposed programmatically
- lesson delivery surfaces: `fab.lesson_manifest()`, `fab.stall_status()`, `fab.next_lesson(require_mastery=True)` (raises `LessonGateError` until the exercise passes), and a `stall` block on every submission report

## Packaging posture for monetization

The Python package is now closer to a sellable SDK than a repo-only prototype:
- package metadata is declared in `pyproject.toml`
- runtime dependencies are explicit
- server-only dependencies live in the `server` extra
- CLI version is sourced from the package version
- public imports are centralized in `src\mammoth_os\__init__.py`

Highest-value next commercial upgrades after this:
1. Stripe or billing-provider integration
2. plan enforcement and entitlement middleware
3. hosted onboarding + tenant self-serve provisioning
4. SDK docs site + integration recipes for React, FastAPI, and internal tools
5. release-gate policy rollout in CI/CD for mandatory pre-merge checks

### What I meant by a billing / usage API

If you later want the product to warn users when they are close to limits, the backend needs some source of truth for usage.

Typical shape:

```json
{
  "plan": "pro",
  "period_start": "2026-08-01T00:00:00Z",
  "period_end": "2026-08-31T23:59:59Z",
  "usage": {
    "requests": 812,
    "request_limit": 1000,
    "tokens": 184200,
    "token_limit": 250000
  },
  "percent_used": 81.2,
  "warning_level": "elevated"
}
```

Then the UI can render a warning banner or usage meter before the limit is hit.

The backend now also exposes a preview-safe tenant usage response at:

- `GET /api/billing/usage/current`

It is intentionally labeled as preview metering until hosted billing tables are wired.

## Production auth + tenant blueprint

The repo now includes a production-oriented Supabase tenant/auth scaffold at:

- `.mammoth\supabase_tenant_auth.sql`

This layer is intended to sit around your existing `atlas` and `mammoth` product tables rather than replacing them.

What it adds:
- tenant ownership (`public.tenants`)
- tenant membership and roles (`public.workspace_memberships`)
- workspace/account containers (`public.workspace_accounts`)
- tenant settings and feature flags (`public.tenant_settings`)
- usage metering and rollups (`public.usage_events`, `public.usage_rollups_daily`)
- policy acceptance and audit trails (`public.policy_versions`, `public.policy_acceptances`, `public.audit_events`)
- owner bootstrap function for your current Supabase user (`public.bootstrap_tenant_for_user(...)`)

Recommended execution order:
1. Run `.mammoth\supabase_schema.sql` if your baseline tables are not already present.
2. Run `.mammoth\supabase_tenant_auth.sql` in the Supabase SQL Editor.
3. Sign in with the account you want to be the admin/owner.
4. Call `select public.bootstrap_tenant_for_user('MammothOS', 'mammothos');`
5. Wire the backend to read tenant membership before exposing admin controls or shared dashboard state.
6. Only then turn on public domain access.

## What you have now

You are no longer at “prototype with cool features only.” You now have:
- a stronger ATLAS SDK / FAB package surface
- safer provider fallback behavior
- auth-guard and tenant-state regression coverage
- a production tenant/auth SQL blueprint
- clearer separation between customer-facing pricing and internal operator/admin controls
- documentation that points toward hosted SaaS + embeddable SDK monetization

That means the product is much closer to a real platform, but it still needs final live-environment wiring before you should treat it as broadly public.

## Biggest launch blockers to watch for

The most likely things that can hinder a clean launch are:

1. **Auth not fully enforced**
   - If route guards are incomplete, a user could see dashboard shells they should not see.
   - Fix: require authenticated tenant context before loading private state.

2. **RLS/policy mismatch in Supabase**
   - If SQL policies and backend assumptions diverge, users may see empty data, permission errors, or cross-tenant leakage risk.
   - Fix: test owner/admin/member flows explicitly after running the migration.

3. **Placeholder metrics shown in production UI**
   - Finance, usage, or health views should not imply real billing if they are still local/demo-only.
   - Fix: gate incomplete metrics behind “demo/local-only/internal” labels until real usage data is wired.

4. **Provider credits / key exhaustion**
   - The runtime now degrades better, but the user experience still needs friendly messaging and warnings at the product layer.
   - Fix: surface usage and provider status through a real backend endpoint.

5. **Public vs admin route confusion**
   - Marketing pages can be public; dashboards and operator tools should require login and tenant membership.
   - Fix: keep a hard route split between public site, customer app, and internal admin screens.

## Recommended next product steps

### Next step inside the product
1. Run the Supabase migration.
2. Bootstrap your current account as owner/admin.
3. Wire real tenant lookup into login/session handling.
4. Add a real `/api/billing/usage/current` response backed by tenant usage tables.
5. Gate the UI so anonymous visitors only see landing/pricing/compliance pages.

### Next step after that
1. Connect billing (Stripe or equivalent).
2. Define plans, limits, and entitlements.
3. Publish terms, privacy, refund, and acceptable-use policies that match actual behavior.
4. Create a hosted onboarding flow for new tenants.
5. Package the SDK with install docs, examples, and a stable versioned API contract.

## Legal / monetization checklist

Before broadly charging customers, make sure you have:
- real authentication and tenant isolation
- a privacy policy aligned with stored user/session data
- terms of service / acceptable use policy
- billing/refund language that matches your checkout flow
- a support/contact path
- a clear statement of what is beta vs production
- a defined data-retention and admin-access posture

This is the difference between “cool software” and “legitimately monetizable software.”

## Current production-readiness snapshot

This build now includes the completed reliability, eval, tutor-outcome, and SDK contract hardening pass. The core platform has moved from "strong prototype" into "controlled production candidate" status.

### What is now enforced

- Runtime fallback states are explicitly degraded instead of silently treated as ready.
- Health/readiness surfaces fail closed when core dependencies are not healthy.
- Release readiness includes an ATLAS eval gate so weak or missing eval history blocks green release status.
- Tutor outcomes are measurable through explicit learner signals (`learning_signal`, `progress_score`, `outcome_summary`).
- SDK snapshots expose stable contract and tenant/usage metadata for embedders.

### Remaining gap is execution polish, not core wiring

- CI enforcement for release-gate policy should be mandatory on every merge path.
- UI polish on lower-traffic pages still needs one final visual pass.
- Hosted billing provider integration is still pending (current usage endpoint is intentionally preview-safe).

## Start the stack

One-click (Windows):
```powershell
cd C:\Users\runni\mammoth_intro_ai.worktrees\agents-mammothos-atlas-agent-system
.\start-mammothos.bat
```

This opens two terminal windows automatically:
- Backend (FastAPI on port 8000)
- Frontend (Vite on port 5173)

If you see `WinError 10013`, port 8000 is usually already occupied. Stop the listener and retry:
```powershell
$conn = Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object -First 1
Stop-Process -Id $conn.OwningProcess
.\start-mammothos.bat
```

Backend:
```powershell
cd C:\Users\runni\mammoth_intro_ai.worktrees\agents-mammothos-atlas-agent-system
.\.venv\Scripts\Activate.ps1
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:
```powershell
cd C:\Users\runni\mammoth_intro_ai.worktrees\agents-mammothos-atlas-agent-system\ui\mad-architecht-command-center
npm run dev
```

UI: http://localhost:5173

System health only checks the Vite dev server when auth is off (local dev), using `MAMMOTH_DEV_SERVER_PORT` (default 5173). A stopped dev server shows as a warning and never blocks the runtime health gate; production does not report it at all.

### Backend layout

`api_server.py` is still the single entrypoint (`uvicorn api_server:app`). It holds app setup, middleware helpers, auth/access helpers, and shared state. The HTTP route handlers live in [`server_routes/`](server_routes/), grouped by feature:

| File | Routes |
| --- | --- |
| `runtime_routes.py` | auth middleware, `/api/run`, `/api/plan`, `/api/plan-execute`, health/status, tasks, activity, approvals, snapshots, observability, terminal, memory, flashcards |
| `atlas_routes.py` | `/api/atlas/*` tutor flows and `/agent/atlas/run` |
| `mammoth_routes.py` | `/api/mammoth/*` chat, threads, files, repo sources, agent runs |
| `team_routes.py` | `/api/team/*` workflow templates, approval policies, runbooks |
| `workspace_routes.py` | workspace artifacts/run history, notes, build log, notifications, onboarding, beta feedback, sales log |
| `governance_routes.py` | modules, MCP, RAG context, audit, operator health, entitlements, billing, account, DOCX downloads |

These files are loaded into `api_server`'s own namespace at import time, so `api_server.run_agent` and other handlers stay importable and monkeypatchable from tests. They are not standalone modules: put shared helpers in `api_server.py` (or a real `mammoth_os` module) and only route handlers in `server_routes/`.

## Audit export

- Backend audit API: `GET /api/audit`
- CSV export: `GET /api/audit/export`
- UI path: Diagnostics page → **Export CSV**

## Agent Workspace

The Agent page opens on a calm workspace instead of a console:

- **Roster**: agents in plain language (what each one is for), with a live Ready / Working / Offline status from `/api/agents`. System agents are hidden behind **Show system agents**.
- **Agent chats**: each agent keeps its own thread (stored locally, last 30 messages). Follow-ups send the last 8 turns as `payload.history`, so the agent remembers the conversation. Start a message with `@reflection`, `@coding`, `@research`, etc. to send that message, with the thread's context, to another agent.
- **Team run**: describe an objective, preview the plan (`POST /api/plan-execute` with `dry_run: true`), untick steps you don't want, then run the selected `step_ids`. Each step sees earlier results, and a final synthesis step returns one answer (`summary`). Every step expands to show its full output.
  Education objectives use Tutor, Research, Reflection and synthesis without
  unrelated market/publishing/custodial steps, even under the autonomous profile.
  Explicit software implementation can add Coding; coding profiles stay intact.
  Routing is conservative lexical policy, not semantic correctness certification.
- **Structured planner** (`POST /api/plan`): complete task JSON must contain
  unique IDs, explicit titles, object inputs and earlier-only dependencies.
  Education DAGs restrict agents to research/reasoning/search/curriculum plus
  explicit software Coding. Malformed/truncated/prose/provider-failed outputs
  return `502 / invalid_plan`, an empty task list and failed quality before
  dispatch; they never become guessed agent-mention actions or filler titles.
  Retry is explicit. Model reasoning remains a separate `reasoning_trace`.
  Saved curriculum planning preserves actual lesson identity and duration
  normalization. Structural validity does not prove agent availability or
  educational correctness; existing approvals and repo isolation remain.
- **Advanced**: creativity (temperature), "Preview file changes before applying", and **Classic console** (the original intent/payload console, unchanged).
- **Coding with a repository**: the Coding agent's header has a repository picker. It shares Mammoth Mind's selection, and the platform repo is listed only for the owner. With a repository picked, coding requests run through the Mammoth Mind agent loop (`POST /api/mammoth/runs`, `surface: "agent_workspace"`, `task: <intent>`). The agent lists, reads, and searches the real files, shows its run timeline, and returns proposed diffs (user repos also get a local branch + patch). Nothing is applied or pushed. With "Preview file changes" on, every non-read tool waits for Approve/Reject. **Stop** cancels a running request. Patch / Refactor / Review with no repository and no pasted code asks you to pick one instead of guessing.
- **Changes** and **History & memory** (Agents page header) replace the old right-hand rail, so the workspace uses the full width. **Changes** shows a count badge when file-change previews are waiting and opens a slide-over with **Pending Approvals** (Approve / Delete) and **Rollback Snapshots** (Restore). **History & memory** holds Run History and Autonomous runs (both with Replay) plus Workspace Memory. Reasoning traces, plan progress and live activity now appear inline on each run, in Run Review and in Task Inbox. Panel data refreshes every 2.2 s only while a panel is open; otherwise agent status and the Changes badge refresh every 10 s. The **Classic console** keeps its original right rail.
- **Layout**: the workspace card grows with the conversation (the page scrolls, nothing is clipped). On desktop the roster stays pinned on the left and the composer stays docked at the bottom. On phones (under 768px) the roster becomes a swipeable chip bar, the side panels stack below, Enter inserts a new line (tap Send to send), and the app sidebar closes after you pick a page.

Conversation history and earlier step results reach the model through a scoped **background channel** (`mammoth_os.llm_client.conversation_context`), never by rewriting the agent's prompt. Template-based agents (reflection, tutor flows) treat the prompt as a topic, so stuffing transcripts into it would leak them into the output.

## Private document uploads and learning materials

Chat and ATLAS share `mammoth.documents.v1` ingestion. Both capability endpoints
(`GET /api/mammoth/files/capabilities`, `GET /api/atlas/files/capabilities`) expose
the actual supported extensions, limits, and the caller's combined raw-file usage.
Defaults are **50 MiB per file**, **500 MiB raw-file storage per user**, and
**200 files** across both libraries. Configure positive values with
`MAMMOTH_UPLOAD_MAX_BYTES`, `MAMMOTH_UPLOAD_STORAGE_BYTES`, and
`MAMMOTH_UPLOAD_MAX_FILES`. Reverse proxies must permit at least the configured
file limit plus 1 MiB multipart overhead and sufficient processing time.
The droplet deploy script installs dependencies in the running backend's Python
environment and updates only the uniquely identified Mammoth site's `/api`
nginx proxy location, preserving its upstream. It validates nginx and restores
its own changes on validation failure. Set `MAMMOTH_PYTHON` or
`MAMMOTH_NGINX_SITE` when discovery is ambiguous; deployment fails explicitly
rather than modifying unrelated sites.

Supported readers: PDF, DOCX, PPTX, XLSX, HTML/HTM, UTF-8/BOM-marked UTF-16
text, Markdown, CSV, JSON, YAML, TOML, RST, logs, and the listed source-code
formats. PDFs retain page numbers, slides retain slide numbers, spreadsheets
retain sheet/row locations, DOCX retains ordered paragraph/table blocks, and
text retains line ranges. Formulas are not recalculated; spreadsheets expose
saved cached values. Embedded images are not transcribed, and DOCX block numbers
are not rendered page numbers.

Uploads stream into private staging files, with multipart-body limits before
spooling, transactional SQLite quotas, two concurrent ingestion slots per server
process, and separate reader processes with a 60-second timeout. Linux readers
also have a 1 GiB address-space limit. Extraction is bounded to 2 million
characters / 2,000 units; ZIP containers have expansion, encryption, macro,
and XML-entity checks. These are resource bounds, not a complete malware scanner
or an OS sandbox. Never execute uploaded code or active HTML.

The whole extracted document is split into source-located sections. Chat,
Mammoth Mind runs, and ATLAS retrieve relevant sections by lexical matching
(or opening sections when no terms match), instead of only using the first
8,000 characters. Ask about a concrete topic or `page 120` / `slide 12`.
This is bounded retrieval, not semantic search or proof that the model's answer
is accurate. Chat uses up to four attached files; ATLAS uses up to six.

The UI shows transfer progress, processing, extraction warnings, cancellation,
and retry. ATLAS offers searchable section previews; chat's **Manage saved files**
opens the same scoped preview/reuse/delete library so detached files can be
removed to reclaim quota. Removing an attachment alone does not delete storage.
`ready` describes text
extraction, not factual quality; `partial`, `needs_ocr`, `empty`, and
`legacy_preview` remain visible. Scan-only PDFs need OCR, **not enabled in this
release**. Neither OCR, audio/video transcription, nor external document services
are invoked or billed. Cancellation after server processing starts may finish
server-side: refresh the library before retrying.

Old upload indexes migrate without rewriting their saved previews. Re-upload
legacy files for full extraction. Corrupt indexes or ambiguous legacy user-folder
ownership require operator repair, never a silent empty library. New storage
uses hashed user folders, and list responses do not expose host filesystem paths.
Back up `.mammoth/documents/` along with legacy upload folders before deployment.

## Safety-first agent workflow

- In the Agent page (Advanced → Preview file changes before applying, or Preview first in the classic console), keep previews enabled for coding edits.
- The Agent Console prompt box accepts short one-line prompts, but best results come from: objective + scope + constraints.
- The Command Center now includes an in-app **Manual** page with terminal examples and prompt patterns for new users.
- Review changes in **Changes → Pending Approvals** (Agents page header; the Classic console keeps them in its right rail).
- Approve only what you want applied.
- If needed, undo with **Changes → Rollback Snapshots** (Restore button).
- Non-coding state mutations now support preview/approval too:
  - `POST /api/atlas/onboard` with `approval_mode: true`
  - `POST /api/atlas/learner/reset` with `approval_mode: true`
  - `POST /api/atlas/reset` with `approval_mode: true`

## CodingAgent hardening pass (v1.2)

Latest improvements to CodingAgent stability and error handling:
- **Asyncio safety**: Replaced unsafe `asyncio.run()` calls with a robust `_run_async()` bridge that detects and handles already-running event loops gracefully.
- **Structured logging**: Wired `log()` method to the standard Python `logging` module for consistent log levels and operator visibility.
- **Exception safety**: Added proper exception handling in async task execution and commit operations with detailed logging for debugging.
- **Type hints**: Fixed Python <3.10 compatibility by using `Union` instead of `|` type syntax.
- **Input validation**: Added guards for empty file lists in `commit_changes()` to prevent silent git errors.

These changes reduce the risk of runtime `RuntimeError` exceptions when CodingAgent is called from async contexts or when handling large workloads.

## Source-aware output contracts

The runtime now treats output quality as a real contract instead of a loose text blob.

- `coding` responses preserve structured payloads instead of flattening everything to raw strings.
- Documentation requests require a real path or source snippet; placeholder values like `unknown` now fail with a `needs_context` result instead of fake docs.
- `brand_voice` accepts explicit modes such as `stakeholder_summary`, `tutorial_copy`, and `rewrite_with_constraints` so the tone and audience stay consistent.
- UI prompts should specify: objective, target file or scope, audience, and guardrails.

This keeps the output source-aware, easier to validate, and far less likely to devolve into generic product copy.

### Research output hygiene (`src/mammoth_os/research_quality.py`)

- **Reasoning never leaks into deliverables.** `<think>`/`<thinking>`/`<reasoning>` blocks (closed, dangling, or cut off mid-way) and task meta-lines ("Okay, let me…", "Here's the section:", "Let me know if…") are stripped from research JSON, long-form sections, and conclusions. Stripped reasoning is returned separately as `reasoning_trace` (research) or per-section `trace` (long-form).
- **Retrieval context and relevance.** Research payloads retain their structured lesson context through API and registry routing. "This curriculum" resolves to the active subject/title; without that context it asks for the subject. The Research agent uses a strict relevance filter (`research_evidence`) and requires excerpts, rather than retaining off-topic search hits when evidence is sparse. Generic education words do not establish nutrition relevance. Provided excerpts remain explicitly user-supplied and unverified. Other consumers of the general-purpose hygiene helper retain its existing weak-source behavior.
- **Entity disambiguation.** When the query names an entity (quoted phrase or multi-word proper noun), sources that don't mention it in full are ranked below those that do. They are never dropped, because the entity may just be a qualifier.
- **Dedupe.** Near-duplicate findings, key facts, key points, next steps, and concepts are collapsed. Long-form documents drop paragraphs that repeat an earlier section.
- **Completeness.** Long-form sections retry once when the model fails or returns nothing but reasoning. Text cut off mid-sentence is trimmed back to the last complete sentence. A section that still fails is marked `status: "failed"` with empty content instead of embedding an error string in the document. The `quality` block reports failed, retried, and trimmed sections, duplicates removed, and sources filtered.
- **Evidence contracts.** Brief, summarize, and curriculum-research modes also return `findings[]` with real source labels and exact supporting excerpt quotes. Unknown citations and invented quotes are excluded from findings and kept separately as unverified claims; summary/facts derive from accepted linked findings. Coverage measures checked links, not factual correctness. No minimum finding count, prompt-as-source, operator identity, stale query year, or training-knowledge filler. Missing evidence returns `insufficient_evidence`.
- **Honest limits.** Exact excerpt and label checks do not prove claim entailment or independently verify sources. Contradictions are `not_assessed`, not inferred from opposing words. Long-form prose remains a review-required draft with unverified claim links; it respects supplied sources and `allow_web_lookup` just like briefs. Numerical agent confidence is not calibrated; the legacy API numeric field is zero for research/coding with `confidence_basis: "not_calibrated"`, while their artifact confidence is null. UI displays actual excerpts and safe source links, including excluded claims and evidence gaps.
- **Task selection and supplied text.** Research a topic produces a research brief; Research a learning path retains the explicit curriculum-research mode. Summarize with `content` or a pasted multi-line/long document treats it as supplied text and never searches that text on the web.

### Coding proposal quality

Existing-file modifications require original source, even from **Write code**:
select a connected repository and target, or paste a complete fenced original /
supply file contents. Four lines of instructions are not pasted code. Repository
requests retain the existing policy-checked proposal-only loop; there is no
implicit platform repository or tenant host access. Source-supplied generation
preserves `patch_existing`, includes the original in the model prompt, and derives
a named unified diff from that exact source. Python implementation/test syntax is
AST-parsed without executing model code; generated tests explicitly remain
`not_run`, and integration is `not_verified`. Syntax failure or prose-only output
is an error, not completed work. Generated test/docs blocks do not inflate a
confidence score. Standalone tutor exercises retain their `solution()` contract;
existing modules preserve their own interfaces. These checks do not establish
behavioral correctness or authorize application of a patch.

## Additive agent bridge (Copilot Tasks optional)

MammothOS supports the existing registry-backed runtime and an optional external HTTP bridge.
This is an upgrade-only path: it adds an explicit task runner surface without replacing the native agent runtime.

- `POST /agent/atlas/run` → routes to the runtime `tutor` agent
- `POST /agent/coding/run` → routes to the runtime `coding` agent
- `POST /agent/shell/run` → executes a shell command in the repo worktree with a safe subprocess wrapper

These routes are intentionally additive and can coexist with `GET /api/agents`, `GET /api/modules`, and the plan/execute APIs.

## Copilot Tasks integration appendix

This is the recommended integration model when an external orchestrator such as GitHub Copilot / Copilot Tasks needs to call into MammothOS without bypassing the native runtime.

- Keep MammothOS as the source of truth for agents, workflows, and state.
- Use Copilot as a conductor, never as the direct file editor.
- Route work through `tutor`, `coding`, and `shell` agent endpoints rather than editing the repo directly.
- Preserve preview-first approval, rollback, and observability.

Example mapping:
```json
POST /agent/coding/run
{
  "objective": "Apply MammothOS Command Center theme to NotesPanel.",
  "context": {
    "files": [
      "ui/mad-architecht-command-center/src/notes/NotesPanel.tsx",
      "ui/mad-architecht-command-center/src/index.css"
    ],
    "plan_profile": "atlas_first",
    "approval_mode": true
  }
}
```

This aligns with the actual runtime contract in `api_server.py`: the external bridge is additive and the real work remains in the runtime-backed agent system.

## Autonomous run contract (Phase 5 prep)

- `GET /api/autonomous/runs` returns a unified run feed from:
  - orchestrator plan/execute tasks
  - ATLAS plan history
- Response includes:
  - `contract_version`
  - `profiles` (`atlas`, `coding`, `balanced`, `autonomous`)
  - aggregate `summary`
  - recent `runs` with status/progress/source
- Agent Console now renders an **Autonomous Runs** panel using this endpoint.

## Local AI vs cloud routing

MammothOS supports a safe multi-provider workflow without failing hard when an account is empty or a key is invalid.

Current selection order in `src/mammoth_os/llm_client.py`:
1. `MAMMOTH_LLM_ADAPTER=local` → deterministic local adapter
2. `MAMMOTH_LLM_ADAPTER=ollama|hermes|codellama|...` → local Ollama model path
3. `MAMMOTH_LLM_ADAPTER=deepseek|deepseek-api|deepseek-cloud` → DeepSeek cloud reasoning path
4. `MAMMOTH_LLM_ADAPTER=openai` → OpenAI coding path
5. `DEEPSEEK_API_KEY` present → DeepSeek, then OpenAI, then Ollama/local fallback
6. Only `OPENAI_API_KEY` present → OpenAI (`gpt-4o-mini` by default), then Ollama/local fallback
7. Ollama running locally → Ollama auto-detect
8. fallback → local deterministic adapter

Graceful-fallback behavior:
- If DeepSeek or OpenAI rejects the request for quota/billing/auth reasons, the runtime falls back to the next viable provider.
- This is the safe path when a provider runs out of credits or a key has expired.
- The app remains usable rather than crashing with a terminal failure.

Recommended split:
- DeepSeek reasoning / ATLAS tutor / long-context coaching
- OpenAI `gpt-4o-mini` for coding generation and code-review work
- Ollama or local echo only when cloud providers are unavailable

The Coding agent and run goals `proposal` / `validated` / `applied` now explicitly
request the coding workload, including when started through either Paths client.
Coding defaults to OpenAI → DeepSeek → Ollama → local, using `OPENAI_MODEL`
(`gpt-4o-mini` by default). Operators can set
`MAMMOTH_CODING_LLM_ADAPTER=deepseek` to retain DeepSeek → OpenAI → Ollama → local
for coding independently of tutor/general routing. Only `openai` and `deepseek`
are accepted; invalid settings fail explicitly. Explicit per-call adapter choices
and process-wide local/Ollama modes remain authoritative. The ambiguous legacy
`deepseek` alias uses cloud when a DeepSeek key exists, otherwise retains its
local-model meaning; `deepseek-cloud` and `deepseek-coder` are unambiguous.

Coding discovery supports `repo_search` with an exact relative `path`. After two
discovery calls containing source locations, search/list/readiness are temporarily
removed from the next model decision so it reads inspected evidence, prepares
an already-inspected edit, or reports a blocker instead of spending the whole
budget searching. This checkpoint does not choose a file, fabricate a plan result,
raise tool privileges or increase the eight-step budget.

If you want to prefer local models even when cloud keys exist, set:
```powershell
$env:MAMMOTH_LLM_ADAPTER = "hermes"
# or
$env:MAMMOTH_LLM_ADAPTER = "ollama"
```

## Sandbox fallback (until kernel update)

If Docker sandboxing is unavailable, force subprocess mode:

```powershell
$env:FORCE_SUBPROCESS_FALLBACK = "1"
# or
$env:SANDBOX_RUNNER_MODE = "subprocess"
```

This keeps development moving but is less isolated than Docker sandboxing.

## Detailed manuals

- `ATLAS_MANUAL.md` — full CLI + UI operating guide
- `ui\mad-architecht-command-center\README.md` — UI-specific workflows

## UI terminal note

- The Command Center terminal supports safe `python -m cli.main ...` flows, including `atlas code` and `atlas ui` commands.
- Long-running ATLAS coding/UI commands now receive extended backend timeouts so they behave more like a real operator terminal session.

## Lessons + curriculum note

- **Lesson manifest** (`mammoth.lesson_manifest.v1`): `/api/atlas/status`, `/lesson`, `/next`, and `/back` return `lesson_manifest` with prerequisites, sample input, expected output, and "done when" criteria. All of it comes from the real lesson/exercise (asserts in the test scaffold, rubric lines, earlier lesson titles). Missing data stays empty instead of being invented.
- **Stall telemetry** (`mammoth.lesson_telemetry.v1`): every submission records per-lesson attempts, consecutive failures, and a normalized error fingerprint in `lesson_telemetry`. `/api/atlas/submit` returns `stall` (`stalled`, `reasons`, one `suggestion`); the status payload carries `lesson_stall`. The thresholds are 3 failures in a row, the same error twice, or 20 minutes without progress.
- **Comprehension gate**: `POST /api/atlas/next` returns `{"status": "gated", "gate": {...}}` when the current exercise has not passed. Send `{"override": true}` to move on anyway; overrides are written to the audit log. Lessons without a gradable exercise are never gated.
- **Retrieval hygiene**: lesson chunk retrieval drops empty and duplicate/near-duplicate chunks before taking the top-k, and labels each chunk with `source_label`.

- `GET /api/atlas/modules` now exposes a broader module catalog across outdoors, emergency, business, health, technology, creative, and life-skills tracks.
- The Lessons page includes an **Adaptive UI** toggle that morphs the exercise surface by lesson type (`code`, `knowledge`, `writing`, `checklist`, `scenario`).
- Until deeper non-code submission contracts land, non-coding lessons still use a Python-backed helper exercise under the hood, but the prompt/test scaffolding is now topic-aware instead of a one-size-fits-all generic coding task.

## Scope + suggestions (credit-efficient path)

### Current scope
- Keep ATLAS + MammothOS stable as a tutor-first system with diagnostics, audit history, and operator logging.
- Prioritize quality and continuity over adding paid features too early.
- Keep product language compliance-safe (no overclaims, no patent claims unless filed).

### Suggestions (in order)
1. Expand **lessons domain architecture** (lowest credit cost, mostly UI/state wiring).
2. Expand **health page** into personal + system health (medium cost).
3. Expand **finances page** into personal + business tracking (medium-high cost).
4. Defer payment wiring until core learning loops and trust surfaces are locked.

### Keep in mind
- Always start from `.\start-mammothos.bat` first to avoid false "disconnected" states.
- Port 8000 conflicts can mimic backend failures; clear listeners before retrying.
- Track meaningful work in Build Log + Diagnostics so progress is provable and reviewable.
