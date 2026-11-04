# MammothOS Feature Handbook

## What this handbook covers

This is the explanation-first companion to the in-app Manual: what each main
workspace feature is for, how to choose it, and what its results do **not** prove.
Its merged baseline includes PR #26 (2026-11-03); operator container-evidence
refinements describe this source edition and require deployment too. This is not a
certification of the version currently running on your server. Availability also
depends on your account, plan, operator configuration and connected providers.

Read this file offline, or ask the **MammothOS Guide** lane or `/guide` to explain
a specific topic. The Guide uses curated documentation bundled with the running
server. Merging a documentation update does not update an already-running server.
The Guide is an explanation aid, not a live health check or proof of correctness.

## How the Guide stays current

The server reads its allowlisted public documentation on each Guide request,
rather than keeping one permanent model-written summary. Relevant heading-based
excerpts are selected for the question. A `docs_revision` content fingerprint
identifies that documentation bundle; it is not a software release number.

For signed-in callers, the server also supplies a request-local capability
snapshot from the existing permission-filtered tool registry and MCP catalog,
canonical recursive capability/limits and workspace access checks. It records
when it was observed. Tool names, permission tiers and approval requirements are
available; private server URLs, credentials, operator logs and other users'
records are not included. Anonymous questions get public documentation only.

This refresh is a read, not a background repository sync, model call, deployment,
or health probe. Installing/deploying new documentation is still necessary when
the product changes. There is no automatic fetch of the platform repository.
Configuration can be enabled while its external provider is unavailable.

Ask "What is documented, what is available to me now, and what remains
unverified?" The Guide should prefer explicit current capability values over
conflicting prose and disclose the conflict. It cannot guarantee that every
answer is accurate or that every feature has been operationally tested.

## Quick choice: which feature should I use?

| Your goal | Start here | Why |
| --- | --- | --- |
| Ask, brainstorm or understand an error | Mammoth Assistant | A normal conversation is usually enough. |
| Work through alternatives and tradeoffs | Reasoning lane | Frames a decision; does not automatically enable recursive review. |
| Inspect your code or propose a change | Coding lane / Agent Workspace | Uses an explicitly selected repository and records tool evidence. |
| Get source-backed information | Research lane | Sources still need checking for relevance and currency. |
| Learn how MammothOS works | MammothOS Guide | Read-only explanation from published docs. |
| Critique and refine one difficult, bounded result | Recursive review in a supported Agent lane | Adds a separate critique and possible revision pass. |
| Inspect a document's later sections | File library, Browse indexed text | Sequential access is more predictable than topic search. |
| Learn through exercises | ATLAS tutor | Lessons, practice and comprehension checks rather than general task execution. |
| Embed the workspace in other software | Mammoth Paths SDK | Runs, events, recovery and workspace records. |
| Embed teaching in other software | Mammoth Mind tutor SDK | Tutor sessions and learning delivery, not workspace administration. |

## Mammoth Mind: a conversation with optional actions

Mammoth Mind is the chat workspace. A lane changes the kind of help requested;
it is not a permission grant, and selecting a more analytical lane does not
guarantee a more accurate answer.

In **Agent** mode the runtime can plan, use permitted tools and collect evidence.
Expand the run timeline to see what happened. **Classic** chat is a conversational
path, not the same tool-execution workflow; slash commands and attachment
messages use that path automatically.

Use ordinary chat for explanations, wording and brainstorming. Use Agent mode
when the answer depends on inspecting source or performing a supported workflow.
Give it a goal, a bounded target, constraints and a measurable definition of done.
For example: "Inspect this module, explain the failure, and propose the smallest
fix. Do not apply it. Include a regression-test plan."

## The Guide lane: explanations, not operations

The MammothOS Guide is the right place for questions such as "When should I use
recursive review?" or "What does validated actually mean?" Ask for examples,
tradeoffs or a walkthrough in plain language.

It draws from selected public product guides, including this handbook. It does
not need private platform repository access to explain product behavior. Its
documentation search is bounded lexical retrieval, not guaranteed exhaustive
reading. A vague question may miss a detail; naming the feature helps.

The Guide does not modify files, execute code or independently check your
deployment. Ask a task-capable lane for real work. An answer describing a feature
does not prove that the feature is enabled, healthy or available to your account.
If source documentation is absent, the correct answer is to disclose that gap,
not invent settings or promise capabilities.

## Recursive review: what it actually does

Recursive review is an optional bounded **plan, execute, critique, route** loop.
The executor attempts the task using available tools; a critic evaluates the
result. A passing critique routes to a final synthesis. A failing critique can
return to planning for another pass within the allowed iteration limit. An
uncertain, low-confidence critique can pause for human judgment.

