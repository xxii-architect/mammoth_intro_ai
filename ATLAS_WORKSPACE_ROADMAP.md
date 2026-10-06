# ATLAS learning workspace and lecture backlog

Keep the ATLAS name. Unify lessons, exercises, corrections, tutor conversation,
and education agents without requiring page changes. Preserve current gates,
source-aware research, document exports, and public SDK contracts.

## Delivery checklist

- [x] EDU-01: compose the existing Lessons renderer and ATLAS Tutor in one calm,
  responsive workspace. Keep the old `lessons` page key as a compatibility alias.
- [x] EDU-02: show a backend-curated education roster (Tutor, Curriculum,
  Research, Reflection, Coding, Browser), with lesson context and isolated
  conversations. Never expose host maintenance agents or operational metadata.
- [x] EDU-03: verify new lesson delivery, exercise submission/corrections,
  mastery gate and override, tutor consultation, research, exports, mobile
  navigation, account switching, and unavailable backend behavior.
- [ ] PLAN-01: fix irrelevant planning steps and structured-response failures.
  An education-design request must not produce community publishing or custodial
  restore actions. This remains separate from the workspace UI delivery.
- [ ] AUDIO-01: add versioned lesson sections/narration contract. Use durable
  section IDs and actual audio durations; never fabricate timestamps.
- [ ] AUDIO-02: choose a licensed TTS provider after operator review of quality,
  cost, retention, and usage rights. Implement one-lesson cached narration,
  playback, speed controls, seeking, and transcript fallback.
- [ ] AUDIO-03: add typed replay, contextual notes, and flashcard commands.
  Bind each command to the lesson revision, section, and playback position at
  invocation. Prevent duplicate saves on retries.
- [ ] AUDIO-04: add push-to-talk with explicit permission/microphone state.
  Always-listening interruption is an optional later feature, not a prerequisite.
- [ ] SDK-01: expose validated lecture/session APIs additively through the
  tutor SDK; retain AtlasFAB aliases and unchanged mastery defaults.

## Additional learning-workspace recommendations

### Current curriculum and adaptation delivery

- [x] COURSE-01: show readable module/lesson previews and explicit generation
  warnings; save private course snapshots and activate the exact reviewed course.
- [x] COURSE-02: reject whole-course ready claims when any lesson is invalid;
  stop substituting generic teaching text for failed model generation. Require
  substantive content, examples, distinct lessons, and unique lesson IDs.
- [x] PROFILE-01: visible, deferrable onboarding with beginner/intermediate/
  advanced/expert starting level, pacing, learning preference, goals, and focus.
  Preserve the existing learner model; separate pacing from evidence and show
  the reason for topic-specific difficulty recommendations.
- [x] ASSESS-01: lesson-grounded written-response rubric with explicit
  coverage-only fallback; unverified fallback feedback cannot increase mastery.
- [x] FLOW-01: use the current learner profile on new exercises, preserve saved
  teaching content, and prepare the next exercise before switching lessons.
  Add reviewed-course activation to the public tutor SDK without alias changes.

These improvements do not rewrite stored curriculum content on profile changes,
certify expertise, or guarantee factual correctness. Provider failures can still
prevent course authoring; the UI reports drafts rather than pretending success.
Durable exercise drafts, multi-course progress switching, and expert-reviewed
subject assessments remain separate follow-ups.

These recommendations are saved for review, not implemented or approved for
execution merely by appearing here. Prefer learning continuity and trustworthy
feedback over adding more agents or permanent panels.

- [ ] LEARN-01: durable "resume where I left off." Save the active lesson,
  exercise draft, tutor conversation, and selected view per learner. Recover
  after refresh or a dropped connection. Show Saved / Saving / Couldn't save
  explicitly. Current tab-switch draft preservation is not durable recovery.
- [ ] LEARN-02: contextual "Explain this" actions. Select lesson text, exercise
  instructions, or correction feedback and request a simpler explanation,
  worked example, or practice question. Send the exact selection and its lesson
  context to the tutor without introducing another permanent panel.
- [ ] LEARN-03: source-linked notes and flashcards. Extend the existing study
  tools rather than creating a second notes system. Link saved items to their
  lesson, section, and source; distinguish learner-written from AI-generated
  content. Let learners review generated cards before saving. Build this
  foundation independently of audio, then reuse it for lecture commands.
- [ ] LEARN-04: evidence-based remediation. Offer a smaller explanation or
  targeted exercise addressing the actual mistake instead of regenerating the
  whole lesson by default. Distinguish attempted, completed, and demonstrated
  understanding. Reading, listening, or liking an answer never implies mastery.
- [ ] LEARN-05: accessibility and focused reading. Add a distraction-reduced
  lesson view, adjustable text size, comfortable line spacing, keyboard
  navigation, and captions/transcripts when audio arrives. On mobile, prioritize
  the current task and collapse secondary tools.
