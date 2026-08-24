import {
  BookOpen,
  Bot,
  Terminal,
  ShieldCheck,
  Sparkles,
  GraduationCap,
  MessageSquare,
  CheckCircle2,
  AlertTriangle,
  Gauge,
  Compass,
  Lock,
  ClipboardList,
} from 'lucide-react'
import OnboardingGuide from '../components/OnboardingGuide'

const sectionStyle = {
  padding: 16,
  marginBottom: 16,
  borderRadius: 12,
}

const firstRunChecklist = [
  {
    step: '1) Start in Manual',
    detail: 'Read this page once before touching Agent or Terminal. It explains what each surface is for and what can change project/device state.',
  },
  {
    step: '2) Use Lessons + ATLAS first',
    detail: 'Run one lesson cycle (intro → content → feedback loop → exercise) so your first test validates the learner flow.',
  },
  {
    step: '3) Record results in Account',
    detail: 'Use Account metrics (goals, heatmap, confidence, wins) to confirm analytics are updating.',
  },
  {
    step: '4) Only then test operator tools',
    detail: 'If your role allows it, run Agent and Terminal workflows with preview/approval modes first.',
  },
]

const upgradePhases = [
  {
    title: 'Phase 1: execution quality loop',
    detail: 'Require plan -> act -> verify -> retry with explicit success checks so agents stop returning generic summaries.',
  },
  {
    title: 'Phase 2: browser automation',
    detail: 'Move beyond page snapshots into stateful navigation, form filling, and replayable browser actions.',
  },
  {
    title: 'Phase 3: memory + evals',
    detail: 'Track task outcomes, regression cases, and quality benchmarks so improvements stay measurable.',
  },
  {
    title: 'Phase 4: docs + UI alignment',
    detail: 'Keep this Manual page, ATLAS_MANUAL.md, and the root README in sync whenever behavior changes.',
  },
]

const atlasFabPatterns = [
  {
    title: 'Clarify a concept',
    prompt: 'Explain this lesson objective in plain language, then give me one practical example and one quick self-check question.',
  },
  {
    title: 'Recover from confusion',
    prompt: 'I am stuck on this step. Diagnose likely misunderstanding, give one correction, then give me the smallest next action.',
  },
  {
    title: 'Prepare for exercise',
    prompt: 'Before I submit, give me a short checklist of what a strong response should include for this exercise.',
  },
  {
    title: 'Internet research command',
    prompt: 'Use /research mammoth os provider fallback to get a concise internet brief, then save the response as a report.',
  },
]

const atlasTutorPatterns = [
  {
    title: 'Lesson kickoff',
    prompt: 'Start a lesson on [topic]. Keep pacing steady and include teaching points before practice.',
  },
  {
    title: 'Adaptive follow-up',
    prompt: 'Use my recent weak concepts and give me one targeted practice rep with feedback criteria.',
  },
  {
    title: 'Review and retention',
    prompt: 'Generate a recap, 3 flashcard prompts, and a one-day revisit plan.',
  },
]

const guardrailRows = [
  {
    name: 'Accuracy + confidence shaping',
    detail: 'Outputs can be useful but imperfect. Use source checks, recap loops, and follow-up questions for critical decisions.',
  },
  {
    name: 'Preview / approval gating',
    detail: 'For file-changing or high-impact actions, prefer preview-first and approval queues before apply.',
  },
  {
    name: 'Role and access boundaries',
    detail: 'Some routes/surfaces are tiered or admin-restricted. Test with the intended role, not owner assumptions.',
  },
  {
    name: 'No guarantee of external truth',
    detail: 'Treat generated content as assistive guidance, not legal/medical/financial truth without verification.',
  },
]

