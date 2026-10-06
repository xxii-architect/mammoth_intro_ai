import {
  AlertTriangle,
  BookOpen,
  Bot,
  CheckCircle2,
  ClipboardList,
  Compass,
  FolderOpen,
  Globe,
  GraduationCap,
  MessageSquare,
  ShieldCheck,
  Terminal,
} from 'lucide-react'
import OnboardingGuide from '../components/OnboardingGuide'

const sectionStyle = {
  padding: 18,
  marginBottom: 16,
  borderRadius: 14,
}

const liveNow = [
  'Mammoth Mind supports multi-thread chat, file attachments, and repo-aware /guide flows.',
  'ATLAS Tutor now has clear Assistant / Tutor / Build lanes, Monaco lesson editing, and expandable guide cards.',
  'Learning materials can be uploaded into the ATLAS library for lesson-side context and reuse.',
  'Mammoth Mind Agent mode streams a run timeline: plan, short reasoning summaries, tool calls, proposed diffs, and inline Approve / Reject cards. Stop cancels a run at any time.',
  'The Mammoth Mind pill is in the top-right header, next to notifications. It opens a quick panel with a link to the full Mammoth Mind page.',
  'Mammoth Mind adapts response depth: short and natural for simple asks, structured and thorough when the work calls for it. Runtime health is a color-coded, expandable header pill, and the chat composer has no divider above it.',
  'Rate any Mammoth Mind reply with thumbs up or down (click again to clear). A thumbs-down can add a reason and a note. Owners see totals and the thumbs-down regression cases on Beta Feedback. Ratings are signal only and never retrain the model.',
  'Research output is cleaner. Model reasoning is moved into a separate trace, off-topic and disambiguation sources are filtered out, repeated paragraphs are removed, and cut-off sections are trimmed or retried. Long-form reports include a quality summary.',
  'Lessons now show a manifest (what to know first, sample input, expected output, done-when). Stuck detection suggests one concrete next move. Next checks that the exercise passed, and you can always choose Continue anyway.',
  'Mammoth Paths is the new workspace SDK (Python `MammothPaths`, JS `@mammothos/paths`) for embedding agent runs, your repos, notes, and the build log in other software. The tutor SDK is now called Mammoth Mind (formerly ATLAS FAB).',
  'Notes and the build log are now private to each account and enforced on the server for Pro tier and above.',
  'Release readiness now includes fail-closed health and eval gates, so weak runtime or missing eval data blocks green status.',
  'Usage warnings are now surfaced through the billing usage endpoint when tenants approach limits.',
]

const surfaceMap = [
  {
    page: 'chat',
    label: 'Mammoth Mind',
    icon: MessageSquare,
    accent: 'var(--photon)',
    purpose: 'Agent-mode runs with visible tool traces and approvals, plus repo-aware chat, /guide walkthroughs, threads, and attachments. Toggle Agent / Classic in the chat header.',
    useWhen: 'You want code-grounded explanations, planning help, or workflow support across the product.',
    avoid: 'Using vague messages with no target file, goal, or repo context.',
  },
  {
    page: 'atlas',
    label: 'ATLAS Tutor',
    icon: GraduationCap,
    accent: 'var(--violet)',
    purpose: 'Adaptive tutoring, practice loops, learner memory, and exercise feedback.',
    useWhen: 'You need lesson flow, coaching, recap/quiz/review, or guided coding practice.',
    avoid: 'Expecting Tutor mode to dump direct answers for active exercises.',
  },
  {
    page: 'agent',
    label: 'Agent',
    icon: Bot,
    accent: 'var(--violet)',
    purpose: 'Chat with a specific agent, hand off with @agent, or run a Team run: preview the plan, pick steps, and get one synthesized answer. Pick a repository in the Coding agent header and it reads your real files and proposes diffs (nothing is applied or pushed). On a phone, swipe the agent chips at the top to switch agents.',
    useWhen: 'You want a specialist (research, coding, reflection, audit) to keep context across turns, or several agents to build on each other.',
    avoid: 'Running broad mutation-heavy prompts without scope, constraints, or verification criteria. The classic console is still under Advanced.',
  },
  {
    page: 'terminal',
    label: 'Terminal',
    icon: Terminal,
    accent: 'var(--cyan)',
    purpose: 'Direct command execution for deterministic inspection and validation.',
    useWhen: 'You already know the exact command you need to run and want raw output.',
    avoid: 'Treating Terminal like a brainstorming surface instead of an execution surface.',
  },
]