This is an opportunity to catch omissions and improve a draft, not independent
verification. The roles can share provider/model limitations and make correlated
mistakes. A critic's confidence is a routing signal, not the probability that the
answer is true. Passing critique does not replace tests, source inspection or
approval to execute changes.

It is **off by default** and is not enabled just by selecting the Reasoning lane.
Supported Agent lanes are Assistant, Reasoning, Research and Coding. Find the
toggle under **More chat options**. It is not a promise of unlimited autonomous
work or an automatic whole-document review.

## When recursive review is useful

Choose it when one bounded task benefits from a deliberate challenge pass:

- Compare two implementation approaches against explicit constraints.
- Review a proposed change for missing acceptance criteria and revise the draft.
- Check a short technical proposal for contradictions and unsupported claims.
- Refine a source-backed answer while retaining references to the inspected text.

Define the target and the review criteria before starting. A useful request is:
"Review this proposed caching design against invalidation, tenant separation and
failure recovery. Identify evidence gaps, revise once if necessary, and separate
tested facts from recommendations."

Keep related evidence available, but avoid attaching an entire unrelated archive.
If there are several independent goals, finish a coherent unit before beginning
another. Deterministic checks often provide more value than another model opinion.

## When not to use recursive review

Leave it off for greetings, simple facts, routine rewriting, navigation questions,
or tasks a single source lookup or test can settle.

Do not use it as a substitute for expert sign-off on high-stakes decisions,
authorization to change a repository, real execution evidence, or guaranteed
exhaustive reading. It cannot repair missing source extraction or make an
unsupported validation environment compatible with your project.

Avoid "review everything until perfect." It has no measurable endpoint and can
consume the budget repeating context. First narrow the scope and define what
evidence would establish completion. If a normal run has already found a concrete
blocker, resolve that blocker rather than paying for another critique of it.

## Recursive review costs and token-cap stops

A successful first pass normally needs at least four model completions; tools,
revisions and retries add more. Recursive review can cost materially more than a
normal run. It is not a credit-saving switch.

Default ceilings are two planning iterations, 64,000 reported tokens, 180 active
seconds and 12 tool attempts. Server maxima are three iterations, 128,000 tokens,
300 seconds and 20 tool attempts. Waiting for human review is excluded from
active runtime time. These limits are not dollar reservations.

The planner and critic each have a 2,048-token output ceiling. Other stages keep
their own output allowances, subject to remaining budget. The runtime also leaves
bounded headroom for synthesis; it cannot guarantee the later prompt will fit.

Input admission is recomputed for the actual provider attempt, including fallback
and conversation background. Known official OpenAI models use local tokenizer
text counts plus byte allowances for the shared request envelope/schema and
overhead. Other models/endpoints or unavailable tokenizer assets use a labeled
**UTF-8 byte upper bound**. This is not exact server-side chat tokenization.
A prompt can still be refused while reported usage remains below the overall cap. An output cap, an
input-admission refusal and a provider failure are different problems.
`insufficient_call_allowance` identifies an admission refusal; missing provider
usage stops accounting explicitly. Estimates are never actual billed usage.

## What to do after a recursive review stops

Open the timeline and Run Review. Check the stage, stop reason, configured limits,
reported usage, last-call input/output allowances and saved completed stages.
A saved executor draft may be available under **recursive review incomplete,
not verified**. Read it as unfinished work, not an accepted final answer.

Human-review approval permits synthesis; it does not approve unrelated tools or
repository writes. Saved approval state can be recovered without replaying
completed roles. History recovery is read-only and does not spend model credits.

Do not confuse that recovery with a new budget after a token-cap stop. Cap stops
do not currently offer automatic larger-budget continuation. The ordinary
**Continue task** action is only for eligible unfinished runs, uses more credits,
and allows up to two continuations; it is not universal.

For diagnosis, retain the run ID and its saved trace, not just the final model
paragraph. An explicit JSON export can contain prompts, source excerpts and tool
arguments: inspect it before sharing and remove secrets or personal data.

## Documents: uploaded, extracted, indexed, selected and reviewed

These are different milestones:

1. **Uploaded:** the file reached storage.
2. **Extracted:** supported text was recovered from the original.
3. **Indexed:** extracted text was split into source-located sections.
4. **Selected:** some sections were retrieved for a request or preview.
5. **Reviewed:** a model actually assessed the required material with evidence.