const pagePlaybook = [
  {
    page: 'Lessons',
    purpose: 'Primary structured learning flow.',
    bestUse: 'Start here for learner testing. Verify intro/content/practice sequencing and clarity.',
    avoid: 'Skipping directly to exercises without checking lesson context.',
  },
  {
    page: 'ATLAS Tutor',
    purpose: 'Adaptive lesson orchestration and practice feedback.',
    bestUse: 'Use for iterative coaching, recap, quiz, and regeneration of exercises.',
    avoid: 'Treating one response as final truth without validation.',
  },
  {
    page: 'Mammoth Mind / ATLAS FAB chat',
    purpose: 'Fast conversational assistant for context-aware help.',
    bestUse: 'Use scoped prompts with explicit outcome, constraints, and expected format.',
    avoid: 'Broad vague prompts that hide objective and success criteria.',
  },
  {
    page: 'Account',
    purpose: 'Progress analytics and learner story.',
    bestUse: 'Track goals, milestones, streak heatmap, confidence trend, wins, and awards.',
    avoid: 'Assuming local-only analytics are globally synced unless backend persistence is enabled.',
  },
  {
    page: 'Agent Console',
    purpose: 'Operator-grade plan/execute and approval workflows.',
    bestUse: 'Use preview-first for any write path, then review the Coding Artifact panel + Run History trace before apply.',
    avoid: 'Running broad, unconstrained prompts that can mutate too much.',
  },
  {
    page: 'Artifacts',
    purpose: 'Saved generated reports and reusable output library.',
    bestUse: 'Save .md/.txt from the FAB and keep finalized research/coding outputs here for replayable context.',
    avoid: 'Treating unsaved chat responses as permanent records.',
  },
  {
    page: 'Task Inbox',
    purpose: 'Queued task cards and lightweight workflow tracking.',
    bestUse: 'Capture tasks from Mammoth Mind and move them through queued/in-progress/complete states.',
    avoid: 'Losing implementation follow-through inside long chat threads.',
  },
  {
    page: 'Terminal',
    purpose: 'Direct command execution.',
    bestUse: 'Use deterministic commands and read output carefully before follow-up actions.',
    avoid: 'Running unknown/destructive commands during tester sessions.',
  },
]

const terminalExamples = [
  {
    title: 'Check runtime status',
    command: 'python -m cli.main status',
    note: 'Use before tests to ensure services are healthy.',
  },
  {
    title: 'Run ATLAS coding prompt',
    command: 'python -m cli.main atlas code generate "build a lessons progress widget"',
    note: 'For coding workflows when authorized.',
  },
  {
    title: 'Scaffold a UI slice',
    command: 'python -m cli.main atlas ui component "create an account insights card"',
    note: 'Useful for bounded UI experiments.',
  },
]

const agentPatterns = [
  {
    title: 'Patch existing',
    body: 'Patch existing [file/surface]. Keep changes minimal, preserve behavior, and return verification steps.',
  },
  {
    title: 'Plan + execute',
    body: 'Plan and execute [objective] with approval-safe edits, explicit constraints, and rollback awareness.',
  },
  {
    title: 'Audit mode',
    body: 'Audit [surface] for gaps/risks only. Do not modify files. Return prioritized findings.',
  },
]