- [ ] LEARN-06: cost and privacy controls. Show estimates before expensive
  research or narration only when they can be calculated reliably. Add per-user
  limits, cancellation, and clear retention/export/delete controls for learning
  history. Ratings inform reviewed evaluations, not silent lesson changes or
  training on private learner content.

Recommended sequence: LEARN-01 recovery, LEARN-02 contextual tutoring,
LEARN-03 connected study materials, LEARN-04 remediation, LEARN-05 accessibility,
then the lecture pilot. Apply LEARN-06 privacy and cost controls alongside every
new persistent or paid feature rather than postponing them until the end.

## Dependencies and acceptance

- [x] LIBRARY-01 (requested follow-up after the current learning-flow work):
  organize the artifact library by explicit artifact type. Candidate categories:
  curricula, lessons, research/reports, notes, flashcards, code/patch proposals,
  and plans. Inspect existing contracts before choosing final wire values.
  Add search and type/agent/date filters, clear draft/ready/failed states, and
  links back to the originating lesson or run. Preserve existing artifacts,
  downloads, ownership boundaries, and an explicit uncategorized legacy bucket;
  do not infer permission or teaching readiness from a category.

  Implemented: backend-owned type taxonomy and additive artifact metadata;
  search/category/agent/status/local-date filters, previews, text/JSON exports,
  authenticated DOCX downloads, private curriculum references, and confirmed
  server-first removals. Unknown legacy metadata remains explicitly unassessed.
  Notes and flashcards are categories for saved outputs, not an unpermissioned
  merge of their separately gated live stores. Origin navigation opens the
  workspace with recorded provenance visible; historical replay is not added.
  Browser-only legacy caches without a known owner are left untouched but never
  displayed or reassigned to whichever account happens to sign in.

EDU-03 verifies EDU-01/02 before release. AUDIO-01 follows stable lesson delivery;
AUDIO-02 requires provider selection and AUDIO-01. AUDIO-03 builds on AUDIO-02;
AUDIO-04 and SDK-01 follow validated AUDIO-03 behavior.

- One active lesson state feeds lesson, tutor, and agent context.
- Switching workspace views must not discard an exercise draft or in-flight
  research. New lessons reset old drafts and correction state.
- On portrait mobile only one main learning surface is visible. Controls do not
  cover the composer or create horizontal overflow.
- Agent catalog failure is explicit. Backend auth remains authoritative.
- Research does not replace lesson content or satisfy mastery.
- Audio listening never automatically implies comprehension.
- No repository context is granted by entering the education workspace.
- Lecture mode must not appear available until audio generation is implemented.

## Execution log

- 2026-10-05: backlog created; EDU-01/02 implementation started. Audio and plan
  routing remain pending; this file does not grant production or push access.
- EDU-01/02/03 completed: 67 backend contract/access/SDK/delivery tests and ten
  isolated browser scenarios passed; the production UI build passed. The browser
  scenarios cover drafts, new lessons, correction feedback, mastery override,
  exercise variants, scoped research and authenticated document downloads,
  desktop consultation, portrait mobile, account changes, catalog failure, and
  the general Agent workspace's team-run control.
- Validation used local auth/API fixtures, not live provider calls or a deployed
  sign-in test. The local fixture server is not a place to enter real credentials.
  Catalog health is registry-reported, not a provider availability probe.
- Curriculum/onboarding follow-up: 107 targeted backend/SDK/retrieval tests and
  15 browser scenarios passed. Coverage includes private exact-course activation,
  draft rejection, model-output hygiene, starting level and topic-specific
  adaptation, rubric assessment, next-lesson failure safety, onboarding, previews,
  save/start, exports, and portrait layout. Content quality still needs ongoing
  real-provider and subject-expert evaluation; automated fixtures cannot prove
  that every generated course teaches its subject correctly.
- LIBRARY-01 completed: 60 targeted backend/producer/tenant/SDK checks and all
  22 browser scenarios (15 ATLAS + 7 artifact-library) passed, with a production
  UI build. Automatic saves preserve full report text and distinct run IDs
  instead of truncating at 4,000 characters or overwriting same-title runs.
  The prior learning release's CI also exposed a route-helper placement error
  and an outdated curriculum payload expectation; both were corrected and the
  route-layout and registry-contract regressions passed.
- Curriculum failure follow-up: reproduced a 450-word / 20-minute lesson being
  rejected by the old character-based duration heuristic. Replaced it with a
  word-based reading floor while keeping depth/examples/all-lesson gates.
  Added safe failure categories and one bounded schema/teaching repair per
  lesson, without retrying provider exceptions. A real-provider nutrition course
  subsequently passed all nine lessons (411-542 teaching words each); two
  lessons required their permitted schema correction. This verifies authoring
  shape and readiness, not subject-expert factual review. Course/module time
  estimates now follow authored lesson estimates. Old drafts need regeneration.