Uploading a file does not establish the other four. Search returns relevant
excerpts, not every section. Initial chat context includes up to three sections
per attached file and up to four files. With no lexical matches, overview samples
are distributed across the document, including its end. This is not a full read.

The extraction ceiling is 2,000,000 characters and 2,000 source units. Image-only
or scanned content needs OCR; OCR is not enabled. Unsupported content and
extraction limits can leave gaps even when all indexed sections are accessible.
Always retain extraction warnings when assessing coverage.

## How to read a document beyond the initial excerpts

Open the saved file library and choose **Browse indexed text**. Use **Next
sections** and **Previous sections** to page through indexed text. Topic search
is useful for finding a particular section; sequential browsing is useful for
checking the entire available index.

The selected/indexed count is a section count, not a percentage of unique
characters or proof the original document was fully extracted. Chunks overlap,
so adding their lengths would overcount source coverage. The preview is text,
not a faithful rendering of every chart, table, image or layout.

In Agent mode, document search/read tools can inspect further indexed sections.
Ask the agent to cite locations and explicitly identify unread or missing
material. Tool availability alone does not establish complete review.

For explicit saved coverage, use **Indexed document review** in the preview.
Enter a bounded goal and create a review: this step calls no model. Each
**Review next batch (uses model credits)** click assesses up to three sections.
Each assessment stores its source index/location/hash, model summary, a quote
checked literally against that source, and reported usage. The workflow resumes
at the next unassessed index rather than repeating completed calls.

The review is read-only and separate from recursive critique. Its default 64,000
reported-token ceiling spans all batches; each batch is limited to 180 seconds.
Reopening/reloading only reads saved progress. Network/proxy timeout does not
establish that a call failed: reload saved state before doing more work.
Unknown provider outcomes remain blocked rather than being replayed. A process
restart with active work likewise cannot authorize automatic replay.

The preview and both workspace SDKs validate the nested saved-review record
before using it: identity and source references, coverage, reported usage,
budget history and synthesis traversal/citation lineage. An invalid response
is an explicit error, not empty progress or permission to retry a paid call.
The last valid record stays visible; reload saved state without a model call
before making another decision. If the initial saved list cannot be trusted,
**Reload saved reviews (no model call)** retries only that read. A timeout does
not prove the original provider call stopped. An active/unknown checkpoint may
remain blocked after reload, which protects against duplicate paid work.
These structural checks do not establish factual truth or current source
freshness; source and access checks remain backend responsibilities.

All indexed sections assessed means exactly that, not recovered OCR, verified
facts, a combined cross-section argument or a guarantee of correct interpretation.
Warnings remain visible even at full indexed coverage. Source changes invalidate
continuation; deleting the source deletes its reviews. Saved reviews can also be
deleted explicitly. The private library retains up to 20 reviews. Budget
extension and cross-section synthesis are not automatic.

### Combining sections and deliberately permitting more usage

After all indexed sections have assessments, **Synthesize next batch (uses model
credits)** combines saved assessments into a cross-section result. It processes
groups of at most eight inputs, with at most three synthesis units per confirmed
batch. Larger reviews have intermediate summary levels. Every completed unit is
checkpointed and never resubmitted on resume; a final result requires traversal
of all indexed assessments, including the final section. There is no hidden
whole-document truncation or automatic paid loop.
Provider fallback can make multiple attempts within a unit; failed-attempt
charges may be unknown, so a unit count is not an invoice count.

Use synthesis for themes, conflicts, conclusions and limitations across assessed
sections. Do not treat it as a new full-source read or use it alone to resolve
a crucial detail: summaries are lossy, and a section being traversed does not
prove every claim survives. Citations retain source-index lineage through the
summary levels and open literal quotes from saved assessments. This validates
the link, not entailment or truth. Source warnings still apply.

Synthesis shares the saved review's reported-token usage and 180-second batch
limit. Opening it or reloading it never runs models. Unknown provider outcomes,
invalid responses, source changes and deletion block safe continuation.

When a known budget stop is the actual blocker, **Confirm larger total ceiling
(no model call)** can deliberately permit more future review usage, up to 128,000
reported tokens total. The default stays 64,000. Enter a total, not an increment.
The operation preserves usage, records an audit event/history, and compares the
expected current ceiling so stale/double confirmations fail. It does not run a
model or automatically start the next batch; each paid batch remains a separate
choice. It cannot unlock uncertain or invalid calls or raise ordinary recursive
run limits. A checkpointed over-ceiling unit is retained, not replayed.

