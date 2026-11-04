# 🐘 ATLAS Manual — MammothOS CLI Reference

> **Quick rule:** every command starts with `python -m cli.main atlas …`
> Run this from the repo root. **Your `.env` file is now loaded automatically** —
> no more setting env vars by hand in every terminal.

## Production-readiness snapshot

### Durable runs, health and runtime token controls

Run API streams/approval/continuation use OS-released cross-process leases.
Checkpoints use atomic replacement, fsync and saved revisions; stale writers
cannot silently overwrite newer evidence. Active/approval-pending runs are not
evicted by recent-run retention. Ordinary interrupted runs become explicit
non-continuable failures on saved-state read, never automatic tool/model replay.
Cancellation is durable and cooperative, not a provider stop or rollback.

Provider keys and agent discovery do not prove availability. Diagnostics and
Modules separate configuration from timestamped observations, stale after five
minutes. Health refresh does not buy a model probe.

Settings > Runtime usage controls sets an optional UTC daily token-admission
ceiling for the signed-in login across accounts. Zero blocks covered calls;
empty removes the ceiling. SQLite serializes reservations across workers.
Provider-reported usage replaces allowances; failures, absent usage and killed
workers retain reservations. Limits are not retroactive and resetting them
does not erase usage. Covered calls go through the shared completion helper or
standard OpenAI/Ollama text adapters. Embeddings, custom paths, internal SDK
retries, provider invoices and calls outside the hosted request context remain
outside separate accounting. This is not dollar/Copilot-credit spend or
authoritative multi-member tenant billing. All workers must share durable disk.

### Shared state and tenant estimated-dollar controls

The optional shared backend adds atomic compare-and-swap for generic JSON
collections, preserving independent keyed appends and rejecting conflicting
record edits with HTTP 409. Corrupt records return a storage error rather than
an empty success. Legacy approvals are durably claimed before execution; an
interrupted claim is an unknown outcome, not permission to replay the action.
Local learner saves also reject conflicting changes and retain deletion fences.
Onboarding, notifications, execution logs and account-deletion request records
also use the shared store. Conflicting edits require reload; unreadable data no
longer silently becomes an empty record. Requesting deletion is not verification
that all copies, provider data or backups have been erased.
Generated research documents can optionally share ownership and binary downloads
through PostgreSQL. Only the owner or an administrator can download; legacy
unowned files remain admin-only. Failed publication preserves draft text, marks
the document unit failed and omits the download link without rerunning the model.
The local backend remains the default; use the documented backup/import/rollback
procedure before changing production storage.

Settings > Tenant usage controls exposes verified active memberships and shared
UTC-day token/estimated-USD ceilings. Only tenant owners/admins can change policy;
changes are audited. Private login ceilings remain additive. Exact expiring
operator-reviewed prices are required when a dollar ceiling is active. Unknown
usage retains reservations; unknown historical prices block dollar-capped
admission. Reported overruns are retained and block later calls, not hidden.
These are conservative estimates, not invoices, Copilot credits or full paid
service coverage. Ordinary/recursive run checkpoints and private login ceilings
also have optional PostgreSQL backends, with session-released execution leases,
durable cross-worker cancellation and explicit per-owner import/export/rollback.
Learning request-count controls can also explicitly use PostgreSQL, preserving
their limits, account-scoped cancellation, retained operations and existing API.
This does not migrate learner recovery/erasure state or enable replicas.
Document metadata, raw uploads, indexed sections and saved reviews additionally
have a coordinated optional PostgreSQL backend. Quotas and deletion are atomic;
unknown review calls are not replayed. Bounded raw bytes live in the database
and require capacity planning. Migration/rollback verifies per-file hashes.
Their existing API contracts and unknown-outcome protections remain unchanged.
See [shared runtime operations](docs/shared_runtime_operations.md).
Full independent-replica readiness and production migration remain explicit
rollout gates; this release does not automatically change host configuration.

### Detailed explanations and Guide freshness

The [MammothOS Feature Handbook](docs/public/mammothos_feature_handbook.md)
explains feature choices, recursive-review use/avoid cases, costs, document
coverage and approval evidence in plain language. The Guide reads bundled public
documentation per request and includes a timestamped capability snapshot for the
current caller, not operator logs or verified service health. Its content hash
identifies the docs bundle, not a release. Deploy updated files to update the
running Guide; no platform repository sync or paid health probe is performed.

### Document coverage and recursive review budgets

Both file libraries offer **Browse indexed text** with bounded previous/next
section pages alongside topic search. Selected/indexed counts do not mean the
model reviewed the whole file; extraction/OCR omissions remain visible. Chat's
three-section overview retains its end-of-document sample instead of dropping
the fourth sample from a larger selection. Agent tools can read further sections.
Paths clients expose the same private paging through `read_document` /
`readDocument`; these reads do not invoke a model.

Recursive review uses smaller planner/critic output allowances without raising
the configured token ceiling. Its timeline separates reported usage from the
conservative byte-based input allowance and explains admission stops. A completed
executor draft survives a later review failure under an explicitly unverified
disclosure. Oversized role context stops instead of silently clipping its tail.
Known official OpenAI models now use local tokenizer text counts with conservative
envelope/schema allowances, per actual provider attempt; other models/endpoints
retain a labeled byte bound. These are admission allowances, not billed usage or
exact server-side chat counts. No fix for an uninspected hosted run is claimed.

**Indexed document review** in a file preview creates a saved review without
model calls. **Review next batch (uses model credits)** explicitly assesses up to
three sections. Source-hashed summaries and exact source quotes persist per
section; reopening/reloading does not call models. Repeat deliberate batches
until all indexed sections are assessed or the review clearly stops partial/
blocked. A default 64,000 reported-token ceiling is shared across batches; each batch is
limited to 180 seconds. Unknown provider outcomes and hard-cap stops are not
replayed. Deleting the source removes its reviews. This is indexed coverage,
not factual verification, original-file completeness or recursive critique;
use a separate explicit synthesis batch to combine saved assessments. Each
confirmed batch runs up to three groups of at most eight inputs, checkpointing
intermediate summaries and source citation lineage until every indexed
assessment has been traversed. This is lossy summary synthesis, not a full-source
reread, verified entailment or truth. Quotes remain available on source sections.

The review's default lifetime ceiling remains 64,000 reported tokens. Confirming
a larger total ceiling (maximum 128,000) is audited and model-free, preserves
usage and requires the expected current ceiling. A stale confirmation fails;
uncertain/invalid calls cannot be unlocked. Only known cap stops can resume at
their checkpoint. Each subsequent paid batch still needs its own click.
Ordinary recursive-run limits and broader tenant spend controls are unchanged.

The preview and both Paths SDKs now reject malformed nested saved-review
evidence: mismatched identity/source references, impossible coverage, invalid
usage/history and broken synthesis traversal/citations. They preserve legitimate
partial, active, blocked and over-ceiling records rather than inventing success.
After an error, paid controls remain unavailable until a model-free saved-state
reload succeeds. If the initial list is invalid, use **Reload saved reviews
(no model call)**; no replacement review is silently created. These are structural
checks, not factual verification or permission to replay unknown provider work.
Real-socket tests with offline models cover assessment timeout plus abrupt
worker restart in both installed clients, not deployed proxy/provider behavior.

### GitHub Desktop handoff for approved coding work

After branch application, the coding timeline and owner pilot card offer
**Prepare GitHub Desktop handoff (no push)**. It reads current execution evidence,
shows the branch/commit and offers an approved patch download. For a recorded
GitHub repository, **Open repository in GitHub Desktop** launches the installed
app with browser permission. Only confirm the local-branch checkbox if the branch
already exists in your local clone or on GitHub, then use **Open prepared branch
in GitHub Desktop** and verify its commit before publishing. The checkbox is your
acknowledgment, not automatic verification of local state.

Use Desktop's Publish branch / Push origin and Create Pull Request, then review
checks and merge on GitHub. Nothing launches on card refresh, pushes or merges
automatically. If Mammoth runs remotely, its unpublished branch is not on your
laptop. Use **Confirm private branch bundle download (no push)** to transfer
the exact applied commit. Its checksum is verified before download; it contains
only the delta and requires the recorded base in your existing clone. Follow
the card's Git bundle verify/fetch/commit-comparison instructions with a local
Git-capable tool/operator. No commands run from the card, and the current checkout
stays unchanged. Desktop does not directly import bundles; fully terminal-free
import still needs a local helper. A checksum is not a signature or code review.
Downloading a patch alone does not preserve the backend commit. Private
bundles/patches contain source; do not share them casually.
**View approved branch on GitHub (after publishing)** opens the exact branch as
a website fallback; it does not push and may show not-found before publishing
or without access. If no valid GitHub identity
was recorded, no repository link is invented. If the browser cannot open Desktop,
open it manually and select the correct clone.

### Focused ATLAS workspace

ATLAS uses four workspace views: Lesson, Tutor, Agents and Curricula. On phones,
the module browser replaces the lesson pane while open; **Back to lesson**
returns without discarding the current exercise draft. **Read** and **Practice**
jump within one scrollable lesson rather than marking any work complete.

**Reading options** provides text-size, line-spacing, focused-reading and adaptive
exercise controls. Focused reading hides the profile strip and module sidebar;
reopen Reading options to exit. Profile setup remains available explicitly on
mobile. The lesson outline and learning-progress panel expand on demand.
No measured retention or time-to-competency is inferred from lesson counts.
Mastery gates, explicit overrides and backend assessment are unchanged.

Reading size, spacing and focused mode stay selected when navigating away and
back in the same signed-in tab; they are not server-saved preferences and refresh
resets them. Changing signed-in accounts clears these settings. Larger text also
scales lesson headings, code and tables. **Read** moves keyboard focus into the
reading area; focused-reading toggles return focus to **Reading options**.
Tab to code examples or lesson tables and use arrow keys to inspect horizontal
overflow. Tables retain their normal screen-reader table structure. Outline
buttons have minimum 44px targets. These refinements are not an accessibility
certification; screen-reader/device testing and future audio captions remain.

The unified workspace privately autosaves the current lesson response, tutor
exercise response, checklist, unsent tutor message, conversation mode and selected
view after a short debounce. **Workspace saved** confirms server storage; those
values survive refresh alongside the existing saved lesson and tutor history.
**Couldn't save workspace** retains the local draft and offers Retry save.
Competing tabs receive a conflict rather than silently replacing a newer draft;
copy important edits before choosing Reload saved workspace. Changing the exercise
starts a new draft; learner/session reset clears its recovery record. Recovery
does not call a model, submit work, approve actions or alter mastery.

Each of the three text fields supports up to 100,000 characters, with a combined
600,000-byte JSON limit and at most 12 checklist entries. Only one current
lesson/exercise draft is recovered, not a draft history. Unsaved last keystrokes
are not guaranteed after an abrupt close. This UI recovery endpoint does not
change standalone CLI or public tutor SDK behavior.

For UI integrations, `GET /api/atlas/status` includes `workspace_recovery`
(`mammoth.learning-workspace.v1`) with `exercise_key`, `revision`, `values` and
`saved_at`. `POST /api/atlas/workspace` accepts `{exercise_key, revision, values}`
and confirms `status: "saved"` with the new snapshot. Validation returns 400,
stale revision/exercise returns 409, and unavailable/invalid storage returns 503.
The backend selects user/account storage; request payloads cannot select a user.

### Returning to a workspace page

