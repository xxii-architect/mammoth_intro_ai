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
  'The FAB can now be hidden and restored without losing its context or history.',
  'Release readiness now includes fail-closed health and eval gates, so weak runtime or missing eval data blocks green status.',
  'Usage warnings are now surfaced through the billing usage endpoint when tenants approach limits.',
]

const surfaceMap = [
  {
    page: 'chat',
    label: 'Mammoth Mind',
    icon: MessageSquare,
    accent: 'var(--photon)',
    purpose: 'Repo-aware general chat, /guide walkthroughs, threads, and attachments.',
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
    purpose: 'Structured plan/execute workflows with visible runs and approval-safe edits.',
    useWhen: 'You want multi-step implementation, audits, or system tasks with traceability.',
    avoid: 'Running broad mutation-heavy prompts without scope, constraints, or verification criteria.',
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
    title: 'Use the path of the machine running the backend',
    body: 'If the app is using your live server, the repo path should be the server path. If the app is hitting your local backend, the repo path should be the local Windows path.',
  },
  {
    title: 'Save both local and live presets',
    body: 'A good pair is C:\\Users\\runni\\mammoth_intro_ai.worktrees\\agents-mammothos-atlas-agent-system for local work and /opt/mammothos/mammoth_intro_ai for live.',
  },
  {
    title: 'Queries determine what code gets surfaced',
    body: 'Generic chat like “do you see the code?” may return empty snippets. Ask for a file, symbol, route, or behavior you want inspected.',
  },
  {
    title: 'Prefer absolute paths',
    body: 'Use a full Windows path such as C:\\Users\\runni\\... instead of a partial path like \\Users\\runni\\....',
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