Avoid raising a ceiling just because a result is partial. Read the actual stop
reason and coverage first. Extension is neither an invoice guarantee nor a
replacement for tenant spend controls; charges for failed/interrupted provider
attempts can remain unknown.

Legacy uploads with only preview text cannot recover their missing original
content through paging; re-uploading may be needed. No amount of recursive
critique can assess a diagram that was never extracted.

## Repository context and privacy

No repository selected means **no repository context**. Select a repository you
connected when you want source-aware help. A repository name in a prompt is not
authorization to access its files.

The platform repository is owner/admin-only, not a customer default. Customers
work with repositories connected to their own account, identified by source ID
or slug rather than backend filesystem paths. Connected public repositories are
supported; do not assume private-repository support merely because a provider
token exists elsewhere.

Repository observations describe the saved inspected revision. They are not an
automatic sync or proof that a later working tree is unchanged. Check readiness
and base revision again when preparing a different change.

## Proposals, validation and application are separate

A model's patch in a message is not a recorded proposal. A proposal is not a
successful build. A successful build is not proof of correct behavior. A recorded
local branch/commit is not a push, merge or deployment.

Connected user-repository changes remain proposal-only; MammothOS never pushes
them for you. The separately gated owner execution pilot can validate a frozen
candidate and, after its separate approval, create a local branch/commit. Review
its diff, selected repository, base revision, validation profile and receipts.

Validation profiles must actually support the selected project. A MammothOS UI
profile does not automatically validate another Next.js or Vite application.
If baseline validation fails before the change runs, fix the environment or use
a reviewed compatible validator. Do not switch to the platform repository to
make another project's check appear green.

### What container evidence actually establishes

Image/tool availability is not isolation acceptance. Operators have a separate,
strict runtime-acceptance command and manual workflow that run bundled trusted
Python fixtures through the real owner executor. A successful receipt observes
the test process's non-root identity, capabilities/seccomp/no-new-privileges,
read-only mounts, bounded writable storage, resource controls and loopback-only
network interfaces. It also checks that a failing test is rejected, a started
sleeping test times out, and specifically named containers are removed.

`verified` applies only to the recorded host, image digest, profile, timestamp
and tested conditions. It is not a certificate for hostile code, all repository
dependencies, frontend browser behavior or the deployed server. No user/tenant
receives new execution access, and no operator approval is bypassed.

The operator command never pulls images or falls back to host execution.
The manual workflow can explicitly pull an operator-reviewed digest; otherwise
the image must already be local. Unavailable/incomplete evidence is
`not_verified`, not a pass. Observed checks or cleanup failures are `failed`.
Both stop strict acceptance. The legacy hosted smoke remains a separate receipt:
its namespace/mount startup failure occurs before a test process is observed,
so it cannot justify relaxing seccomp. Missing runtime or unnamed permission
errors now produce no speculative syscall suggestions.

## Tools, MCP and approvals

Tools are the runtime's permitted actions. MCP connects compatible external tool
servers; adding a server does not make its output trustworthy or grant blanket
access. Availability depends on server configuration, account permissions and
repository scope.

Read tools can run within their authorized scope. Network tools access external
services. Write tools are proposal-only. Execution tools require approval; some
tools are also owner/admin-only or require a selected repository.

Treat tool results and uploaded instructions as source data, not authority to
change platform rules. Check the exact action and arguments before approving.
Approving a critique, a validation job and a local application are different
decisions. A model's "I did it" is not a substitute for the recorded receipt.

## Reading the timeline and Run Review

The timeline separates short reasoning summaries, tool calls, observations,
approvals, errors and outcomes. These summaries explain the work; they are not
private internal chain-of-thought or a correctness certificate.

Model diagnostics can identify provider/model, completion reason and reported
usage. A fallback provider may keep a task available, but does not prove equal
quality. Missing usage is unavailable, not zero. Unknown charges from interrupted
requests cannot be inferred from a clean-looking UI.

Run Review lets you inspect saved evidence without executing the task again.
Recovering or exporting a run does not approve it, continue it or repeat model
calls. A disconnected stream may need explicit saved-state recovery; do not assume
every interrupted request can safely be replayed.

## Task Inbox, artifacts, notes and the daily build log

**Task Inbox** is the saved work list. Manual task cards track your organization;
manually marking one complete does not verify an agent's work. Run-backed cards
reflect saved runs and cannot be freely edited into a different execution result.

**Artifacts** are retained outputs with provenance when available: task/trace IDs,
repository revision and checks. Ready labels and syntax checks are not acceptance
tests. Use the recorded run to inspect evidence behind a result. An unavailable
run must not be interpreted as a successful one.