const laneGuide = [
  {
    title: 'ATLAS Assistant',
    detail: 'Use for /guide, architecture help, repo-aware walkthroughs, and broader thinking. This is the least restrictive chat lane.',
  },
  {
    title: 'ATLAS Tutor',
    detail: 'Use for explanations, hints, recap, reflection, and anti-cheat-safe coaching during an active lesson.',
  },
  {
    title: 'ATLAS Build',
    detail: 'Use for worked examples, implementation thinking, and lesson-adjacent building help while staying learning-aware.',
  },
]

const promptPatterns = [
  {
    title: 'Code-grounded walkthrough',
    surface: 'Mammoth Mind Assistant',
    prompt: '/guide walk me through how atlas_chat handles assistant, tutor, and build modes',
  },
  {
    title: 'Repo-aware debugging',
    surface: 'Mammoth Mind Assistant',
    prompt: 'Look at api_server.py and explain why this route is returning a 422.',
  },
  {
    title: 'Lesson coaching',
    surface: 'ATLAS Tutor',
    prompt: 'I am stuck on this exercise. Tell me the likely misunderstanding, then give me the smallest next step.',
  },
  {
    title: 'Build-oriented practice',
    surface: 'ATLAS Build',
    prompt: 'Show me how to structure this solution, but stop short of giving me the full final answer.',
  },
  {
    title: 'Safe execution request',
    surface: 'Agent',
    prompt: 'Plan and execute a fix for the chat sidebar bug. Keep changes minimal, preserve behavior, and verify with the smallest relevant build/test.',
  },
]

