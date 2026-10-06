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

## Dependencies and acceptance

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