export default function ManualPage({ setPage }) {
  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
        <BookOpen size={20} color="var(--cyan)" /> Platform Manual
      </h1>

      <OnboardingGuide variant="banner" currentPage="manual" setPage={setPage} />

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '2px solid var(--cyan)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <Compass size={16} color="var(--photon)" />
          <strong>Mission of this manual</strong>
        </div>
        <div style={{ color: 'var(--txt-sec)', lineHeight: 1.7, fontSize: '0.88rem' }}>
          This is the operator + tester playbook for MammothOS and ATLAS. It explains how to prompt well, where guardrails apply, what each page is for, and how to run efficient test sessions without unintended platform changes.
        </div>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '2px solid var(--violet)' }}>
        <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Gauge size={16} color="var(--violet)" /> 7 to 8 upgrade phases
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 10 }}>
          {upgradePhases.map((item) => (
            <div key={item.title} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: '0.78rem', color: 'var(--txt-pri)', fontWeight: 700, marginBottom: 6 }}>{item.title}</div>
              <div style={{ color: 'var(--txt-sec)', fontSize: '0.76rem', lineHeight: 1.6 }}>{item.detail}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <CheckCircle2 size={16} color="var(--photon)" /> First-run tester checklist
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {firstRunChecklist.map((item) => (
              <div key={item.step} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--txt-pri)', fontWeight: 600, marginBottom: 6 }}>{item.step}</div>
                <div style={{ color: 'var(--txt-sec)', fontSize: '0.76rem', lineHeight: 1.6 }}>{item.detail}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <ShieldCheck size={16} color="var(--violet)" /> Accuracy + safety guardrails
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {guardrailRows.map((item) => (
              <div key={item.name} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--txt-pri)', fontWeight: 600, marginBottom: 6 }}>{item.name}</div>
                <div style={{ color: 'var(--txt-sec)', fontSize: '0.76rem', lineHeight: 1.6 }}>{item.detail}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <MessageSquare size={16} color="var(--cyan)" /> ATLAS FAB chat: best prompt shapes
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {atlasFabPatterns.map((item) => (
              <div key={item.title} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--txt-pri)', fontWeight: 600, marginBottom: 6 }}>{item.title}</div>
                <div style={{ color: 'var(--photon)', fontSize: '0.76rem', lineHeight: 1.6 }}>{item.prompt}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <GraduationCap size={16} color="var(--violet)" /> ATLAS Tutor: what it can / cannot do
          </h2>
          <div style={{ color: 'var(--txt-sec)', fontSize: '0.82rem', lineHeight: 1.7, marginBottom: 10 }}>
            <strong style={{ color: 'var(--txt-pri)' }}>Can do:</strong> lesson generation, recap/quiz/review, adaptive pacing, learner-context-aware prompting, and iterative coaching.
          </div>
          <div style={{ color: 'var(--txt-sec)', fontSize: '0.82rem', lineHeight: 1.7, marginBottom: 12 }}>
            <strong style={{ color: 'var(--txt-pri)' }}>Cannot guarantee:</strong> perfect factual accuracy, policy/legal/medical certainty, or autonomous permission to modify sensitive system state.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {atlasTutorPatterns.map((item) => (
              <div key={item.title} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--txt-pri)', fontWeight: 600, marginBottom: 6 }}>{item.title}</div>
                <div style={{ color: 'var(--photon)', fontSize: '0.76rem', lineHeight: 1.6 }}>{item.prompt}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '2px solid var(--cyan)' }}>
        <h2 style={{ fontSize: '0.92rem', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Gauge size={16} color="var(--cyan)" /> Page-by-page testing guide
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10 }}>
          {pagePlaybook.map((item) => (
            <div key={item.page} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 12 }}>
              <div style={{ fontSize: '0.8rem', color: 'var(--txt-pri)', fontWeight: 700, marginBottom: 6 }}>{item.page}</div>
              <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)', lineHeight: 1.55, marginBottom: 5 }}><strong>Purpose:</strong> {item.purpose}</div>
              <div style={{ fontSize: '0.74rem', color: 'var(--txt-sec)', lineHeight: 1.55, marginBottom: 5 }}><strong>Best use:</strong> {item.bestUse}</div>
              <div style={{ fontSize: '0.74rem', color: '#fca5a5', lineHeight: 1.55 }}><strong>Avoid:</strong> {item.avoid}</div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Bot size={16} color="var(--violet)" /> Agent panel playbook (detailed)
          </h2>
          <div style={{ color: 'var(--txt-sec)', fontSize: '0.82rem', lineHeight: 1.7, marginBottom: 12 }}>
            Use Agent panel for plan/execute orchestration and structured objectives. Prefer explicit scope, constraints, and expected output.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {agentPatterns.map((item) => (
              <div key={item.title} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--txt-pri)', fontWeight: 600, marginBottom: 6 }}>{item.title}</div>
                <div style={{ color: 'var(--photon)', fontSize: '0.76rem', lineHeight: 1.6 }}>{item.body}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Terminal size={16} color="var(--cyan)" /> Terminal playbook (detailed)
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {terminalExamples.map((item) => (
              <div key={item.command} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--txt-pri)', fontWeight: 600, marginBottom: 6 }}>{item.title}</div>
                <code style={{ display: 'block', whiteSpace: 'pre-wrap', color: 'var(--photon)', fontSize: '0.78rem' }}>{item.command}</code>
                <div style={{ color: 'var(--txt-sec)', fontSize: '0.76rem', marginTop: 6, lineHeight: 1.6 }}>{item.note}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '2px solid var(--amber)' }}>
        <h2 style={{ fontSize: '0.92rem', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Lock size={16} color="var(--amber)" /> Tester restrictions + access intent
        </h2>
        <div style={{ color: 'var(--txt-sec)', lineHeight: 1.75, fontSize: '0.84rem' }}>
          If testers should have admin visibility but not mutation-heavy surfaces (like coding-agent/terminal), enforce role-based restrictions explicitly.
          Keep owner-only controls on sensitive pages and verify with a non-owner test account before each test cycle.
        </div>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '2px solid var(--violet)' }}>
        <h2 style={{ fontSize: '0.92rem', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
          <ClipboardList size={16} color="var(--violet)" /> Efficient test-session template
        </h2>
        <ol style={{ margin: 0, paddingLeft: 20, color: 'var(--txt-sec)', lineHeight: 1.8, fontSize: '0.84rem' }}>
          <li>Log in as the intended tester role and verify visible navigation matches role policy.</li>
          <li>Run one full lesson cycle and one ATLAS chat clarification cycle.</li>
          <li>Check Account analytics: goals, milestones, heatmap, confidence, wins, awards.</li>
          <li>Capture one bug + one UX friction + one improvement idea.</li>
          <li>Log findings in Notes/Build Log for triage.</li>
        </ol>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '2px solid var(--cyan)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <AlertTriangle size={16} color="var(--cyan)" />
          <strong>Reminder</strong>
        </div>
        <div style={{ color: 'var(--txt-sec)', lineHeight: 1.7, fontSize: '0.88rem' }}>
          Use this manual as the operating baseline for coworker tests. When behavior changes (auth rules, tier gates, approval policy, or page capabilities), update this page in the same PR so testers always see current instructions.
        </div>
      </div>
    </div>
  )
}