const repoContextRules = [
  {
    title: 'Set your learning profile, then review and start a course',
    body: 'ATLAS onboarding lets you choose beginner through expert study, pacing, learning preference, goals, and focus areas; you can defer or edit it. Pacing is not mastery. The Curriculum learning agent shows modules and lesson content: review, Save to my curricula, then Start this curriculum. My curricula stores your private snapshots. Starting begins at lesson one and replaces the active course; continue the current course through Lesson & practice. Draft courses can be saved or exported but cannot start until authored content passes the shared checks. These checks do not verify factual accuracy or confer certification. Written practice uses lesson-grounded rubric feedback when available; coverage-only fallback feedback does not increase mastery. Profile changes apply to new teaching/exercises, not silent rewrites of existing content.',
  },
  {
    title: 'ATLAS is one learning workspace',
    body: 'Lesson & practice brings lesson content, exercises, and corrections into the main field. Consult ATLAS Tutor beside the lesson on desktop, or switch views on mobile. Learning agents includes Tutor, Curriculum, Research, Reflection, Coding, and Browser when registered, using your active lesson as context. Advanced tutor tools remain available. Lecture audio is planned, not enabled yet.',
  },
  {
    title: 'Review reply ratings by agent and date',
    body: 'Owners/admins can filter Beta Feedback reply ratings by agent and an inclusive UTC date range. Dates refer to the latest rating update. The summary and Cases JSON use the same filters; ratings remain review signals, not automatic model training.',
  },
  {
    title: 'No repository selected means no repo context',
    body: 'Mammoth Mind never falls back to a default repository. Pick a repo in the Repo Context panel or the agents answer without code context.',
  },
  {
    title: 'Connect your own repositories',
    body: 'Enter a public GitHub repo as owner/repo. MammothOS clones it into your private sandbox; other users can never see it. Use the sync button to refresh it.',
  },
  {
    title: 'Edits are proposals, never pushes',
    body: 'Write requests on a connected repo produce a local branch plus a git patch you can apply with `git am` or turn into a pull request. MammothOS never pushes to your repository.',
  },
  {
    title: 'The MammothOS platform repo is owner-only',
    body: 'Only the owner/admin sees the locked "MammothOS platform" option. The server enforces this; filesystem paths and forks of the platform repo are rejected for everyone else.',
  },
  {
    title: 'Your runs, tasks, and artifacts are private',
    body: 'The Agent Workbench (Pro), Task Inbox, and Artifacts only show items you created. Shared agents run sandboxed for your account: they cannot read the host machine, run host tests, or fetch private-network addresses. The Terminal stays owner-only.',
  },
  {
    title: 'Find and review saved artifacts',
    body: 'Artifacts groups saved outputs into Curricula, Lessons, Research & reports, Notes, Flashcards, Code & patch proposals, Plans, and Uncategorized. Combine search, agent, status, and local-date filters; expand a preview or download text/JSON and available authenticated DOCX files. Ready means declared output readiness, not factual verification, mastery, or safe-to-apply code. Old outputs without metadata remain Uncategorized / Not assessed. Saved ATLAS curricula are linked from their own library; clearing saved outputs never deletes those courses or the live Notes and Flashcards libraries. Origin buttons open the workspace and show recorded run/lesson IDs, not an automatic replay. Backend failures stay visible; unscoped browser caches are not shown.',
  },
  {
    title: 'When curriculum authoring fails',
    body: 'Generation warnings distinguish invalid lesson JSON, missing or incorrectly typed fields, failed teaching checks, and provider/runtime failures. Authoring allows one correction attempt for lesson-output failures; provider exceptions use the runtime fallback chain instead. Corrections can add time and model usage. Lesson durations include practice and are checked against a word-based reading floor. Failed drafts stay blocked from starting and are never replaced with filler. Regenerate the curriculum after a fix; saved old drafts do not update automatically.',
  },
  {
    title: 'Read lessons without the wall of text',
    body: 'The lesson pane and curriculum previews format headings, paragraphs, emphasis, lists, code, and tables. Standard plain-text teaching headings are recognized too. Use In this lesson to jump to a section without leaving the lesson or losing your exercise draft. Examples keep their formatting, and stored content is not rewritten. Embedded images and active HTML are not loaded. Readability does not imply factual verification or mastery.',
  },
  {
    title: 'Dark mode while the platform is polished',
    body: 'Dark is currently the only supported appearance. The sidebar and Settings no longer offer theme toggles. Saved Aurora and older theme preferences migrate to Dark automatically, and leftover inline colors are cleared to keep text readable. Settings shows the active appearance.',
  },
  {
    title: 'Recover an interrupted page',
    body: 'Startup, sign-in checks, and page-render failures show a reload or retry control instead of a blank view. Sign-in checks time out after 15 seconds without treating the error as a signed-out session. Saved backend work is retained; unsent browser-only text may be lost when reloading. Older hashed frontend assets are retained during deployment so existing tabs can still open their pages.',
  },
  {
    title: 'Learning resources are not operational plans',
    body: 'Lesson Notes rebuilds lesson-matched notes, excluding unrelated recent notes and operational plan JSON. Other saved notes and run artifacts remain in their own libraries. Flashcards use saved question-and-answer pairs for your active lesson, or recall cards drawn from its actual teaching content and public exercise examples. Objectives are not answers. An empty deck means there is no answered content yet; it never silently displays demo cards. Use Refresh deck or Refresh lesson notes to load newly saved content.',
  },
  {
    title: 'Read Modules status literally',
    body: 'The owner/admin Modules view refreshes backend snapshots every 30 seconds and reports fetch failures. Catalog-only agents are unknown; discovered source files and integrated helpers are not claimed running or healthy. An MCP launcher being present means configured, not a verified connection. Connected means a live initialized MCP client in the current context. Needs context requires an authorized repository selection; needs setup requires backend configuration. Merely viewing Modules does not launch MCP servers. Platform repository and approval restrictions are unchanged.',
  },
  {
    title: 'Upload and inspect learning documents',
    body: 'Chat and ATLAS use the same backend file policy: by default 50 MiB per file, 500 MiB combined raw-file storage, and 200 files per user. PDFs, DOCX, slides (PPTX), spreadsheets (XLSX), HTML, text/Markdown, CSV and supported code formats have real text readers. Transfer progress and processing are separate; extraction can be partial. Use Preview in My Learning Materials or chat’s Manage saved files to search a topic or page/slide number and inspect the extracted sections. Delete stored files to reclaim quota; removing an attachment alone does not delete them. Chat uses four attachments per request; ATLAS uses six. Retrieval searches the whole bounded extraction, not just its opening preview, but lexical matches are not factual verification. Scans need OCR, which is not enabled; embedded images and media are not transcribed. Re-upload old legacy-preview files for whole-document indexing. Cancellation may finish server-side if processing already started; use Refresh library before retrying. Delete failures retain the record rather than pretending success.',
  },
  {
    title: 'Research evidence is visible, not assumed',
    body: 'Research resolves “this lesson/course” from the active subject. With no subject it asks for context. Irrelevant search hits and missing excerpts cannot become evidence. Brief findings carry source IDs and exact matching excerpt quotes; invented quotes and unknown citations are excluded and available separately for review. Source-linked does not mean fact-verified. Evidence gaps stay explicit, contradictions are not automatically inferred, and long-form documents remain drafts requiring claim review. Supplied sources and no-web settings are honored for both brief and long-form research.',
  },
  {
    title: 'Coding produces proposals, not invented integrations',
    body: 'For existing-file changes, select your connected repository and a target, or paste the complete original in a code fence. Write code cannot bypass this requirement; multiline instructions are not source. The agent includes the original source and returns a reviewable diff, preserving existing interfaces. Python syntax checks do not execute code. Generated tests remain not run and integration not verified until real validation is performed; generating tests or docs does not confer confidence. Nothing here grants access to the platform repository or pushes to your repository.',
  },
  {
    title: 'Curricula follow their actual course sequence',
    body: 'New template courses first plan distinct subtopics, objectives, and earlier-only prerequisites in one outline call. If the outline fails validation, the course remains a draft without authoring every lesson. Each lesson author receives the actual sequence and the application adds the real next lesson. Invented numerical studies must be labeled hypothetical rather than presented as research. Authoring retains one bounded correction attempt. These structural checks are not independent factual review, and existing saved courses are not silently rewritten.',
  },
  {
    title: 'Queries determine what code gets surfaced',
    body: 'Generic chat like “do you see the code?” may return empty snippets. Ask for a file, symbol, route, or behavior you want inspected.',
  },
]