Within the same tab, navigating between Agent, Mammoth Mind, Notes, Build Log and
ATLAS preserves their working drafts and available full results in account-scoped
memory. Agent threads, team preview/results/follow-ups and Mammoth Mind conversation
history are retained without replacing them with shortened browser-cache summaries.
Signing out or switching signed-in accounts discards this page memory.
Inactive pages unmount and stop polling; returning never automatically replays
billable work or approvals.
New browser thread caches are account-scoped. Older unowned Agent caches are
left untouched but not automatically adopted; use private Artifacts for saved
outputs rather than exposing another account's browser-only history.

Page memory is not a permanent archive or background-execution guarantee.
Leaving a live chat can still end its streaming connection. After a browser reload,
use confirmed ATLAS saves and private Artifacts/run records; keep exports for an
independent copy. Unsubmitted Notes/Build Log drafts are navigation memory only.
Accessibility, privacy/cost controls and narration follow-ups remain in the
[ATLAS roadmap](ATLAS_WORKSPACE_ROADMAP.md).

### Contextual help and connected study materials

Select rendered lesson text (2-4,000 characters), then choose **Study selection**.
**Explain instructions** and **Work on feedback** also open the same on-demand
dialog. Choose a simpler explanation, worked example, practice question, or
feedback-specific remediation, then explicitly choose **Ask tutor**. Opening the
dialog does not call a model; asking uses the configured provider and model
credits. Help does not submit work, change the exercise, or demonstrate mastery.
Remediation uses actual feedback, not an inferred diagnosis of the learner.

The backend validates the exact quotation against the active lesson, instructions
or feedback and checks exercise identity again after generation. Stale context
is rejected, even if the request has already used credits. Runtime failure or a
local echo is an explicit failure, not a canned successful explanation. Private
model reasoning is separated from the visible answer. Successful help is also
saved in the existing tutor conversation.

Within the dialog, write a **Study note** or use the help as an AI-assisted draft.
**Save reviewed note** uses existing private Notes and its Pro/developer gate.
For cards, **Draft recall card** derives an editable question/answer from the
selected teaching passage without a model call. Instruction-only passages may
produce no card; **Write my own card** lets you supply the answer instead.
Review both sides before **Save reviewed card**, which uses existing lesson
flashcards. Notes/cards distinguish learner-written/edited, source-derived and
AI-assisted content as applicable; no save action generates a model answer.

Saved items show collapsed **Lesson provenance** in Notes, lesson notes and
flashcards. It records the lesson, section, quotation, authorship and source URLs
already present in that lesson section. These are provenance links, not
independently verified facts or newly researched citations.

Study drafts, help and pending-request state survive in-app navigation in the
same signed-in tab. A failed save retains the draft; no automatic retry is made.
Selecting different text starts a new study draft. Unsaved dialog notes/cards
are not included in the server recovery snapshot and do not survive refresh.
Confirmed notes/cards use their existing storage and retention; flashcard study
aid history retains the latest 120 records. Repeating an ambiguous save after a
network failure can create a duplicate; check the destination before retrying.

API additions are additive: `POST /api/atlas/study-preview` accepts
`learning_selection: {exercise_key, source, selection}` and returns a model-free
draft. `POST /api/atlas/chat` accepts that selection plus `action` inside
`contextual_help`. `POST /api/notes` and `POST /api/flashcards` accept
`learning_selection`, `reviewed: true`, and explicit `authorship`. The server
derives `mammoth.learning-selection.v1` provenance and ownership; clients cannot
choose another user's context. Standalone tutor SDK behavior is unchanged.

### Lecture transcript foundation (no audio playback yet)

`GET /api/atlas/lecture` requires sign-in and reads only the request user's
active lesson. `ATLASSession.lesson_lecture()` and
`MammothMind.lesson_lecture()` expose the same additive
`mammoth.lesson_lecture.v1` contract. `AtlasFAB` is still the same class alias.
Reads generate no text/audio, change no exercise/mastery, and incur no model
call. This is an integration foundation, not a visible lecture player.

The response contains `lesson_id`, `lesson_title`, `lesson_revision`,
`status` (`transcript_only` or `empty`), ordered `sections`, `narration`,
and `model_calls: 0`. Each section has `section_id`, `title`,
`content_markdown`, `audio_start_seconds: null`, and
`audio_duration_seconds: null`. Content comes from the actual lesson
body (or summary when there is no body), teaching points and examples.
Objectives are not substituted as a lecture. Reasoning tags are removed.
Markdown is source text, not trusted HTML; consumers must sanitize rendering.

IDs are deterministic hashes of lesson identity, section heading and content,
plus an occurrence suffix for identical duplicates. An unrelated section
insertion preserves existing IDs; editing section text/heading changes its ID.
Inserting/deleting identical duplicates can change their occurrence identity.
The whole-lesson revision binds the ordered content and title; future commands
must carry the revision as well as a section ID. A transcript without a lesson
ID is not sufficient to target a persisted playback session.

`narration.status` is `not_configured`; provider, voice and duration are null.
There are no fabricated durations or seek positions. Voice/provider selection,
licensed usage review, cached audio, playback/seek/speed controls, microphone
permissions and duplicate-safe lecture commands remain planned.

### Learning export, privacy and spending

Open **Learning profile** in the desktop workspace header (or **Edit learning profile**
in the mobile profile strip). Each layout has one profile toggle, not a duplicate
desktop strip control,
then **Learning privacy & costs**. Closing the profile retains unsaved edits while
the workspace stays mounted; it does not save them. **Not now** collapses the form,
and successful saving collapses it while retaining the confirmation. Existing
first-time desktop setup remains automatic; mobile setup remains opt-in.
Switching signed-in users clears the prior user's local profile draft. The disclosure
is on demand so the normal mobile lesson does not lose another toolbar row.
**Export saved learning JSON** downloads `mammoth.learning-export.v1`: the active
local account's saved lessons, exercises, full retained tutor/assistant messages,
study-aid records, explicitly owned lesson-linked notes, saved learner profile,
and recovery snapshot. The additive `learner_adaptation` block
(`mammoth.learner-export.v1`) includes the actual saved private model's supported
fields: onboarding, mastery/confidence, attempts/streak, error patterns, retained
outcomes and memory graph. It returns `status: saved` and `model`, or
`status: not_saved` and `model: null` when no scoped record exists. It never
creates a default model, imports legacy data or trims saved outcomes.
The same payload is included as `learning_workspace` in
Account's existing data export. It does not generate content or call a model.

The export excludes unsaved tab drafts, uploads, other accounts, unverified legacy
learner models, unknown top-level learner extension fields, telemetry, Artifacts, Mammoth Mind threads, provider records
and backups. It is not a full account archive or an atomic snapshot of concurrent
edits. Recovery values with `saved_at: null` have no confirmed server draft.
Previously trimmed history is not recoverable. Exported notes preserve the
stored record, including provenance; unowned legacy notes are not adopted.
Downloaded files contain private content and must be managed on your device.

`POST /api/atlas/export` requires sign-in; there is no client-supplied user/account
selector. Success uses `Cache-Control: no-store`. Corrupt/unreadable state,
linked-note storage, private learner adaptation or recovery fails explicitly (503).
Invalid ownership also fails without a partial success or reset. Up to 8 MiB of
ASCII-serialized JSON is accepted; larger exports fail (413) without a shortened
success result. Individual Notes and curricula exports remain alternatives.

Normal saved windows are 80 lesson-history records, 120 study-aid records,
60 messages per tutor/assistant history and one current recovery draft.
These are count-based windows, not automatic age-based expiration; an export
does not prune the underlying stored records. Exact generation-price estimates
are unavailable: costs vary by provider, tokens, tools and retries. Reading,
restoring, exporting and source-derived card previews do not call a model.
Asking for tutor help, lessons/courses or agent work can use credits. Failed or
interrupted calls can already be billable; no automatic export retry is made.

Use **Open Notes controls** for individual note deletion, the materials manager
for uploaded-file deletion, and **Open Account controls** for account-deletion
requests. Resetting progress is not a privacy wipe. A request is not proof of
completed erasure of operational records, provider copies or backups.

**Refresh learning request controls** loads your private
`mammoth.learning-controls.v1` record. The optional **Daily ATLAS request cap**
is uncapped by default; blank disables it and zero pauses covered requests.
It counts admitted HTTP requests, not model calls, tokens, dollars or credits.
Failed, cancelled, guarded, and gated requests count too: there are no refunds
that might conceal already-billable work. Counts reset at midnight UTC;
changing a limit does not reset usage. Atomic SQLite reservations enforce the
exact allowance across concurrent workers and all local accounts of the signed-in
user. Usage counts retain at most 32 UTC dates; recent terminal request metadata
is bounded to about 100 records. Unconfirmed running/requested records are retained
without a fabricated completion or expiry. No prompts or replies are stored there.

Covered routes: `POST /api/atlas/lesson`, `/submit`, `/next`, `/curricula/start`,
`/regenerate`, `/chat`, `/plan`, `POST /agent/atlas/run`, and
`POST /api/atlas/agents/run` for non-streaming Learning-panel requests.
The latter requires an explicit Tutor, Curriculum, Research, Reflection, Coding
or Browser catalog ID; invalid agents fail before dispatch. Failed requests count.
The worker thread retains private request/cancellation context; cancellation
discards a delayed answer before completion is recorded and prevents checked retries.
Reading, exports,
source-derived previews and saved-workspace recovery are outside the cap.
**General workspace runs, repository/tool-loop runs, Mammoth Mind and SDK/local calls
are not covered**. This is a self-imposed ATLAS request cap, not an operator
billing ceiling, subscription entitlement or full-platform spending guarantee.
`GET/PUT /api/atlas/controls` require sign-in; PUT accepts only
`{"daily_request_limit": null}` or a whole number from 0 to 100000.
Exhausted admission returns 429 before the route executes. Invalid input is 400;
storage failures are explicit 503, never an uncapped fallback.