**Notes** are personal workspace records; the **daily build log** records progress
and decisions. Use them for context, not as authoritative usage or deployment
receipts. Account and subscription checks still apply; they are not public
cross-user knowledge stores.

## Terminal and owner controls

The workspace Terminal is owner-only. Customer repository access does not imply
access to the backend host. A terminal-like answer or suggested command is not
evidence the command ran.

Do not equate a green sandbox diagnostic job with verified isolation. Current
Docker-only smoke evidence remains **not_verified** after runtime namespace/mount
startup failures. The diagnostic reports that boundary rather than silently
running on the host. Production hostile-code isolation needs separate operational
evidence; no automatic policy weakening is an acceptable substitute.

## ATLAS and the Mammoth Mind tutor SDK

ATLAS is for structured learning: lessons, exercises, hints, progress and
comprehension checks. Use it when the aim is learning a skill, rather than
producing a repository patch as quickly as possible.

Lesson cards use real lesson data for prerequisites, examples and completion
signals; absent data should stay absent rather than become filler. Stuck-step
signals suggest a next move, not a diagnosis of the learner.

The comprehension gate supports an explicit **Continue anyway** override. An
override is a learner choice, not a passed exercise or a learning-outcome claim.
The tutor SDK's `next_lesson()` stays ungated unless `require_mastery=True`.

The product name is **Mammoth Mind tutor SDK**. Older **ATLAS FAB** names remain
compatible aliases. It embeds teaching sessions; it does not grant workspace,
terminal, tenant-administration or repository permissions.

## Mammoth Paths: the workspace SDK

Paths lets developers integrate workspace capabilities into other software:
agent runs and events, approvals, saved-run recovery, repository connections,
tasks, artifacts, notes, build logs and permitted terminal operations.

Python and JavaScript clients target the same backend contract. The backend
enforces user ownership, plan gates and tool permissions; an SDK option cannot
grant access. Each app must supply its own authentication lifecycle.

Private document paging is available through `read_document` / `readDocument`.
It reads indexed sections without invoking a model. Run recovery is also
read-only, not a hidden paid retry.

Usage hooks describe calls and transport outcomes for your integration. They
are not authoritative provider billing, factual validation or automatic spend
enforcement. Use the SDK guide for method names and wire details; use this
handbook to decide which capability fits the job.

## Getting useful results without needless AI spend

Start with normal chat or one focused Agent run. Use recursive review only when
its extra critique answers a concrete question. Batch tightly related work;
do not combine unrelated goals simply to make the prompt larger.

Specify acceptance checks early. Reuse inspected evidence and deterministic test
results instead of asking multiple models to restate them. Keep source excerpts,
not an ever-growing repeated conversation, in a bounded task.

When blocked, inspect the actual receipt before retrying. Narrow a scope that
cannot fit rather than automatically raising caps. Read-only document browsing
and saved-run recovery do not require new model calls.

Neither smaller role allowances nor fewer calls prove a specific credit saving.
Copilot credits, Mammoth provider usage and provider invoices are different
accounting systems. Measure what is actually reported and label unknown values.

## What remains planned, not promised

Provider-aware local admission now distinguishes tokenizer text plus conservative
request-envelope allowances from byte fallback; exact server-side billing counts
remain provider-reported after the call. Explicit indexed review now checkpoints
bounded section assessments and resumes known completed work without replay.
Separate, explicitly confirmed batches can now synthesize saved assessments and
deliberately extend a saved review's total ceiling, with checkpoint and
unknown-outcome protections. This is not automatic recursive whole-file critique,
full-source rereading, or an extension of ordinary recursive-run budgets.

The two reported hosted token-cap failures have not been independently reproduced
from their original run receipts. Deterministic tests verify specific behaviors,
not those unseen production executions.

Docker startup/isolation evidence and compatible per-repository validation images
form a separate infrastructure gate. Documentation cannot satisfy it. Live
disconnect/restart behavior, broader nested SDK validation and authoritative
tenant spend controls also remain roadmap work.

## Further reading

- [Mammoth Mind quick user guide](./mammoth_mind_user_guide.md)
- [Mammoth Paths SDK guide](./mammoth_paths_sdk_guide.md)
- [Tutor SDK product guide](../atlas_fab_product_guide.md)
- [In-repository ATLAS manual](../../ATLAS_MANUAL.md)

For a useful Guide question, try: "Explain recursive review costs and token-cap
stops, then help me decide whether my task needs it. Distinguish current behavior
from indexed-review coverage, saved synthesis and deliberate budget controls."