const agentRunRules = [
  {
    title: 'Agent mode shows its work',
    body: 'Each run shows a collapsible “Worked · N tool calls” timeline: the plan, one-line reasoning summaries, what was read or searched, and any proposed diff. Reasoning lines are short summaries written by the model, not hidden chain-of-thought.',
  },
  {
    title: 'Risky tools stop and ask',
    body: 'Write tools only produce proposals. Execution tools, and MCP tools that would change something, pause the run on an approval card. Approve to continue or Reject to let Mammoth Mind work around it.',
  },
  {
    title: 'Stop is always available',
    body: 'While a run is active the Send button becomes Stop. Cancelled runs keep the steps already completed.',
  },
  {
    title: 'Classic mode is still there',
    body: 'Slash commands (/guide, /research, /web, /plan) and messages with attachments use the classic chat path automatically. Switch to Classic in the header to use it for everything.',
  },
  {
    title: 'Live web search',
    body: 'When the server has a Brave or Tavily key, Agent mode gets a web_search tool, and Research and Search use the same provider before falling back to the free scrapers. Without a key, results say so plainly. Nothing is faked.',
  },
  {
    title: 'Live weather',
    body: 'Name a place ("near Stanley, Idaho") and Field Ops adds a live Open-Meteo forecast. Weather hazards raise the risk level and appear in the safety notes. Agent mode also has a weather_forecast tool.',
  },
]