Each recorded request offers **Request cancellation**.
`POST /api/atlas/operations/{id}/cancel` selects only the authenticated user's
private operation record (404 for another user's ID). It first records
`cancellation_requested`, not "stopped". Cooperative checks before/after model
calls, before fallback and state saves stop at the next checked boundary and
record `cancelled_at_boundary`; the original HTTP request then returns 409
with `status: cancelled`. Already-sent provider work may finish and be billed;
prior assessment/mastery updates, executed plan steps or other completed side
effects are not undone. Blocking generation runs off the event loop so the
controls remain reachable and preserve request context. No thread is killed.
After a server interruption, an unconfirmed running record is not proof of
ongoing provider work. Refresh explicitly to read the latest recorded status.
Contextual-help dialogs can close their view while help runs; closing is not
cancellation, and the pending help remains in same-tab memory.

Hosted adaptation now lives in a separately hashed signed-in-user + learning-account
directory. It stores onboarding, mastery/confidence, error patterns and memory
graphs. The API supplies this scope; client user IDs cannot select another model.
The additive `mammoth.learner-storage.v1` metadata identifies the scope and
reports `legacy_imported: false`. Unverified global legacy models and unmarked
cached adaptation are not imported. Existing lessons and conversations remain;
learners may need to re-enter their starting preferences. Legacy files are left
untouched for a future reviewed ownership/recovery workflow, never guessed into
a tenant or erased automatically. The saved private model's supported fields now
appear in learning/Account exports. Standalone adaptation remains outside the
saved-learning deletion action described below; export does not erase it.
Corrupt/foreign model records produce explicit 503 failures without a reset.
Confirmed model writes use atomic replacement, and onboarding/assessment changes
serialize across workers so concurrent attempts are not lost. Evaluation probes
use disposable storage rather than writing a learner's real adaptation.
Local callers retain the existing `storage_path` option and model filename; use
a distinct trusted directory per learner. Reading or overwriting a record belonging
to a different `user_id` now fails explicitly instead of reassigning it.

For the separately stored model, **Review private adaptation deletion scope**
calls authenticated `GET /api/atlas/learner/privacy-review`. Its
`mammoth.learner-privacy-review.v1` result lists saved supported field names and
counts of mastery/confidence concepts, error patterns, retained outcomes and
memory nodes/edges. It returns explicit `not_saved`/null counts if absent,
without creating defaults or reading the unverified legacy model. It does not
return concept labels, goals, answers or filesystem paths. Corrupt/foreign
records fail explicitly; responses are no-store and no model calls occur.

This review is not an executable deletion preview: `deletion_available: false`
and `review_only: true` are mandatory for this endpoint. There is no confirmation
token or receipt for this read-only action. No requests are cancelled. Lessons/recovery, notes, uploads,
curricula, other accounts, legacy/unknown model extensions, telemetry, threads,
artifacts/plans, audit/usage, provider copies, backups and other tabs/downloads
remain outside this review, not promised retained by a future erasure flow.
It is not a full inventory or atomic snapshot.
Refreshing a failed review clears the old displayed result; no automatic retry.

**Preview private adaptation deletion** is the separate destructive flow.
Authenticated `GET /api/atlas/learner/deletion-preview` returns
`mammoth.learner-erasure.v1`, the active account, model saved/absent status,
cached field names, exclusions, blockers and a content-bound preview token.
It can create lock files but never creates a default learner model. Unknown
top-level model extension fields block deletion rather than being silently
discarded. Corrupt, unreadable or foreign models fail explicitly and are not
removed. An absent model can still have caches to erase.

Type exactly **DELETE PRIVATE ADAPTATION**, then select **Delete private
adaptation**. `DELETE /api/atlas/learner/adaptation` accepts only `confirmation`
and `preview_token`; owner/account selectors cannot expand scope. Changed model,
onboarding, caches, account, owner or deletion generation requires a new preview
(409). This erases the current private model's onboarding/preferences/goals,
mastery/confidence, errors, retained outcomes and memory graph, plus
`learner_model`, `learner_context`, `learner_profile`, `learner_storage` in the
active account's root/session caches. It preserves lesson/session/recovery
content, conversations, drafts, linked notes, files, saved curricula, telemetry,
other accounts, legacy files, threads, artifacts/plans, audit/usage, provider
records, backups and other tabs/downloads. Previously generated lessons/plans
may still reflect old adaptation; this is not semantic removal from all content.

Hosted writers lock state before model storage and compare durable erasure
generations. Older assessment/onboarding/reset work and cached state envelopes
cannot recreate deleted adaptation. Pre-deletion or unbound learner mutation
approvals are rejected; request a new approval. Deletion requests cancellation
of tracked Learning operations for this account, not other accounts. Already-sent
provider work may finish/bill; completed unrelated side effects are not undone
and usage is not refunded. New deliberate activity can create fresh adaptation.
Local SDK model APIs are unchanged; these guarantees cover hosted API writers.

Deletion first saves a content-free pending fence and clears the four caches,
then removes and verifies the model, and finally confirms the complete fence.
The response has a receipt only after verification. A failure is explicit and
may be partial: pending deletion blocks model hydration/writes. Read-only review
and export remain available for recovery, explicitly marked `pending_deletion`;
they are not receipts. Review and retry explicitly. Do not remove the fence to
recover access. No retry is automatic.
The UI clears its obsolete preview/confirmation after any delete attempt, clears
profile edits on verified success and refreshes adaptation without deleting
lesson drafts. Reload other tabs: their in-memory content cannot be remotely
erased. A receipt does not verify provider, backup or download erasure.

The existing **Preview saved learning deletion** action below still concerns only
the lesson session/recovery, not the standalone learner model.
Type **DELETE SAVED LEARNING** to enable the destructive action. The preview
fingerprint binds to the account, saved session and recovery revision; changed
content or an account switch requires a new preview (409). Successful
`DELETE /api/atlas/history` verifies removal of the active saved lesson/exercise,
curriculum session, tutor/assistant conversations, lesson history, study cards,
session learner profile and recovery file from their canonical active stores.
It returns a content-free receipt, requests cancellation of tracked operations
for that account, and clears workspace/study drafts in this tab. The saved
erasure epoch prevents older in-flight state saves from restoring deleted data,
including an older envelope containing other local accounts.
New requests admitted after deletion can create new saved data.

This action deliberately **does not delete** linked Notes, uploads, separately
saved curricula, standalone learner models or cached learner context,
onboarding/mastery, telemetry, other accounts, Mammoth Mind threads, artifacts,
plans, audit/usage records, provider records, backups, other tabs or downloaded
exports. Those need their own controls; do not describe this as an account wipe.
The unverified legacy learner-model ownership still needs separate review;
the private adaptation flow above never imports or removes that file.
Lesson-session deletion failures are explicit 503 with
no success receipt; a recovery file may already have been removed before a
failed state commit. Review a new preview before retrying.

Automatic age-based history expiry, full-platform cancellation/spending limits,
and verified erasure of the excluded stores remain in LEARN-06. This is not a
privacy/compliance certification.

The website uses a dark semantic palette: brass/copper primary actions and agent
identity, blue keyboard focus/links/secondary interaction, and grey/white text.
Settings > Theme includes a Texture lines toggle for the scan-line overlay.
Its preference is saved in this browser, not synchronized to the account.
The control keeps a stable accessible name, exposes its pressed state, supports
Space/Enter, and has a minimum 44px by 44px touch target.
Runtime health and success/warning/failure colors remain meaningful; destructive
actions stay red. Decorative purple/pink/teal accents are removed, not emoji or
logo artwork. Mammoth Mind's lane/task controls retain their choices with themed
dark selects and clear keyboard focus. This styling does not change CLI behavior.

This repo has completed the reliability + eval + tutor-outcome + SDK hardening sweep and now sits in a controlled production-candidate state.

### Current rating summary

| Area | Score | Notes |
|---|---:|---|
| System overall | 9.5 / 10 | Core runtime and release gating are now fail-closed and auditable |
| MammothOS Chat | 9.4 / 10 | Native chat, multi-agent routing, approvals, and usage warning surfaces are in place |
| CodingAgent | 9.5 / 10 | Async safety, structured logging, and guarded execution paths are stable |
| TutorAgent | 9.5 / 10 | Adaptive tutoring now includes measurable learner outcome signals |
| ShellAgent | 9.3 / 10 | Safety controls and approval-aware behavior are consistent |
| API Server / Orchestration | 9.5 / 10 | Health gate + release gate + eval gate now enforce deployment confidence |
| UI / Command Center | 9.2 / 10 | Workflow surface is strong; final visual polish remains on least-used pages |
| LLM Runtime / Provider Chain | 9.4 / 10 | Fallback chain is active, explicit, and degraded-state aware |

### Where Mammoth stands vs Copilot

- Mammoth is now competitive on multi-agent control, tutor specialization, and operator-facing workflow safety.
- Remaining gap is not architecture depth; it is breadth and scale polish (cross-tenant enterprise rollout, CI policy enforcement on every branch, and hosted billing/provider operations at volume).

### Phase plan — 8 → 9 (completed)

1. **Execution quality loop ✓** — plan → act → verify → retry for coding and agent work; success criteria explicit.
2. **Browser automation layer ✓** — stateful navigation, form filling, and replayable flows.
3. **Agent memory + evals ✓** — `MemoryEngine` now persists ATLAS lesson outcomes via `/api/memory`; eval history tracked via `/api/atlas/evals` with observability dashboard.
4. **Docs + UI alignment ✓** — this manual, the in-app Manual page, `LandingPage` doc links, and the root README are now in sync.

### What is “ready enough” now

- Developer/operator testing flows are working and validated
- Approval gating, diagnostics export, and health pages are operational
- Core agent lanes are normalized around structured outputs
- Native chat can route to agent work and keep operational context visible

### Phase 3/4 operator workflow surfaces now live

- Agent Console now renders structured coding artifacts (overview/code/tests/docs/diff) with apply/write feedback.
- Run History replay now preserves backend-linked metadata (`task_id`, `trace_id`, runtime adapter/model).
- FAB chat responses can be saved directly into Artifact Library records (`.md` or `.txt`).
- Task Inbox provides a lightweight queue for follow-through on workflow cards; load/update failures are shown directly, and run-backed task statuses stay read-only while manual cards remain editable.
- Workspace > Run Review reopens your saved plans, tool traces, diagnostics, checks and branch receipts. Refresh is read-only: no model calls, continuation or approvals. Download review JSON explicitly; it can contain prompts, source excerpts and logs, so inspect it before sharing. Saved status overrides old event state (including cancelled approvals). Runs follow server retention, not permanent archival. Both Paths clients expose `recover_run` / `recoverRun`; JavaScript also exports `hydrateRun` for full snapshots. Automatic reconnect/background execution remain deferred.
- Artifact provenance exposes recorded task/trace IDs, repository/base SHA when available, quality and verification details, and up to ten previous revisions. View recorded run loads account-scoped task state or explicitly client-supplied saved history; it never executes or replays work. A recorded base SHA is the selected Git ref, not a clean-working-tree guarantee. Generated tests/diffs and output-contract checks are not acceptance-test evidence or approval to apply code. Missing run records produce an explicit error while the artifact remains available.
- Internet commands are available in chat:
  - `/research <query>`
  - `/web <url>`

### What still needs a final pass

- Enforce the release/eval gates in CI as mandatory merge checks on all protected branches.
- Complete final visual polish on the least-used UI screens.
- Replace preview-safe usage metering with hosted billing-provider-backed metering.

### CI enforcement update

- `.github/workflows/release-guardrails.yml` now runs the release/eval/tutor/SDK guardrail suite on PRs to `main`, pushes to `main`, and manual dispatch.
- `.github/workflows/deploy-digitalocean.yml` now requires the same guardrail suite to pass before deployment.
- For full protection, require `Release Guardrails / guardrails` in branch protection for `main`.

---


---

## MCP Browser Bridge

MammothOS now ships a **Playwright MCP browser bridge** that gives Mammoth Mind real browser automation capability — navigate pages, click, fill forms, screenshot, and run Lighthouse site audits. This is the same pattern as Microsoft Copilot Tasks.

### What it does

| Tool | What it does |
|---|---|
| `browser_navigate` | Open a URL, wait for full load |
| `browser_snapshot` | Extract DOM snapshot, headings, links, text |
| `browser_click` | Click a button or link by selector |
| `browser_fill` | Fill form fields |
| `browser_screenshot` | Capture a full-page screenshot |
| `site_audit` | Browser snapshot + Lighthouse performance/SEO/accessibility audit |

### Start the browser bridge (local machine)

**Linux / macOS:**
```bash
bash scripts/start-browser-mcp.sh
```

Linux fallback for non-interactive audits:
```bash
MCP_BROWSER_MODE=system-headless bash scripts/start-browser-mcp.sh
```

**Windows:**
```powershell
.\scripts\start-browser-mcp.ps1
```

First run opens a **headed Chromium window** so you can complete any login/auth gates. After sign-in, the persistent profile at `./tmp/mammothos-browser-profile` stores cookies automatically — subsequent runs resume without re-auth. The `system-headless` fallback is for Linux hosts that already have Chromium/Chrome installed and only need non-interactive audits.

### Run a site audit via Mammoth Mind

In the Agent Console, set intent to `site_audit` and send:
```
https://truexxiisupply.com
```

Or use the Mammoth Mind chat:
```
Run a site audit on truexxiisupply.com — headings, nav, CTAs, Lighthouse scores, and top 10 fixes.
```

### MCP config files

All MCP server configs live in `mcp/`:

| File | Purpose |
|---|---|
| `mcp/index.json` | Master registry of all MCP servers |
| `mcp/playwright.json` | Playwright browser bridge config |
| `mcp/filesystem.json` | Repo filesystem read/write access |
| `mcp/git.json` | Git status, diff, log (commit/push require approval) |

### Human gate

When the browser hits an auth wall or needs your input, the agent returns `status: human_gate` with instructions. Complete the action in the browser window — the workflow resumes automatically.

### MCP status in Command Center

The **Modules page** now shows a **MCP Tool Bridges** panel at the top with live status for each server (ready / needs_setup / disabled). A `needs_setup` status means Node.js or the MCP package is not installed yet.

---
## 1 — One-time setup

### 1a. `.env` file (set once, loads automatically)
The CLI reads `.env` from the repo root on every run. You do not need to
`$env:...` anything manually anymore — just keep the file up to date.

### 1b. Python install quickstart

```powershell
pip install mammoth-os
```

If you are running the API server or the command-center stack:

```powershell
pip install mammoth-os[server]
```

> **Update:** the CLI now hard-pins itself to the active worktree `src\` path on
> startup, so legacy parent-repo installs or stale boot scripts are much less
> likely to hijack imports.

Required keys in `.env`:
```
SUPABASE_URL              = https://mkstgbegjkonmwmjqkpz.supabase.co
SUPABASE_SERVICE_ROLE_KEY = <your service_role JWT>
OPENAI_API_KEY            = <your OpenAI key>          # optional if using Ollama
```

> **PowerShell JWT tip:** always wrap the value in double-quotes in the `.env` file:
> `SUPABASE_SERVICE_ROLE_KEY="eyJhbG..."`

---

## 0 — Scope, suggestions, and operator notes

### Scope right now
- Keep ATLAS as the top-level adaptive tutor and MammothOS as the execution shell.
- Strengthen reliability, continuity, diagnostics, and lesson quality before monetization wiring.
- Maintain enterprise-safe posture: accurate claims, auditable operations, no legal overstatements.

### ATLAS FAB standalone direction (developer-grade)
- Use the public Python SDK surface for embedding:
  - `from mammoth_os import AtlasFAB, AtlasFABConfig`
- Keep embeddings account-scoped (`user_id="workspace:<account_id>"`) to prevent cross-user state leakage.
- Expose runtime metadata to integrators via `AtlasFAB.runtime_state()` so they can show provider/fallback health.
- Treat this as the bridge to paid distribution (SDK + hosted API + usage-metered plans).

### Billing/usage warning surface (what it means)
To warn customers before limits are hit, the product needs a usage source of truth from backend or billing provider.

Suggested response shape:
```json
{
  "plan": "pro",
  "period_start": "2026-08-01T00:00:00Z",
  "period_end": "2026-08-31T23:59:59Z",
  "usage": {"requests": 812, "request_limit": 1000, "tokens": 184200, "token_limit": 250000},
  "percent_used": 81.2,
  "warning_level": "elevated"
}
```

### Production auth/tenant execution path

Use the new Supabase tenant/auth blueprint to move from a local-operator build to a real multi-account product:

1. Run `.mammoth\supabase_tenant_auth.sql` in Supabase.
2. Keep your current authenticated account as the initial owner/admin.
3. Bootstrap it with:
   ```sql
   select public.bootstrap_tenant_for_user('MammothOS', 'mammothos');
   ```
4. Require authenticated tenant membership for:
   - dashboard data
   - operator settings
   - usage/billing views
   - developer/admin controls
5. Keep public pages separate:
   - landing
   - pricing
   - compliance / trust
   - docs / marketing copy

### What a random public visitor should see

When this goes to your domain, a normal visitor should **not** see your private dashboards, your personal metrics, or your internal operator state.

The correct production behavior is:
- public visitors see only marketing/trust pages
- signed-in customer users see only their tenant-scoped workspace data
- owner/admin users see private operator controls
- internal-only controls remain role-gated even after login

If any anonymous or wrong-account session can see shared numbers, health data, usage, or internal toggles, treat that as a production blocker.

### Go-live risk checklist

Before launch, test these flows on the deployed domain:
- anonymous user loads the site
- new customer signs up
- customer lands in an empty, fresh workspace
- admin account sees owner controls
- member account does **not** see owner controls
- usage warning banner only appears when real tenant usage crosses threshold
- no page shows your local/dev placeholder values as if they were customer data

### Suggested next build order (lowest credits first)
1. **Lessons domain architecture** (UI-first track templates, starter pathways, progress shells).
2. **Health dual-mode expansion** (personal readiness + system telemetry in one page).
3. **Finance dual-mode expansion** (personal + business lanes, rollups, and notes).
4. **Payments and checkout** only after the above surfaces are stable and policy-ready.

### Keep in mind
- Use `Preview first` for coding agent edits and approve intentionally.
- Keep startup deterministic (`start-mammothos.bat`) before debugging UI connectivity.
- Record major runs in Build Log and Diagnostics export so work remains portfolio-verifiable.
- Avoid mixing legal claims with roadmap intent; document "current posture" vs "planned posture."

### Source-aware output contracts and prompt shaping

The runtime now keeps structured payloads intact for coding and brand-voice work instead of flattening everything into a raw string, which was the root cause of low-grade generic outputs.

**Core rules:**
- `coding` tasks should always carry a clear `prompt`, `target`, and optional `context.files` or `context.source`.
- Documentation-only requests without a real file path or source snippet return a `needs_context` response rather than fake “generated docs.”
- `brand_voice` tasks should specify `mode`, `audience`, `tone`, and optional `constraints` so the rewrite stays on-message.
- The UI prompt box works best when the user enters: objective + scope + constraints + expected output.

**Research hygiene** (`research_quality.py`, used by `ResearchAgent`):
- Web search and research fallback sources share subject-aware filtering:
  generic "API/docs" words do not establish relevance to a named product,
  documentation requests exclude non-documentation hits, duplicate URLs are
  collapsed, and obvious source instructions are excluded. Search tool results
  include retained/dropped counts and reason counts in `quality`. No usable hits
  means insufficient evidence, not invented findings or increased confidence.
  Filtering adds no paid calls; it does not verify facts/domain ownership, and
  instruction detection is heuristic rather than comprehensive protection.
- Model reasoning and meta-commentary are removed from research output and long-form documents and returned separately as `reasoning_trace` / per-section `trace`.
- Off-topic sources and disambiguation pages are filtered (`sources_filtered`). Entity mismatches are ranked lower, never silently dropped.
- Duplicate findings and repeated cross-section paragraphs are removed. Truncated sections are trimmed to the last full sentence; failed sections retry once, then show as `status: "failed"`.
- Long-form results include a `quality` block so you can see exactly what was cleaned.

### CodingAgent hardening: Asyncio safety & exception handling (v1.2)

**Problem:** CodingAgent was calling `asyncio.run()` in multiple places, which raised a `RuntimeError` when the agent was invoked from an already-running event loop. This was especially common during concurrent AI requests or when orchestrating multiple coding tasks.

**Solution:** Added a robust `_run_async()` bridge method that:
1. **Detects** if an event loop is already running with `asyncio.get_running_loop()`.
2. **Routes** safe calls: if no loop is running, call `asyncio.run()` directly.
3. **Bridges** event loop conflicts: if a loop is already running, use a thread pool executor to run the coroutine in a fresh thread.
4. **Logs and re-raises** exceptions for visibility: all errors in async task execution now appear in the standard logging stream.

**Additional improvements:**
- Wired `log()` method to Python's standard `logging` module (not `print()`), so all CodingAgent activity is now part of the operator audit trail.
- Added input validation: `commit_changes()` now checks for empty file lists to prevent silent git command failures.
- Fixed type hints for Python <3.10 compatibility (replaced `str | Dict` with `Union[str, Dict]`).
- Standardized log levels: replaced non-standard `"WARN"` with `"WARNING"`.

**Result:** CodingAgent now safely handles nested async contexts, provides better debugging visibility, and is much less likely to crash when called during concurrent multi-agent orchestration.

### Additive agent bridge

MammothOS keeps the native runtime-first flow and adds an optional HTTP bridge for external orchestrators such as Copilot Tasks.
The bridge is deliberately additive and does not replace the existing registry + workflow APIs.

```http
POST /agent/atlas/run
POST /agent/coding/run
POST /agent/shell/run
```

Use these endpoints as an optional integration layer when you want an external conductor to delegate to ATLAS or CodingAgent without forcing Copilot itself to do all edits.

### Copilot Tasks integration appendix

This is the recommended integration model when an external orchestrator such as GitHub Copilot / Copilot Tasks needs to talk to MammothOS without bypassing the native runtime.

**Goal:**
- Keep MammothOS as the source of truth for agents, workflows, and state.
- Use Copilot as a conductor, not as the direct file editor.
- Route work through the runtime agents rather than editing files directly from the external tool.
- Preserve safety rails: preview-first, approvals, rollback, observability.

**Connection surface:**
```http
POST /agent/atlas/run
POST /agent/coding/run
POST /agent/shell/run
```

**Contract:**
- `/agent/atlas/run` → routes to the runtime tutor agent for lesson planning, coaching, adaptive feedback, and ATLAS-first orchestration.
- `/agent/coding/run` → routes to the runtime coding agent for code generation, refactor, explain, and UI scaffolding tasks.
- `/agent/shell/run` → executes a safe shell command in the repo worktree using the safe subprocess wrapper.

These routes are additive and coexist with:
- `GET /api/agents`
- `GET /api/modules`
- `POST /api/plan-execute`
- `GET /api/autonomous/runs`

**Copilot Task → MammothOS mapping example:**
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

MammothOS then:
1. Uses the runtime `coding` agent to propose a patch preview.
2. Uses the `tutor` agent if the plan profile is `atlas_first` for strategy and safeguard checks.
3. Surfaces the preview in the approval workflow.
4. Applies changes only after approval, with rollback support enabled.

**Recommended profiles:**
- `atlas_first` — ATLAS strategy layer first, coding subordinate.
- `tutor_coding` — balanced tutoring + implementation.
- `coding_only` — tightly scoped, low-risk code work.
- `autonomous_prep` — larger multi-agent execution with ops and safety steps.

**Safety and authorship rules:**
- Preview-first is mandatory for any Copilot-driven task (`approval_mode: true`).
- No direct file writes from Copilot; all code edits should come through the runtime agent bridge or the plan/execute API.
- Use MammothOS agents as the actual implementation layer; Copilot acts as orchestrator, not direct editor.
- Log and show progress via `GET /api/autonomous/runs` and the build log / diagnostics trail.

**Minimal wiring checklist:**
1. Point the external orchestrator at `http://localhost:8000`.
2. Enable discovery with `GET /api/agents` and `GET /api/modules`.
3. Use the bridge for execution: `POST /agent/atlas/run`, `POST /agent/coding/run`, `POST /agent/shell/run`.
4. Use `POST /api/plan-execute` with `plan_profile` and `approval_mode` for multi-step work.

Education objectives in balanced/ATLAS/autonomous plans use Tutor, Research,
Reflection and synthesis rather than adding market, deployment, publishing or
custodial steps because of topic words or the autonomous profile. Explicit
software implementation wording can add Coding; explicit coding/coding-only
profiles retain their existing behavior. This routing is conservative and
lexical, not a guarantee that a plan understands every ambiguous request.

`POST /api/plan` and PlannerAgent require complete structured task graphs with
unique task IDs, explicit titles, object inputs and dependencies referencing
earlier tasks. Invalid JSON, truncated arrays, lesson-shaped execution payloads,
out-of-scope education agents and provider failures do not become generic
fallback plans. The API returns `502`, `status: failed`, `code: invalid_plan`,
an empty task list and `quality.ready: false` before dispatch. Retry is explicit;
no automatic model retry or fabricated task title is used. Saved curriculum
plans retain actual lesson IDs, titles and normalized estimated durations.
Stripped model reasoning is returned separately as `reasoning_trace`, never
inside task inputs. Structural DAG validation does not prove agent availability
or teaching correctness; normal execution approval/access checks still apply.
5. Respect approvals and rollback before any mutable action.
6. Display run history via `GET /api/autonomous/runs`.

---

## 2 — LLM model selection

MammothOS now supports a safe dual-provider runtime: DeepSeek for reasoning-heavy work and OpenAI for coding tasks, with automatic fallback if a provider is out of credits or a key is invalid.

| Priority | Condition | Result |
|---|---|---|
| 1 | `MAMMOTH_LLM_ADAPTER=local` in `.env` | Deterministic echo (CI only) |
| 2 | `MAMMOTH_LLM_ADAPTER=ollama|hermes|codellama|...` | That Ollama model |
| 3 | `MAMMOTH_LLM_ADAPTER=deepseek|deepseek-api|deepseek-cloud` | DeepSeek cloud reasoning path |
| 4 | `MAMMOTH_LLM_ADAPTER=openai` | OpenAI |
| 5 | `DEEPSEEK_API_KEY` is set | DeepSeek, then OpenAI, then Ollama/local fallback |
| 6 | Only `OPENAI_API_KEY` is set | OpenAI (`gpt-4o-mini` default), then Ollama/local fallback |
| 7 | Ollama is running on localhost:11434 | Ollama auto-detected |
| 8 | Nothing available | Local echo fallback |

### Recommended provider split

- Use DeepSeek for reasoning, long-context tutoring, and ATLAS coaching.
- Use OpenAI `gpt-4o-mini` for coding generation, repair, and code review.
- If the current provider is out of quota / billing blocked / key invalid, MammothOS retries through the next provider instead of dead-ending the workflow.

Coding-agent generation/advice/refactoring and Mammoth Mind proposal/validation/
application runs use an explicit coding workload. Its default order is OpenAI,
DeepSeek, Ollama, then local echo. Operators may set
`MAMMOTH_CODING_LLM_ADAPTER=deepseek` to prefer DeepSeek for coding without changing
tutor/general routing; values other than `openai` / `deepseek` are rejected.
Explicit per-call adapters and process-wide offline settings still take priority.
The `deepseek` adapter alias uses cloud when a DeepSeek key is configured; without
one, its old local-model alias is retained. Use `deepseek-cloud` or
`deepseek-coder` when you need an unambiguous choice.

Coding search can be scoped to an exact repository-relative file or directory.
After two discovery calls with source matches, a checkpoint temporarily removes
more search/list/readiness calls from the next decision, encouraging a real
source read instead. No extra task steps or permissions are granted. A checkpoint,
schema-valid decision or passing build is not proof of correct code or layout.

### Cloud keys in `.env`

```env
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
MAMMOTH_LLM_ADAPTER=deepseek
```

### Installed local models (Ollama)

All of these are ready to use — set `MAMMOTH_LLM_ADAPTER` in `.env`:

| Alias | Actual model | Best for |
|---|---|---|
| `hermes` | hermes3:8b | ATLAS tutor, hints, general (default) |
| `deepseek` | deepseek-coder:latest | Code generation |
| `qwen-coder` | qwen2.5-coder:latest | Code generation (alt) |
| `codellama` | codellama:latest | Code generation (fallback) |
| `llama` | llama3.1:8b | General purpose |
| `mistral` | mistral:latest | General purpose |
| `qwen` | qwen2.5:latest | General purpose |
| `phi` | phi3:latest | Fast/lightweight tasks |
| `nous-hermes` | nous-hermes:7b | Instruction following |

**Switch models by changing one line in `.env`:**
```
MAMMOTH_LLM_ADAPTER=deepseek    # DeepSeek reasoning path (cloud)
MAMMOTH_LLM_ADAPTER=hermes      # Hermes3 for ATLAS (local)
MAMMOTH_LLM_ADAPTER=openai      # force OpenAI even if Ollama is running
```

**Ollama must be running** for local models:
```powershell
ollama serve    # start in a separate terminal (or it auto-starts on Windows)
```

---

## 3 — All wired CLI commands

### Start a lesson
```powershell
python -m cli.main atlas lesson "Python for loops"
python -m cli.main atlas lesson "Python lists" --difficulty intermediate
python -m cli.main atlas lesson "Recursion" --module 2 --lesson 1
python -m cli.main atlas lesson "Functions" --llm   # LLM-generated exercise
```

ATLAS will persist lesson chunks into RAG storage when Supabase is configured, so generated or imported lessons can be reused later instead of being re-authored every time.

### Check your current session
```powershell
python -m cli.main atlas status           # shows active lesson + exercise prompt
python -m cli.main atlas status --db      # also fetches the latest mammoth.ai_sessions row
```

### Inspect the curriculum library
- Open **Lessons → Curriculum Library** in the UI.
- It shows the current lesson snapshot, which lessons have persisted chunks, and which ones are still only living in the in-memory curriculum state.

### Submit a solution
```powershell
python -m cli.main atlas submit solution.py
python -m cli.main atlas submit --inline "def solution(a, b): return a + b"
```
On pass: XP recorded in Supabase. On fail: error + TutorAgent hint.

### Advance to the next lesson
```powershell
python -m cli.main atlas next
```
In the UI and over HTTP (`POST /api/atlas/next`), advancing past an exercise that has not passed returns `status: "gated"` with a message and any stall signal. The learner can keep practicing or choose **Continue anyway** (`{"override": true}`), which is audit-logged. In the SDK, `next_lesson()` keeps its old behaviour; pass `require_mastery=True` to get the gate (`LessonGateError`).

### Reset your session
```powershell
python -m cli.main atlas reset
```

### CodingAgent — generate code
```powershell
python -m cli.main atlas code generate "a function that sums a list"
python -m cli.main atlas code generate "binary search implementation"
python -m cli.main atlas code generate "a parser that reads a build log into JSON"
```
Generates solution() + tests + docs, runs tests in sandbox, logs to Supabase.
Works with both OpenAI and all Ollama models.

Use this command for Python/problem-solving work. If the prompt is UI-first (for example `notes panel`, `dashboard`, `component`, `theme`, or `styling`), the CLI now redirects you to the UIBuilder path instead of generating misleading Python:

```powershell
python -m cli.main atlas ui component "upgrade my notes panel"
python -m cli.main atlas ui palette "apply MammothOS command center styling to NotesPanel"
```

The website's Coding conversation also accepts explicitly advice-only prompts
such as "what are your suggestions?" when no implementation is requested.
These return recommendations labeled as advice, not generated code or file
changes. Actual implementation and patch requests retain source requirements
and output checks. Failure messages surface the agent's summary and validation
warnings instead of only `status=error`. This chat behavior does not change the
CLI commands above.

### CodingAgent — refactor a file
```powershell
python -m cli.main atlas code refactor my_script.py             # writes my_script.refactored.py
python -m cli.main atlas code refactor my_script.py --inplace   # overwrites original
python -m cli.main atlas code refactor my_script.py --output out.py
```

### CodingAgent — explain a file
```powershell
python -m cli.main atlas code explain my_script.py
```

### UI scaffolding — generate a starter app
```powershell
python -m cli.main atlas ui scaffold "ATLAS progress dashboard"
```
Creates a Vite + React starter app in `ui/atlas-progress-dashboard`.

Run it locally:
```powershell
cd ui/atlas-progress-dashboard
npm install
python server.py
```
In a second terminal:
```powershell
cd ui/atlas-progress-dashboard
npm run dev
```
Open http://localhost:3000. The Vite frontend proxies `/api/*` to the Python API server on port `8765`, which reads live Supabase metrics from your repo `.env` file.

This is a lightweight first-pass UI workflow: prompt → scaffold app → preview locally → show real ATLAS progress data.

### UI generator baseline verification
From the active worktree root, this PowerShell-native sequence verifies the UI
generator path and the current scaffold target:

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m cli.main atlas ui scaffold "mad architecht command center"
& $py -m cli.main atlas ui component "Create status card component"
& $py -m cli.main atlas ui style "Apply enterprise dark neon style tokens"
& $py -m cli.main atlas ui backend "Generate API hooks for /api/status and /api/agents"
& $py -m cli.main atlas ui graph "Generate simple activity graph module"
& $py -m cli.main atlas ui palette "Generate command palette actions"
& $py -c "import json,pathlib; s=json.loads(pathlib.Path('.mammoth/atlas_ui_state.json').read_text('utf-8')); assert 'mammoth_intro_ai.worktrees' in s.get('active_ui_project',''); print('State check: OK')"
Set-Location ui\mad-architecht-command-center; npm run build; Set-Location ..\..
```

---

## 4 — Adaptive learner model

ATLAS now keeps a lightweight learner profile in `.mammoth/atlas_learner_model.json` and surfaces it in the tutor UI. The model tracks concept mastery, confidence, streaks, error patterns, and recent outcomes so future lessons and hints can be tuned to the student’s current state.

The tutor UI reads this profile through `/api/atlas/status` and shows the recommended difficulty, pacing, and the weakest concepts to focus on next.

---

## 5 — ATLAS plan + execute

ATLAS can now turn the current lesson or exercise into a visible tutor plan. The plan is generated from the active lesson context, executed step-by-step through the agent runtime, and surfaced in the ATLAS tutor page with real progress and step status.

- Use the new **Build Plan** action in the ATLAS lesson page to generate a plan from the active exercise.
- Choose a tutor plan profile directly in the lesson page:
  - **Tutor + Coding** for implementation-heavy work
  - **Balanced** for mixed coaching/execution
  - **ATLAS-first** for more strategic tutoring and safeguards
  - **Autonomous Prep** to include community and custodial readiness steps
- Each plan step is executed by the relevant sub-agent (seed/research/coding/reflection/ops) and reported back to the tutor UI.
- The plan is persisted in the atlas session state so returning to the lesson preserves the most recent plan view.
- Every completed plan now includes an **ATLAS synthesis** block with:
  - learner-facing summary
  - coding brief
  - safe next action
  - checkpoint list distilled from the sub-agent outputs

---

## 6 — ATLAS evals + observability

ATLAS now has a lightweight tutor observability layer in the lesson UI.

- Use **Run Evals** in the tutor page to execute the current smoke checks:
  - onboarding profile persistence
  - adaptive feedback generation
  - resume continuity reconstruction
- Recent eval runs are stored in `.mammoth/atlas_evals.json` and surfaced back into the tutor UI.
- The tutor sidebar now shows compact observability metrics:
  - learner pass rate
  - eval pass rate
  - plan/eval run counts
  - guard trigger rate
  - sandbox success rate
- The tutor page also shows recent plan history so you can track ATLAS orchestration over time.

---

## 7 — Verify Supabase connectivity

```powershell
python .mammoth\check_supabase.py
```
Expected output:
```
OK  mammoth.users accessible
OK  mammoth.progress accessible
OK  mammoth.activity_log accessible
OK  atlas.atlas_progress accessible
OK  atlas.adaptive_metrics accessible
OK  atlas.community_stats accessible
OK  atlas.sessions accessible
```

Show the latest AI session row:
```powershell
python -m cli.main atlas status --db
```

> **If `ai_sessions` shows 404:** Run `.mammoth/supabase_schema.sql` in Supabase
> SQL Editor to create the `mammoth.ai_sessions` table.

---

## 8 — Where things live (source map)

| What | Path |
|---|---|
| CLI commands | `cli/atlas.py` |
| CLI entry point (loads .env) | `cli/main.py` |
| LLM routing factory | `src/mammoth_os/llm_client.py` |
| OpenAI adapter (v2 SDK) | `src/mammoth_os/openai_adapter.py` |
| Ollama adapter | `src/mammoth_os/ollama_adapter.py` |
| Session state (local JSON) | `.mammoth/atlas_cli_session.json` |
| Supabase schema | `.mammoth/supabase_schema.sql` |
| Supabase connectivity check | `.mammoth/check_supabase.py` |
| TutorAgent | `src/mammoth_os/agents/tutor_agent.py` |
| CurriculumAgent | `src/mammoth_os/agents/curriculum_agent.py` |
| CodingAgent | `src/mammoth_os/agents/coding_agent.py` |
| Sandbox runner | `src/mammoth_os/sandbox_runner.py` |
| UI shell + routing + FAB | `ui/mad-architecht-command-center/src/App.jsx` |
| All UI pages | `ui/mad-architecht-command-center/src/pages/` |
| API fetch wrapper + WS helper | `ui/mad-architecht-command-center/src/api/client.js` |
| React polling hooks | `ui/mad-architecht-command-center/src/hooks/useApi.js` |
| Design tokens + CSS | `ui/mad-architecht-command-center/src/index.css` |
| FastAPI backend | `api_server.py` (repo root) |
| Runtime data files | `.mammoth/` (notes, buildlog, sales_log, atlas session, eval history) |

---

## 9 — Mad Architecht Command Center (Main UI)

The primary user interface is a full React SPA located at:
```
ui/mad-architecht-command-center/
```

### Start the full stack

**Terminal 1 — FastAPI backend:**
```powershell
cd C:\Users\runni\mammoth_intro_ai.worktrees\agents-mammothos-atlas-agent-system
.\.venv\Scripts\Activate.ps1
uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — React frontend (Vite):**
```powershell
cd ui/mad-architecht-command-center
npm run dev
```
Open **http://localhost:5173**

### Pages in the UI

| Page | What it does |
|---|---|
| **Home** | Live dashboard: agent status, health dots, build log feed, sales total, quick-copy commands |
| **Agent** | Run any CortexRouter intent (plant_seed, field_ops, research_*, etc.) with live thought stream, approval queue, snapshot rollback, coding shortcuts, and prompt playbook examples |
| **Terminal** | WebSocket terminal wired to the backend. HTTP fallback mode when WS is offline. Quick-action buttons plus ATLAS CLI examples for safe `python -m cli.main ...` runs |
| **Manual** | In-app operator guide for terminal usage, prompt patterns, and recommended workflow habits |
| **Notes** | Full CRUD note-taking, auto-saved to `.mammoth/notes.json` |
| **Modules** | Live scan of all agents in `src/mammoth_os/agents/` |
| **Health** | Real-time service health: Ollama, Supabase, OpenAI, API server — polls every 10s |
| **Log Sale** | Sales tracker: log items + amounts, running total, persisted to `.mammoth/sales_log.json` |
| **Lessons** | Quick-access ATLAS lesson start + embedded tutor chat |
| **ATLAS Tutor** | Full 3-column ATLAS experience: curriculum tree | exercise + code editor | live chat with model selector, lesson memory, and latest submission summary |
| **Build Log** | Log + browse project build entries with tags, persisted to `.mammoth/buildlog.json` |
| **Settings** | System info, env key inspector, ATLAS reset, Dark-only appearance status, AI runtime status |

### Owner isolated validation and coding measurements

The Coding workspace now includes an owner/admin-only, opt-in isolated validation
pilot. It requires an explicitly selected repository and a frozen, expiring
approval. Baseline/candidate checks use disposable worktrees and offline,
non-root, resource-bounded Docker containers. There is no host fallback,
automatic merge or push. Uncommitted checkout content is not included or changed.
The preview remains an unapplied draft until a separate owner approval creates a
commit on a new local `mammoth/owner/<execution-id>` branch. The selected checkout,
HEAD, staged index and remote stay unchanged. Application never merges, pushes or
deploys. It requires successful validation, no observed regression and a fresh
application digest; changed HEAD, expired/reused approvals or changed proposals
are rejected. Mammoth Mind Agent mode and the Coding workspace expose both
approval steps with recorded patch/test evidence. Repository test success is not independent
acceptance verification. Cancellation and restart cleanup are job-scoped; failed
cleanup blocks further owner execution, not the whole platform.

Operators can run `scripts\quality\check_owner_container.py --image
<reviewed-image@sha256:digest> --output-dir <private-evidence-directory>` with
`PYTHONPATH=src`. It exercises the real owner executor with bundled trusted
fixtures, not user code: actual non-root test-process controls, a rejected
failing test, timeout enforcement and specifically named container cleanup.
It never pulls images, changes policy, enables the pilot or falls back to the
host. `verified`, `failed` and `not_verified` receipts are host/image/profile/
timestamp-specific; both nonverified outcomes exit nonzero. Logs require review
before sharing. The manual Owner Container Acceptance workflow offers the same
strict check with a separate operator-approved digest pull (default off).

Local acceptance passed for the existing reviewed Python digest on Linux Docker
29.6.2 on 2026-11-03. It does not validate frontend profiles, arbitrary repository
dependencies, deployed infrastructure or hostile-code isolation. Hosted legacy
Docker smoke still lacks runtime evidence after namespace/mount startup failure.
That failure now has an actionable classification and does not produce speculative
seccomp relaxation suggestions; repair runner infrastructure, not isolation flags.

The profile picker uses `isolation.profiles` from a bounded offline image probe.
Unavailable tools are rejected before freezing a proposal; installed tools do
not imply installed project dependencies or relevant coverage. Excluded
environments are omitted before checking Git entry types; source symlinks and
submodules remain unsupported and report the blocking path. The separate UI
Build GitHub workflow verifies lockfile installation and the production Vite
build after publication. Separately, optional `ui_build` and `ui_component`
profiles provide pre-application production compilation and narrow actual
React trust-row rendering checks. They require a separate reviewed
`MAMMOTH_OWNER_UI_IMAGE`, with locked dependencies baked in, 768 MB memory and
120 seconds per phase. Dependency changes require an image rebuild; runtime
stays offline. Component rendering does not prove browser interactions or
general acceptance.

The additive `ui_browser` profile first builds production assets, then runs the
four workspace browser suites (ATLAS, artifacts, uploads, reliability) using
locked Playwright and Chromium dependencies baked into the reviewed frontend
image. The configuration is image-owned, uses one worker, forbids focused tests,
and rejects empty, skipped, flaky or failing results.
Stable hashed test identities also retain baseline regression evidence; removing
a previously passing test blocks branch application even if the remaining suite passes.
It does not run arbitrary
test commands or download dependencies during validation. The outer Docker
boundary remains offline, non-root, read-only, capability-dropped and
no-new-privileges, without host execution or a Docker socket. Chromium uses
Playwright's container-compatible non-sandboxed mode **inside this boundary**;
this is not an additional browser sandbox or a hostile-code VM. Browser-only
limits are 1024 MB memory, 256 MB each for work/tmp storage, a 64 MB per-file limit
for Chromium shared-memory files, 256 PIDs and 600 seconds per phase. Existing
profiles retain their limits. No extra container privileges are granted.

UI JSX/TSX/CSS changes conservatively require an `acceptance` object containing
nonempty `expected_behavior` and `regression_tests` arrays, plus an edit to a
declared test file in that suite. Examples of outcomes: closing without saving,
successful-save dismissal, retained drafts, keyboard access, mobile fit and
account switches. This is a reviewed test requirement, not proof that generated
tests are sufficient or honest; never weaken tests to make a proposal pass.
`ui_browser` is preferred when available. A build-only proposal can still be
separately approved, but its browser behavior remains explicitly `not_tested`.

API evidence, approval cards and run handoffs separately expose build
`passed|failed|not_tested` and behavior `verified|failed|not_tested`. A failing
browser suite can retain a passed build result. "Verified" means the recorded
workspace browser tests passed, not independent acceptance or certification.
Existing records without new evidence default to `not_tested`.

Operators must rebuild and pin the reviewed frontend image before `ui_browser`
becomes available; existing images report it unavailable, never fall back to
host execution. The image now includes root test manifests as well as UI
manifests, so either dependency change requires review/rebuild. The browser
configuration serves baked Monaco assets through local Vite using
`VITE_MONACO_BASE_URL`; production's default loader behavior is unchanged when
this variable is unset. Deployments may set it to their own hosted `vs` directory.

Preparation accepts full `{path, content}` changes or small
`{path, edits: [{old, new}]}` changes, resolved against committed base bytes.
Each old string must match exactly once. New files require content.
Coding runs can require proposal, validation or application through **Required
result**; both SDKs expose the same optional completion goal. Recorded `progress`
tracks reads/hashes, frozen jobs, checks, blockers and branch/commit evidence.
Goals can only increase. Unsupported completion claims end as incomplete,
not successful work; normal replies say Answered. Same-run observation recall
reuses saved reads only while accessible file hashes still match. Plans are
model-written summaries, not independent evidence.

Refresh isolation and HEAD only rereads the selected backend checkout and probes
installed images. It does not fetch GitHub, change branches or include dirty
files; connected clones have a separate Sync action. A new run can refresh
owner status through its tool without a manual panel refresh. Frozen proposals
keep their original base; changed HEAD requires fresh preparation and approval.
Applied owner branches do not move the selected checkout.
For managed validated/applied goals, the runtime queues approvals from fresh
receipts; model decisions cannot call run/apply with guessed execution identities.
Failed checks require a corrected candidate against committed source, a new job
and fresh validation approval, then separate application approval after passing.
Bounded failure excerpts persist in saved progress for review and repair; they
do not establish that the model can reliably fix every failing check.

Reply confidence is unassessed unless explicitly supplied with assessment
metadata: chat/tutor responses now return null, not a synthetic 74%/80%.
Provider identity and source counts remain visible. Legacy heuristic scores
render Not assessed, and explicit shared-component scores are uncalibrated
reported values, never a measured correctness probability. Learner mastery
and exercise results are unaffected.

The opt-in `python -m mammoth_os.workflow_benchmark --model` measures the real
agent loop and two scoped approvals on disposable Python fixtures with fixed
independent acceptance tests. It records failures, tokens and latency, not
invented billing estimates. It never approves real repository actions.
Small samples are smoke measurements, not evidence of arbitrary-repo autonomy.
Runs remain limited to eight model decisions per segment, with up to two
continuations. Use **Continue task** to preserve saved progress rather than
starting the same investigation over. This does not bypass either approval.

Enable `MAMMOTH_OWNER_EXEC_ENABLED=1` only on an operator-reviewed backend host with
Docker and a locally installed immutable `MAMMOTH_OWNER_EXEC_IMAGE` digest.
The reviewed image needs Python 3.11.8+ and any tools/dependencies required by the
fixed unittest/pytest/Node test profile. Containers share the host kernel and
are not a hostile-code VM. See the README's **Owner isolated coding validation
pilot** for limits, SDK methods, configuration and benchmark commands.

`python -m mammoth_os.coding_benchmark` measures the harness using known solutions;
`--model` explicitly spends provider credits on CodingAgent proposals evaluated
against fixed independent tests. Reports distinguish reference/model modes,
failures, observed regressions, p95 latency and only actually reported costs.
Neither reference success nor the small synthetic model corpus certifies general
coding reliability or enables autonomy.

### Agent Console safety flow
- Turn on **Preview first** before using the coding agent for file edits.
- Switch to **Plan + Execute** mode to run multi-agent orchestration from one objective.
- Use **Plan Profile = ATLAS-First** to keep seed/strategy framing at the front of the run.
- Use **ATLAS + Coding Assistant** when you want coding depth without making coding the top-level driver.
- Approved edits are queued in **Pending Approvals**.
- Once approved, the backend applies the change and creates a rollback entry in
  **Rollback Snapshots**.
- Use **Restore** on a snapshot to reverse the approved change.

### Coding shortcuts
When **coding_agent** is selected in the Agent Console, quick templates are
available for:
- `/create`
- `/write`
- `/patch`
- `/insert`

These are the safest way to teach yourself the command shapes while keeping
approval mode on.

### Prompting guidance
- A short sentence is valid in the Agent Console.
- Better prompts usually include:
  1. the outcome you want
  2. the files, module, or page in scope
  3. any constraints like "keep preview first on" or "preserve existing navigation"
- Use **Plan + Execute** for multi-step objectives, tutorials, onboarding, or cross-surface changes.

### Terminal CLI guidance
- The UI terminal is meant to support the same safe MammothOS commands you would run in PowerShell.
- Supported examples now include:
  - `python -m cli.main atlas status`
  - `python -m cli.main atlas code generate "build a MammothOS notes panel"`
  - `python -m cli.main atlas ui component "create a neon command-center status card"`
- For safety, chained shell expressions and metacharacter-heavy commands are blocked in the UI terminal.
- Long-running `atlas code` and `atlas ui` commands get longer backend timeouts than simple status/health calls.

### ATLAS learning memory
The ATLAS Tutor sidebar now shows:
- current lesson resume state
- saved lesson history
- total lesson count in the loaded curriculum
- latest submission outcome and coaching hint
- welcome-back lesson summary when returning to a prior lesson
- deterministic prior-work summary recovered from lesson history, even for legacy state shapes
- quick pull-up actions for related notes and saved flashcards
- onboarding profile controls for experience, pacing, style, goals, and focus areas
- learner memory map summary with recent lesson/concept nodes

### Mammoth Mind quick panel (header pill; formerly the floating ATLAS FAB)
A **Mammoth Mind** pill sits in the header's top-right next to the notification bell on **every page**.  
Click it and a quick chat panel opens under the header (a bottom sheet on mobile). Escape closes it, and **Full view →** opens the Mammoth Mind chat page.  
On the chat page the panel uses `POST /api/mammoth/chat`; elsewhere it uses `POST /api/atlas/chat` with full chat history.

Phase 2 upgrades now wired in the quick panel:
- **Tutor mode** + **Plan + Build mode** toggle
- **No-cheat guard** toggle (blocks direct answer dumping for active exercises)
- automatic **fresh exercise regeneration** when guard is triggered (if enabled)
- page-aware context payload (current page, selection, lesson snapshot) so ATLAS can observe what you're working on
- usage telemetry events (`fab_usage_events`) recorded for future monetization analytics

### Appearance
**Dark** `#050608` is currently the only supported appearance while the platform
is being polished. Aurora is paused; the sidebar selector and Settings toggles
are removed. Saved Aurora and legacy `darker`/`midnight` preferences migrate to
Dark automatically. Old inline theme colors are cleared to prevent unreadable
dark-on-dark text. Settings shows the active appearance without an inactive toggle.

### Runtime Status Bar
- Runtime health is a color-coded pill in the header beside Mammoth Mind: green for healthy, amber for degraded, and red for blocked.
- Press the pill to expand provider, model, fallback, and next-action details; press it again to collapse. The detail popover is transient and starts collapsed.
- The pill replaces the in-content runtime banner, giving the current page more room.

### Mammoth Mind response style
- Mammoth Mind should match the response to the ask: quick and conversational for simple questions, clearly structured and thorough when a request is multi-part, technical, consequential, or explicitly asks for depth.
- Structure is used when it helps, not forced onto every reply. Complex answers lead with the outcome and then cover rationale, caveats, and useful next steps.
- Mammoth Mind can explain its rationale and evidence, but does not expose private chain-of-thought.
- The chat feed now meets the composer without a horizontal divider.
- Agent runs distinguish incomplete work from completion. Malformed decisions retry once without consuming a task step; offline or invalid output is never marked successful.
- Eligible partial/recoverable runs offer **Continue task** in Mammoth Mind and the Coding workspace. It retains saved evidence, rechecks repository access and approvals, and uses additional credits (up to two continuations). Expand the timeline for reported model-call diagnostics. This does not certify task correctness.
- Recognized OpenAI GPT-4o/4.1 models use schema-constrained decisions with only authorized tool names. Other providers retain validated compatibility formats. Tool arguments are checked before approval/execution, and diagnostics display the selected protocol. Model defaults and tutor output remain unchanged.

### Design System
- Colors: `--shell`, `--photon: #4da6ff`, `--cyan: #00f5d4`, `--violet: #b47cff`
- Glass cards: `backdrop-filter: blur(16px)`, `rgba(13,17,23,0.7)`
- CRT scanline overlay on entire app
- Fonts: Inter (UI), JetBrains Mono (code/terminal)

### API endpoints (api_server.py)

| Endpoint | Purpose |
|---|---|
| `GET /api/status` | Python version, uptime, agent count, engine count |
| `GET /api/health` | Service connectivity: Ollama, Supabase, OpenAI, env keys |
| `GET /api/agents` | List all agent files from `src/mammoth_os/agents/` |
| `POST /api/run` | Run a CortexRouter intent (`{intent, context}`) |
| `POST /api/plan-execute` | Run orchestrated multi-agent plan (`{objective, plan_profile, approval_mode}`) |
| `GET /api/autonomous/runs` | Unified autonomous run feed (`plan_execute` + `atlas_plan`) with status/progress summary |
| `GET /api/atlas/status` | Current ATLAS session: lesson, exercise, curriculum, chat history |
| `POST /api/atlas/lesson` | Start a lesson (`{topic, difficulty, module, lesson, llm}`) |
| `POST /api/atlas/submit` | Submit code (`{code}`) → graded result + adaptive feedback payload |
| `POST /api/atlas/onboard` | Save learner onboarding profile (`approval_mode` supported for preview-first) |
| `POST /api/atlas/next` | Advance to next lesson |
| `POST /api/atlas/back` | Return to previous lesson with resume packet |
| `GET /api/atlas/flashcards` | Generate + save lesson flashcards for recall |
| `POST /api/atlas/regenerate` | Generate a new exercise variant for the current lesson |
| `POST /api/atlas/learner/reset` | Reset learner model (`approval_mode` supported for preview-first) |
| `POST /api/atlas/reset` | Reset ATLAS session (`approval_mode` supported for preview-first) |
| `POST /api/atlas/chat` | Chat with ATLAS tutor (`{message, model?, mode, strict_guard, regenerate_on_guard, page_context}`) |
| `GET /api/models` | All available models: active adapter, model, Ollama status, installed models |
| `GET/POST /api/notes` | Note CRUD |
| `GET/POST /api/buildlog` | Build log entries |
| `GET/POST /api/logsale` | Sales log entries |
| `GET /api/modules` | Scans real agents directory |
| `POST /api/terminal/exec` | HTTP terminal fallback: run an allowed command, returns stdout/stderr/exit_code |
| `WS /ws/terminal` | WebSocket terminal with streaming stdout/stderr |

---

## 8 — Project status (as of August 2026)

### Done and working ✅
- Full ATLAS lesson → submit → pass/fail loop wired to Supabase
- adaptive_metrics and atlas_progress written on each submission
- mammoth.ai_sessions logged on every atlas code generate call
- CurriculumAgent reads real DB lessons with template fallback
- CLI auto-resolves UUID from public.profiles
- `.env` auto-loaded on every CLI run
- All 11 local Ollama models wired (hermes3, deepseek-coder, codellama, llama3.1, mistral, qwen2.5, qwen2.5-coder, phi3, nous-hermes)
- OpenAI adapter updated to v2 SDK (gpt-4o-mini default)
- LLM auto-detection: Ollama running → use it; OPENAI_API_KEY set → use that
- Mad Architecht Command Center: 11-page React UI fully wired to FastAPI backend
- Mammoth Mind header pill + quick panel on all pages (replaced the floating ATLAS FAB)
- Mammoth Mind agent runs (`mammoth.run.v1`): plan, tool calls, approvals, and reasoning/run traces
- Repo lockdown: no repo selected means no repo context; the platform repo is owner-only; users connect their own repos
- Mammoth Paths workspace SDK (Python `MammothPaths`, JS `@mammothos/paths`) with server-side tier gates and per-user build log
- Tutor delivery: lesson manifests, stall telemetry, comprehension gate with override, retrieval dedupe
- Research hygiene: reasoning stripped to traces, relevance/disambiguation filtering, dedupe, truncation repair
- Dedicated ATLAS Tutor page (3-column: curriculum | editor | chat)
- Dark-only appearance with automatic migration of saved Aurora/legacy preferences and no inactive theme controls
- Terminal WebSocket + HTTP fallback
- All data files auto-initialized in `.mammoth/`
- Branch pushed to origin: `ui/compliance-legal-shell`
- Agent Console run history (browser-local, replay/clear, up to 20 entries)
- Plan + Execute multi-agent orchestration mode in Agent Console
- ATLAS-First plan profile (seed/strategy framing before code)
- Agent smoke test workflow with baseline health validation
- **Phase 1 complete:** learner onboarding profile, memory graph, `POST /api/atlas/onboard`,  
  `POST /api/atlas/back` (resume packet), `GET /api/atlas/flashcards` (recall),  
  welcome-back lesson summary in ATLAS Tutor UI

### Next up (priority order)
1. **Phase 2** — Adaptive lesson delivery (see roadmap below)
2. `atlas progress` CLI command — show XP, lessons completed, streak from Supabase
3. Write `atlas.sessions` rows on lesson start (track topic history in DB)
4. ReasoningAgent hints on submission fail (chain-of-thought explanation)
5. Ascension Metrics page — real learning stats pulled from Supabase `atlas_ascension` table
6. Completion Graph — visual skill tree of completed vs pending lessons

### Parked
- Docker sandbox seccomp tuning (review-only CI artifacts; `sandbox-diagnostics`
  now records verified/failed/not_verified Docker-only smoke evidence without
  host fallback. Diagnostic collection is not owner or production isolation
  acceptance. Missing infrastructure remains unverified; observed smoke or
  hardening failures fail the job. See the README's legacy sandbox CI section.)
- Full LLM lesson generation at scale (`ATLAS_EXERCISE_GEN_MODE=llm`)
- Wednesday gothic neon theme variant

---

## 9 — ATLAS Upgrade Roadmap

> **ATLAS is the top-level system.** The CodingAgent is ATLAS's teaching assistant —  
> it generates, explains, and refactors code *in service of ATLAS's adaptive learning goals.*  
> The original idea: a recursive, self-improving, individualized cognitive tutor OS.  
> This roadmap is the execution plan for that vision.

---

### Phase 1 — Onboarding + Learner Memory Foundation ✅ COMPLETE

**Goal:** Know the student before the first lesson starts.

| Feature | Status |
|---|---|
| Learner model file (`learner_model.py`) | ✅ Done |
| Onboarding profile (experience, pacing, style, goals, focus areas) | ✅ Done |
| Memory graph (concept nodes + lesson edges) | ✅ Done |
| `POST /api/atlas/onboard` endpoint | ✅ Done |
| Onboarding UI in ATLAS Tutor sidebar | ✅ Done |
| Learner memory map display in UI | ✅ Done |
| Welcome-back lesson summary on return | ✅ Done |
| Flashcard recall (`GET /api/atlas/flashcards`) | ✅ Done |
| `POST /api/atlas/back` resume packet | ✅ Done |

---

### Phase 2 — Adaptive Lesson Delivery 🚧 IN PROGRESS

**Goal:** ATLAS selects the *right lesson* at the *right difficulty* based on the learner model.

| Feature | Plan |
|---|---|
| Learner-model-informed lesson selection | Pull weakest concepts from mastery map and weight curriculum accordingly |
| Dynamic difficulty scaling | Adjust difficulty based on streak + recent outcome history from learner model |
| Hint depth calibration | Measure confidence score → calibrate hint verbosity (less hand-holding for high confidence). **Baseline shipped** via `adaptive_coaching.hint_depth` |
| Pacing adapter | Honor onboarding `preferred_pacing` field to space exercises / explanations |
| Post-lesson mastery update | Write concept mastery scores back to learner model after every submission. **Shipped** with mastery/confidence deltas in `recent_outcomes` |
| Remediation branching | Trigger support mode for repeated failures, with optional automatic exercise regeneration |
| Lesson manifest | **Shipped**: `lesson_manifest` (prerequisites, sample input, expected output, done-when criteria) derived from real lesson data |
| Per-step stall telemetry | **Shipped**: `lesson_telemetry` + `stall` signal (3 fails in a row / same error twice / 20 min idle) with one targeted suggestion |
| Comprehension gate | **Shipped**: `/api/atlas/next` gates unpassed exercises; explicit, audit-logged "Continue anyway" override |
| Retrieval hygiene | **Shipped**: deduped, labeled lesson chunks before top-k |
| Anti-cheat continuity | If direct-answer request is detected on active exercises, ATLAS refuses and can auto-generate a parallel variant |
| Supabase session rows on lesson start | Write `atlas.sessions` entries for full lesson-history tracking |
| `atlas progress` CLI command | Display XP, lessons completed, streak, weakest concepts from DB + learner model |

---

### Phase 3 — ReasoningAgent Chain-of-Thought Hints

**Goal:** When a student fails, ATLAS explains *why* step-by-step, not just "wrong."

| Feature | Plan |
|---|---|
| ReasoningAgent integration on fail | CodingAgent fails → ReasoningAgent generates chain-of-thought walkthrough |
| Socratic probe mode | ATLAS asks follow-up questions instead of immediately revealing the fix |
| Error pattern tracking | Repeated errors update `error_patterns` in learner model → ATLAS flags known sticking points. **Foundation shipped** in learner model + adaptive coaching |
| Contextual micro-lessons | When a concept is repeatedly failed, inject a targeted micro-lesson before the next attempt |
| Return continuity hardening | **Shipped** — deterministic resume packets on status reads/transitions, historical submission recovery, legacy study-aid normalization, note/flashcard pull-up fallback |

---

### Phase 4 — Ascension Metrics + Skill Tree

**Goal:** Make the student's growth visible and motivating.

| Feature | Plan |
|---|---|
| Ascension Metrics page | Real learning stats from Supabase `atlas_ascension` table |
| Completion Graph | Visual skill tree: completed vs pending lessons, mastery color-coded |
| Streak + XP leaderboard (personal) | Self-comparison over time, not competitive |
| Weekly focus report | ATLAS generates a "here's what you learned this week" summary |
| Concept dependency graph | Show which concepts unlock which advanced topics |

---

### Phase 5 — Multi-Agent Cognitive Loop (Recursive Self-Improvement)

**Goal:** ATLAS + CodingAgent teach each other. The system improves its own curriculum.

| Feature | Plan |
|---|---|
| ATLAS evaluates CodingAgent output | ATLAS scores code quality against learner goals, not just correctness |
| CodingAgent proposes curriculum additions | When generating code solutions, agent flags concepts student hasn't seen yet |
| Curriculum self-amendment | OrchestratorAgent can add new lessons to the curriculum based on learner model gaps |
| Agent role hierarchy enforced in UI | Plan Profile = ATLAS-First locks ATLAS as strategy layer; CodingAgent always subordinate |
| Recursive improvement loop | Each lesson cycle produces learner model updates → curriculum updates → better next lesson |

---

### CodingAgent Upgrade Plan (parallel track, subordinate to ATLAS)

The CodingAgent is ATLAS's teaching assistant. These upgrades make it a better one:

| Upgrade | Purpose |
|---|---|
| Per-run model selection in Agent Console | Let ATLAS choose the best model for each coding task |
| Reasoning trace display | Show CodingAgent's thought steps live in the UI |
| Context-aware code generation | CodingAgent reads learner model before generating — calibrates complexity to student level |
| File approval + rollback | Already wired; ensure rollback snapshots preserve ATLAS lesson state too |
| Smoke test on every code write | Run sandbox tests automatically after every CodingAgent file write |

---

## 10 — Quick troubleshooting

| Symptom | Fix |
|---|---|
| SKIP: SUPABASE_URL not set | Check .env file exists at repo root with correct keys |
| Invalid API key (Supabase) | Wrap JWT in double-quotes in .env |
| permission denied for table | Run GRANT SELECT ON table TO service_role; in Supabase SQL Editor |
| ai_sessions write failed 404 | Run .mammoth/supabase_schema.sql in Supabase SQL Editor |
| [LOCAL_ADAPTER] in output | Ollama not running (ollama serve) and no OPENAI_API_KEY set |
| Ollama not reachable | Start Ollama: ollama serve |
| [CodingAgent:WARN] no sub-engines | Informational only — safe to ignore |
| check constraint adaptive_metrics | Already fixed — difficulty maps to easy/medium/hard |
| UI shows blank / no data | Start the FastAPI backend first: `uvicorn api_server:app --reload` on port 8000 |
| Terminal says DISCONNECTED | Backend not running. UI auto-switches to HTTP fallback mode — commands still work via POST /api/terminal/exec |
| `atlas code` feels unsupported in the UI terminal | Use the full CLI form like `python -m cli.main atlas code generate "..."`. The terminal now supports safe ATLAS CLI command trees and gives code/UI flows longer timeouts |

---

## 11 — Run the full test suite

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q
```

Tests that hit Supabase or OpenAI are skipped when credentials not set — safe offline.


---

## 9 — Compliance, Legal & Monetization

### 9a. Product pages (in-app)

Three public-facing product pages are now wired into the MammothOS sidebar under the **Product** section:

| Page | Route key | Description |
|---|---|---|
| Landing Page | `landing` | Hero, feature grid, free/pro tiers, legal footer |
| Pricing | `pricing` | 3-tier grid (Explorer / Pro / Enterprise) + FAQ |
| Legal & Compliance | `compliance` | 4-tab legal: Terms, Privacy, Acceptable Use, Disclaimer |

All pages use `setPage` prop for navigation — no separate router needed. A compliance footer strip (Terms · Privacy · About) also appears at the bottom of the sidebar.

---

### 9b. Terms of Use (summary)

- MammothOS is an AI-assisted educational platform for personal and educational use.
- ATLAS is a learning aid — not professional instruction, therapy, or certified education.
- Do not use MammothOS to cheat on exams or circumvent academic integrity policies.
- Users retain ownership of their submitted code and notes. MammothOS makes no claim.
- By using the platform you agree to these terms. Full text available in-app under **Legal & Compliance**.

---

### 9c. Privacy Policy (summary)

- Data collected: lesson history, onboarding profile, learner model state, submitted code.
- Storage: local browser session + your local Supabase instance. No third-party analytics.
- AI providers (OpenAI, Ollama) process prompts per their own terms.
- We do not sell, rent, or share personal data.
- Delete your data anytime: Settings → Reset Session.

---

### 9d. Acceptable Use Policy

- ATLAS is a coach, not a solution generator. Do not use it to produce work you submit as your own.
- Do not attempt to bypass the no-cheat guard via prompt engineering.
- Do not use MammothOS for harmful, abusive, or illegal content generation.
- Violations may restrict access to advanced features.

---

### 9e. Monetization tiers

| Tier | Price | Status |
|---|---|---|
| **Explorer** | Free, forever | ✅ Active |
| **Pro** | ~$12/mo (est.) | 🔜 Coming soon |
| **Enterprise / Team** | Contact us | 📅 Future |

**Explorer** includes: ATLAS tutor chat, adaptive pacing, lesson resume, flashcards/quiz, basic evals, local storage.

**Pro** adds: multi-agent plan orchestration, all plan profiles, Supabase sync, eval history dashboard, audit export, coding agent with approval workflow, priority model routing.

**Enterprise** adds: team dashboards, cohort analytics, custom curriculum authoring, LMS integration, white-label ATLAS, fine-tuned models, SLA.

> **Monetization note:** No formal patents have been filed. "Patents pending on adaptive tutor and memory graph methodologies" is forward-looking product positioning language. All monetization scaffolding is designed to be wired to Stripe + Supabase entitlement sync when billing is ready.

---

### 9f. Entitlement API

Two routes control feature gating:

**`GET /api/entitlements`** — returns current tier and feature flags:
```json
{
  "status": "ok",
  "tier": "explorer",
  "features": {
    "atlas_tutor": true,
    "adaptive_pacing": true,
    "multi_agent_orchestration": false,
    "supabase_sync": false,
    ...
  },
  "upgrade_cta": "pricing"
}
```

**`POST /api/entitlements/tier`** — set tier (admin/testing):
```bash
curl -X POST http://localhost:8000/api/entitlements/tier \
  -H "Content-Type: application/json" \
  -d '{"tier": "pro"}'
```

Valid tiers: `explorer`, `pro`, `enterprise`. Tier is persisted to `.mammoth/atlas_state.json`.

---

### 9g. Compliance and monetization scaling plan

| Phase | Feature | Status |
|---|---|---|
| ✅ Phase 6a | Product pages (Landing, Pricing, Compliance) | Done |
| ✅ Phase 6b | Entitlement API with tier persistence | Done |
| 🔜 Phase 7 | Stripe integration for Pro subscriptions | Planned |
| 🔜 Phase 8 | Supabase user accounts + tier sync | Planned |
| 🔜 Phase 9 | Team dashboards and cohort reporting | Planned |
| 🔜 Phase 10 | White-label ATLAS for schools/bootcamps | Future |

---

### 9h. Legal positioning

MammothOS is positioned as an **educational AI assistant**:
- Not a covered educational institution (not FERPA-regulated as a software vendor)
- Not intended for users under 13 (COPPA safe harbor requires collecting no data from minors)
- Not providing certified instruction or professional advice
- All AI outputs carry an implicit "verify before use" disclaimer surfaced in the Disclaimer tab

When seeking investment, partnerships, or enterprise contracts: lead with the adaptive tutor story, the memory graph, and the no-cheat guard — these are your key differentiators.