- Lesson readability refinement: shared sanitized Markdown reader for active
  lessons, examples, and curriculum previews; standard plain-text teaching
  headings, section jumps, reading-width/spacing, and mobile-safe code/tables.
  Stored content, assessment gates, and exercise drafts are unchanged.
  Validation: 25 browser scenarios and the production build passed, including
  readable plain headings/lists/code, section focus, unsafe HTML/link stripping,
  no embedded-image fetches, shared previews, and portrait draft preservation.
- User-output review follow-ups (not fixed by the readability work): contextual
  research about nutrition retrieved Ofsted curriculum-inspection sources,
  despite source-grounded labels. Add an evaluation for resolving "this
  curriculum" to the active subject and reject unrelated evidence/claims.
  Coding returned `generate_code` with `target unknown` for a minimal Health
  Module edit; require a selected repository and an actual target/read/diff
  before presenting such output as an integrated patch. The pasted standalone
  prototype is not proof of file integration or validation.

## Agent quality upgrade delivery

- [x] RESEARCH-01: preserve structured context through API/registry; resolve
  active lesson/course references to the subject. Reject unrelated search
  sources and missing excerpts instead of filling gaps with fabricated evidence.
- [x] RESEARCH-02: require real labels and exact excerpt quotes for brief
  findings; exclude unsupported claims, derive summary/facts from checked links,
  and calculate actual link coverage. Display excerpts, safe links, and gaps.
  Remove source-count/temperature confidence and keyword-based contradiction claims.
- [x] CODING-01: existing-file requests under Write code require source too.
  Multiline prose is not source. Preserve patch task type, include original
  source in prompts, retain module interfaces, and emit applicable named diffs.
  Python AST checks are explicit; generated tests remain unexecuted. No host
  permissions, repository access, automatic application, or pushes were added.
- [x] CURRICULUM-01: one bounded outline call assigns distinct subtopics and
  objectives while validating exact IDs/order and earlier-only prerequisites.
  Pass the real sequence to authors and derive next-lesson navigation from it.
  Reject unlabeled fictional numerical studies; preserve bounded repairs and
  all shared readiness/mastery/SDK contracts.
- [ ] EVIDENCE-REVIEW-01: independently evaluate claim entailment, factual
  accuracy, source trust/date, and contradiction reasoning against reviewed
  domain benchmarks. Exact quotes and lexical relevance are not this review.
  Long-form prose is explicitly a draft, not claim-verified research.
- [ ] CODE-EXEC-01: isolated tenant-scoped behavioral validation with explicit
  dependencies, approvals, resource limits, and verification receipts. Generated
  tests and AST parsing do not establish correctness.
- [ ] COURSE-REVIEW-01: expert-reviewed domain coverage and teaching evaluation
  for beginner through expert study. Structural readiness is not pedagogy
  certification, medical advice, or proof that every requested subtopic is taught.

No numerical "9.9/10" quality guarantee is made. These changes improve observable
contracts and failure honesty; the remaining reviewed evaluations are separate
deliverables. Regenerate old drafts for content improvements; existing saved
artifacts do not receive rewritten model output.

Validation includes the full Python regression suite with paid model calls
disabled, a final 148-test agent/SDK regression run, 27 browser scenarios,
production UI build, and lint on new helpers.
Bounded live-provider checks returned two excerpt-linked research findings and
a Python patch preserving the existing function name, with passing AST checks.
Live curriculum authoring produced a 462-word introductory lesson and
manifest-derived navigation. The live test exposed forward promises despite
prompt constraints; these are now removed into separate sequence diagnostics,
teaching readiness is rechecked, and the actual next lesson is appended. This
tests output contracts, not a full expert-reviewed nine-lesson nutrition course.
The revised live outline also passed structure checks with distinct nutrition
topics spanning macronutrients, micronutrients, balanced meals, assessment, and
practical dietary changes. Exported long-form documents retain the draft warning
and omit model reasoning; traces remain separate from document content.

## Repeating the workspace checks

Run from the repository root with the project Python dependencies available:

```powershell
$env:PYTHONPATH="$PWD\src;$PWD"
python -m pytest tests\test_atlas_learning_workspace.py tests\test_agent_sandbox.py tests\test_atlas_fab_sdk.py tests\test_tutor_delivery.py -q -p no:warnings
```

For browser checks, the dedicated Playwright configuration starts and stops its
own Vite server on port 5194 with test-only settings. The browser harness supplies
its own authentication and API responses, and generated results go to a unique
temporary directory rather than tracked `test-results` files. Set `ATLAS_UI_URL`
only to reuse an already running local test server:

```powershell
npx playwright test --config=tests\atlas-workspace.playwright.config.js
```

Run `npm run build` from `ui\mad-architecht-command-center` for the production
bundle. Lecture/provider and plan-routing tasks above remain unimplemented.