const safetyRules = [
  'Use preview or approval-first flows for mutations whenever the surface supports them.',
  'Treat generated content as assistive output until it is validated against the repo, runtime, or course material.',
  'Use /research or /web for current-source lookups instead of expecting stale model memory to behave like a browser.',
  'Keep repo, learner, and operator context scoped correctly so one session does not pretend to represent another.',
]

const qaChecklist = [
  'Open Landing, Manual, and Command Library first to confirm product positioning and surface naming are current.',
  'Run one Mammoth Mind /guide request and verify expandable guide steps appear.',
  'Run one Mammoth Mind Agent-mode question and confirm the run timeline shows tool calls and a real final answer; press Stop on a second run to confirm cancellation.',
  'Run one ATLAS lesson loop: lesson start -> exercise -> submit -> adaptive feedback -> recap or quiz.',
  'Check /api/health and confirm health_gate is present and passed before release actions.',
  'Check /api/release-readiness and confirm release_gate and eval_gate are both passed.',
  'Upload one chat attachment or ATLAS material and confirm it appears in the right library.',
  'Capture final artifacts or tasks in Artifacts / Task Inbox so test sessions stay replayable.',
]

export default function ManualPage({ setPage }) {
  return (
    <div className="page-enter page-shell" style={{ maxWidth: 1180 }}>
      <h1 style={{ fontSize: '1.15rem', fontWeight: 700, marginBottom: 18, display: 'flex', alignItems: 'center', gap: 8 }}>
        <BookOpen size={20} color="var(--cyan)" /> MammothOS Manual
      </h1>

      <OnboardingGuide variant="banner" currentPage="manual" setPage={setPage} />

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '3px solid var(--cyan)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <Compass size={16} color="var(--photon)" />
          <strong>What this page is for</strong>
        </div>
        <div style={{ color: 'var(--txt-sec)', lineHeight: 1.7, fontSize: '0.9rem', marginBottom: 14 }}>
          This manual is the clean operating map for MammothOS right now: what is live, which surface to use, how repo context behaves,
          and how to test the platform without getting lost in old prototype-era noise.
        </div>
        <div className="manual-grid-wide" style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))' }}>
          {liveNow.map((item) => (
            <div key={item} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12, background: 'rgba(255,255,255,0.02)', color: 'var(--txt-sec)', fontSize: '0.8rem', lineHeight: 1.55, display: 'flex', gap: 8 }}>
              <span style={{ color: 'var(--cyan)' }}>✓</span>
              <span>{item}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '3px solid var(--violet)' }}>
        <h2 style={{ fontSize: '0.96rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <CheckCircle2 size={16} color="var(--violet)" /> Choose the right surface
        </h2>
        <div className="manual-grid-wide" style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          {surfaceMap.map((item) => {
            const Icon = item.icon
            return (
              <div key={item.page} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Icon size={16} color={item.accent} />
                  <div style={{ fontSize: '0.84rem', color: 'var(--txt-pri)', fontWeight: 700 }}>{item.label}</div>
                </div>
                <div style={{ color: 'var(--txt-sec)', fontSize: '0.77rem', lineHeight: 1.55 }}><strong>Purpose:</strong> {item.purpose}</div>
                <div style={{ color: 'var(--txt-sec)', fontSize: '0.77rem', lineHeight: 1.55 }}><strong>Use when:</strong> {item.useWhen}</div>
                <div style={{ color: '#fca5a5', fontSize: '0.77rem', lineHeight: 1.55 }}><strong>Avoid:</strong> {item.avoid}</div>
                <button
                  onClick={() => setPage(item.page)}
                  style={{ marginTop: 'auto', padding: '9px 12px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)', fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer' }}
                >
                  Open {item.label}
                </button>
              </div>
            )
          })}
        </div>
      </div>

      <div className="manual-grid-mid" style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <GraduationCap size={16} color="var(--violet)" /> ATLAS lane guide
          </h2>
          <div style={{ display: 'grid', gap: 10 }}>
            {laneGuide.map((item) => (
              <div key={item.title} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', fontWeight: 700, marginBottom: 6 }}>{item.title}</div>
                <div style={{ fontSize: '0.77rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>{item.detail}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <FolderOpen size={16} color="var(--photon)" /> Repo context rules
          </h2>
          <div style={{ display: 'grid', gap: 10 }}>
            {repoContextRules.map((item) => (
              <div key={item.title} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
                <div style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', fontWeight: 700, marginBottom: 6 }}>{item.title}</div>
                <div style={{ fontSize: '0.77rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>{item.body}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '3px solid var(--photon)' }}>
        <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Bot size={16} color="var(--photon)" /> Mammoth Mind agent runs
        </h2>
        <div className="manual-grid-wide" style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          {agentRunRules.map((item) => (
            <div key={item.title} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', fontWeight: 700, marginBottom: 6 }}>{item.title}</div>
              <div style={{ fontSize: '0.77rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>{item.body}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '3px solid var(--cyan)' }}>
        <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <MessageSquare size={16} color="var(--cyan)" /> Prompt patterns that actually work
        </h2>
        <div className="manual-grid-wide" style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
          {promptPatterns.map((item) => (
            <div key={item.title} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12 }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', fontWeight: 700, marginBottom: 4 }}>{item.title}</div>
              <div style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>{item.surface}</div>
              <div style={{ color: 'var(--photon)', fontSize: '0.77rem', lineHeight: 1.6 }}>{item.prompt}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="manual-grid-mid" style={{ display: 'grid', gap: 16, gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShieldCheck size={16} color="var(--violet)" /> Safety and trust defaults
          </h2>
          <div style={{ display: 'grid', gap: 10 }}>
            {safetyRules.map((item) => (
              <div key={item} style={{ border: '1px solid var(--border)', borderRadius: 12, padding: 12, color: 'var(--txt-sec)', fontSize: '0.78rem', lineHeight: 1.6, display: 'flex', gap: 8 }}>
                <span style={{ color: 'var(--violet)' }}>•</span>
                <span>{item}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <ClipboardList size={16} color="var(--photon)" /> Clean validation loop
          </h2>
          <ol style={{ margin: 0, paddingLeft: 20, color: 'var(--txt-sec)', fontSize: '0.79rem', lineHeight: 1.85 }}>
            {qaChecklist.map((item) => (
              <li key={item} style={{ marginBottom: 6 }}>{item}</li>
            ))}
          </ol>
        </div>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '3px solid var(--amber)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <Globe size={16} color="var(--cyan)" />
          <strong>Fast memory hook</strong>
        </div>
        <div style={{ color: 'var(--txt-sec)', lineHeight: 1.7, fontSize: '0.86rem', marginBottom: 10 }}>
          If you need current information, use <span style={{ color: 'var(--photon)', fontFamily: 'JetBrains Mono, monospace' }}>/research</span> or <span style={{ color: 'var(--photon)', fontFamily: 'JetBrains Mono, monospace' }}>/web</span>.
          If you need code truth, target a file, route, or symbol. If you need learner-safe help, stay in Tutor mode.
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button onClick={() => setPage('commandlib')} style={{ padding: '10px 14px', borderRadius: 10, border: 'none', background: 'linear-gradient(90deg, var(--photon), var(--cyan))', color: '#050608', fontWeight: 800, cursor: 'pointer', fontSize: '0.8rem' }}>
            Open Command Library
          </button>
          <button onClick={() => setPage('landing')} style={{ padding: '10px 14px', borderRadius: 10, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)', fontWeight: 700, cursor: 'pointer', fontSize: '0.8rem' }}>
            Open Landing Page
          </button>
        </div>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '3px solid var(--cyan)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <AlertTriangle size={16} color="var(--cyan)" />
          <strong>Keep this page honest</strong>
        </div>
        <div style={{ color: 'var(--txt-sec)', lineHeight: 1.7, fontSize: '0.86rem' }}>
          Update this manual whenever surface names, repo-context behavior, lesson flows, guardrails, or visible capabilities change.
          The manual should reflect the product as it exists now, not the prototype it used to be.
        </div>
      </div>
    </div>
  )
}
