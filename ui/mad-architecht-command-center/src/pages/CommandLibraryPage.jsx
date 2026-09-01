import { useMemo, useState } from 'react'
import {
  BookOpen,
  Bot,
  Brain,
  ChevronDown,
  ChevronRight,
  FileText,
  FolderOpen,
  Globe,
  GraduationCap,
  MessageSquare,
  Search,
  Shield,
  Sparkles,
  Terminal,
} from 'lucide-react'

const QUICK_STARTS = [
  '/guide walk me through how atlas_chat handles different modes',
  'Look at api_server.py and explain this 422 error',
  'Start a lesson on Python loops and keep pacing gentle',
  'Use my uploaded materials to summarize today’s chapter',
  '/research official vite deployment guide',
  'Plan and execute a fix for the ATLAS sidebar with minimal edits',
]

const COMMANDS = [
  {
    category: 'Start here',
    icon: Sparkles,
    accent: 'var(--cyan)',
    description: 'High-signal starter prompts that show off the current product without extra setup.',
    commands: [
      {
        name: 'Tour MammothOS with Guide',
        syntax: '/guide walk me through the MammothOS landscape',
        example: '/guide walk me through the MammothOS landscape and point me at the most important files',
        description: 'Runs the repo-aware guide flow and returns expandable steps with live code references when the backend has repo access.',
        parameters: [],
        output: 'A structured guide with step cards, file references, and targeted explanations.',
        guardrails: 'Best in Assistant lanes with valid repo context. Empty or generic queries can still return weak context.',
        tips: 'Name the route, symbol, or file you care about to get better code grounding.',
        surface: 'Mammoth Mind or ATLAS Assistant',
        status: 'Live now',
      },
      {
        name: 'Explain a code path',
        syntax: 'Look at [file or route] and explain how it works',
        example: 'Look at api_server.py and explain how atlas_chat chooses assistant vs tutor vs build',
        description: 'Great for code tours, architecture learning, and rapid handoff understanding.',
        parameters: [
          { name: 'file or route', description: 'The target file, symbol, endpoint, or behavior.' },
        ],
        output: 'A code-grounded explanation focused on the requested path.',
        guardrails: 'If the query does not anchor to real code, the answer may be broad instead of snippet-rich.',
        tips: 'Ask for the exact route or function name when possible.',
        surface: 'Mammoth Mind Assistant',
        status: 'Live now',
      },
      {
        name: 'Start an adaptive lesson',
        syntax: 'Start a lesson on [topic]',
        example: 'Start a lesson on Python loops',
        description: 'Creates an ATLAS lesson with learner-aware pacing, exercise scaffolds, and feedback loops.',
        parameters: [
          { name: 'topic', description: 'The subject you want to learn or practice.' },
        ],
        output: 'Lesson framing, current exercise, and follow-up coaching surfaces.',
        guardrails: 'Tutor flows are assistive. They do not guarantee perfect curricular alignment to a specific institution.',
        tips: 'Save onboarding preferences first for better pacing and difficulty calibration.',
        surface: 'ATLAS Tutor',
        status: 'Live now',
      },
    ],
  },
  {
    category: 'Mammoth Mind + Guide',
    icon: MessageSquare,
    accent: 'var(--photon)',
    description: 'Repo-aware prompts for planning, code explanation, /guide, and multi-thread work.',
    commands: [
      {
        name: 'Guide a specific subsystem',
        syntax: '/guide walk me through [subsystem]',
        example: '/guide walk me through the guide agent and repo context pipeline',
        description: 'Targets a subsystem and produces structured, expandable learning steps instead of a single wall of text.',
        parameters: [
          { name: 'subsystem', description: 'Route, feature, agent, or file area to inspect.' },
        ],
        output: 'Guide summary, file references, and expandable code-backed steps.',
        guardrails: 'Works best when the repo path points to the machine hosting the backend.',
        tips: 'Pair with a valid repo preset and a concrete subsystem name.',
        surface: 'Mammoth Mind Assistant',
        lane: 'Assistant',
        status: 'Live now',
      },
      {
        name: 'Plan before changing code',
        syntax: 'Plan a fix for [problem] and list the smallest safe steps',
        example: 'Plan a fix for guide step rendering and list the smallest safe steps',
        description: 'Useful when you want structure before editing, especially for risky or cross-surface changes.',
        parameters: [
          { name: 'problem', description: 'The bug, workflow gap, or feature request.' },
        ],
        output: 'A staged implementation plan with focused next actions.',
        guardrails: 'Planning does not validate the code by itself; still verify with builds/tests.',
        tips: 'Include what must not change to constrain the plan.',
        surface: 'Mammoth Mind Assistant',
        lane: 'Assistant',
        status: 'Live now',
      },
      {
        name: 'Use attachments for context',
        syntax: 'Review the attached files and tell me [goal]',
        example: 'Review the attached files and tell me what architecture risks you see',
        description: 'Uses uploaded chat files as extra context for planning, explaining, or summarizing.',
        parameters: [
          { name: 'goal', description: 'What you want from the attached file set.' },
        ],
        output: 'A response grounded in the uploaded file previews and the current chat thread.',
        guardrails: 'Large or binary files may only contribute partial preview text.',
        tips: 'Attach only the files relevant to the question so the prompt stays focused.',
        surface: 'Mammoth Mind Assistant',
        lane: 'Assistant',
        status: 'Live now',
      },
      {
        name: 'Switch threads intentionally',
        syntax: 'Create a new thread for [topic]',
        example: 'Create a new thread for tenant auth rollout planning',
        description: 'A good habit prompt when you want to keep one line of work cleanly separated from another.',
        parameters: [
          { name: 'topic', description: 'The purpose of the new thread.' },
        ],
        output: 'A cleaner chat history and easier future retrieval.',
        guardrails: 'Thread creation is a UI feature; the prompt is just the workflow reminder.',
        tips: 'Use one thread per objective: bugfix, deploy, architecture pass, or lesson topic.',
        surface: 'Mammoth Mind',
        status: 'Workflow pattern',
      },
    ],
  },
  {
    category: 'ATLAS learning lanes',
    icon: GraduationCap,
    accent: 'var(--violet)',
    description: 'Prompts tuned for Assistant, Tutor, and Build behavior inside the ATLAS Tutor page and FAB.',
    commands: [
      {
        name: 'Assistant lane architecture help',
        syntax: 'Explain [topic] and give me the most important next file or concept to inspect',
        example: 'Explain how the lesson workspace is wired and give me the next file to inspect',
        description: 'Use the least restrictive ATLAS lane for general explanation, guide-style help, and workspace tours.',
        parameters: [
          { name: 'topic', description: 'Architecture or product area to explain.' },
        ],
        output: 'A clear explanation with a concrete next pointer.',
        guardrails: 'Assistant is broader, but still not a substitute for validating against code or lesson state.',
        tips: 'If you need live repo grounding, prefix with /guide.',
        surface: 'ATLAS Tutor',
        lane: 'Assistant',
        status: 'Live now',
      },
      {
        name: 'Tutor lane coaching',
        syntax: 'I am stuck on [step]. Diagnose the misunderstanding, then give me one small next action.',
        example: 'I am stuck on my loop condition. Diagnose the misunderstanding, then give me one small next action.',
        description: 'Keeps the response learner-safe and focused on coaching instead of answer dumping.',
        parameters: [
          { name: 'step', description: 'The exact point of confusion or failure.' },
        ],
        output: 'A hint-driven explanation and a small next move.',
        guardrails: 'Tutor mode can refuse direct answer requests for active exercises.',
        tips: 'Paste the failing snippet or describe the exact symptom for sharper hints.',
        surface: 'ATLAS Tutor',
        lane: 'Tutor',
        status: 'Live now',
      },
      {
        name: 'Build lane worked example',
        syntax: 'Show me how to structure [solution], but stop short of a full final answer',
        example: 'Show me how to structure this function, but stop short of a full final answer',
        description: 'Best for implementation framing, scaffold thinking, and partial worked examples.',
        parameters: [
          { name: 'solution', description: 'The concept, component, or code shape you need help structuring.' },
        ],
        output: 'A build-oriented outline, example shape, or partial implementation strategy.',
        guardrails: 'Still lesson-aware; not meant to bypass tutoring restrictions.',
        tips: 'Ask for pseudocode, checklist, or skeleton if you want even more guardrails.',
        surface: 'ATLAS Tutor',
        lane: 'Build',
        status: 'Live now',
      },
      {
        name: 'Use learning materials',
        syntax: 'Use my uploaded materials to summarize [topic] and give me a quick self-check',
        example: 'Use my uploaded materials to summarize today’s biology chapter and give me a quick self-check',
        description: 'Leverages the ATLAS materials library as grounding context for lesson help.',
        parameters: [
          { name: 'topic', description: 'The chapter, worksheet, or concept to target.' },
        ],
        output: 'A materials-aware summary plus a retention check.',
        guardrails: 'Results depend on the quality and readability of the uploaded material preview.',
        tips: 'Rename or tag materials clearly so you can keep large course libraries organized.',
        surface: 'ATLAS Tutor',
        lane: 'Tutor or Assistant',
        status: 'Live now',
      },
    ],
  },
  {
    category: 'Files, threads, and artifacts',
    icon: FolderOpen,
    accent: 'var(--amber)',
    description: 'Practical prompts and workflows for keeping context organized instead of lost in one giant conversation.',
    commands: [
      {
        name: 'Summarize an uploaded file',
        syntax: 'Summarize the attached file for [audience] with [format]',
        example: 'Summarize the attached file for a beginner with bullet points',
        description: 'Converts raw uploads into reusable notes, summaries, or implementation briefs.',
        parameters: [
          { name: 'audience', description: 'Who the explanation is for.' },
          { name: 'format', description: 'Bullets, checklist, recap, outline, etc.' },
        ],
        output: 'A targeted summary grounded in the file preview.',
        guardrails: 'Very large or binary files can have incomplete extracted text.',
        tips: 'Use this before asking follow-up questions so the model is grounded in the source.',
        surface: 'Mammoth Mind or ATLAS',
        status: 'Live now',
      },
      {
        name: 'Save the response as an artifact',
        syntax: 'Save this as a report',
        example: 'Save this as a report and keep it in markdown form',
        description: 'Use the FAB save controls to turn the latest useful response into a durable artifact.',
        parameters: [],
        output: 'A .md or .txt report stored in the artifact library.',
        guardrails: 'Saving is a UI action tied to the latest assistant message.',
        tips: 'Use reports for deployment notes, architecture tours, and validated research summaries.',
        surface: 'ATLAS FAB or Mammoth Mind FAB',
        status: 'Live now',
      },
      {
        name: 'Promote work into Task Inbox',
        syntax: 'Turn this into a task list with clear next steps',
        example: 'Turn this into a task list with clear next steps for the ATLAS lesson renderer',
        description: 'A good pattern when a chat answer should become actionable follow-through.',
        parameters: [
          { name: 'next steps', description: 'The work items that should be extracted from the conversation.' },
        ],
        output: 'A structured checklist ready to copy into Task Inbox or a work tracker.',
        guardrails: 'Task capture is only useful if the list is concrete and scoped.',
        tips: 'Ask for acceptance criteria and validation steps in the same prompt.',
        surface: 'Mammoth Mind or ATLAS Assistant',
        status: 'Workflow pattern',
      },
    ],
  },
  {
    category: 'Live web research',
    icon: Globe,
    accent: 'var(--cyan)',
    description: 'Current-source retrieval when model memory is not enough.',
    commands: [
      {
        name: 'Research a live topic',
        syntax: '/research [query]',
        example: '/research official DeepSeek API quota error docs',
        description: 'Runs a live web research pass and returns a concise practical brief.',
        parameters: [
          { name: 'query', description: 'The topic, source type, or official docs target.' },
        ],
        output: 'A source-aware summary with evidence-oriented takeaways.',
        guardrails: 'External pages can be stale, biased, or incomplete. Verify important claims with primary docs.',
        tips: 'Add “official docs”, “release notes”, or a domain name to reduce noise.',
        surface: 'Mammoth Mind or ATLAS',
        status: 'Live now',
      },
      {
        name: 'Summarize one URL',
        syntax: '/web [url]',
        example: '/web https://docs.python.org/3/whatsnew/3.12.html',
        description: 'Fetches one public page and extracts the most useful parts for the current task.',
        parameters: [
          { name: 'url', description: 'The public URL to retrieve.' },
        ],
        output: 'A cleaned summary of the page.',
        guardrails: 'Login-protected or blocked pages may fail or return partial content.',
        tips: 'Best when you already trust the source and just want fast extraction.',
        surface: 'Mammoth Mind or ATLAS',
        status: 'Live now',
      },
    ],
  },
  {
    category: 'Operator + build workflows',
    icon: Bot,
    accent: 'var(--violet)',
    description: 'Prompts for the Agent and Terminal surfaces when you need structured execution instead of chat alone.',
    commands: [
      {
        name: 'Plan and execute a bounded fix',
        syntax: 'Plan and execute a fix for [bug]. Keep changes minimal and verify with [test/build].',
        example: 'Plan and execute a fix for guide expansion in ATLAS chat. Keep changes minimal and verify with npm run build.',
        description: 'A strong shape for targeted implementation work with explicit verification.',
        parameters: [
          { name: 'bug', description: 'The defect or issue to fix.' },
          { name: 'test/build', description: 'The smallest validation command that proves the change.' },
        ],
        output: 'A bounded implementation pass with clear validation.',
        guardrails: 'Always define what must stay unchanged to avoid scope creep.',
        tips: 'Name the file or route if you already know where the issue lives.',
        surface: 'Agent',
        status: 'Live now',
      },
      {
        name: 'Read-only audit',
        syntax: 'Audit [surface] for risks only. Do not modify files.',
        example: 'Audit the ATLAS Tutor page for stale UX copy. Do not modify files.',
        description: 'Useful for review passes when you want findings before implementation.',
        parameters: [
          { name: 'surface', description: 'The page, route, or feature to inspect.' },
        ],
        output: 'A prioritized list of risks, gaps, or improvements.',
        guardrails: 'This is not a fix prompt; it is intentionally read-only.',
        tips: 'Ask for high-confidence issues only when you want a tighter result set.',
        surface: 'Agent',
        status: 'Live now',
      },
      {
        name: 'Deterministic terminal validation',
        syntax: 'Run [command] and tell me what changed or failed',
        example: 'Run npm run build and tell me what failed',
        description: 'A good operator framing when using the terminal or delegating validation tasks.',
        parameters: [
          { name: 'command', description: 'The exact validation or inspection command.' },
        ],
        output: 'Raw or summarized command results.',
        guardrails: 'Use known-safe commands; terminal is an execution surface, not a sandbox.',
        tips: 'Prefer the smallest command that proves the behavior you changed.',
        surface: 'Terminal',
        status: 'Live now',
      },
    ],
  },
  {
    category: 'Guardrails and answer quality',
    icon: Shield,
    accent: 'var(--amber)',
    description: 'Prompt shapes that improve answer quality without fighting the platform.',
    commands: [
      {
        name: 'State your objective and output shape',
        syntax: 'I want to [goal]. Respond with [format] and keep it [constraint].',
        example: 'I want to understand this route. Respond with a 5-step walkthrough and keep it code-grounded.',
        description: 'A general-purpose prompt formula that makes almost every response better.',
        parameters: [
          { name: 'goal', description: 'What outcome you want.' },
          { name: 'format', description: 'Checklist, walkthrough, bullets, table, patch plan, etc.' },
          { name: 'constraint', description: 'Short, deep, beginner-friendly, no code changes, etc.' },
        ],
        output: 'A response that is shaped to your actual need instead of generic prose.',
        guardrails: 'Better framing improves usefulness, not truth by itself.',
        tips: 'Add audience and success criteria when the result quality really matters.',
        surface: 'Any chat surface',
        status: 'Always useful',
      },
      {
        name: 'Ask for verification',
        syntax: 'Explain [thing], then tell me how to verify it',
        example: 'Explain why this deploy looks stale, then tell me how to verify the live commit',
        description: 'Pushes the system toward measurable output instead of vibes-only confidence.',
        parameters: [
          { name: 'thing', description: 'The claim, bug, or explanation to validate.' },
        ],
        output: 'Explanation plus validation steps.',
        guardrails: 'Verification steps are only as good as the environment they can access.',
        tips: 'This is especially valuable for deployment, auth, and billing questions.',
        surface: 'Any chat surface',
        status: 'Always useful',
      },
    ],
  },
]

const BADGE_STYLE = {
  padding: '2px 8px',
  borderRadius: 999,
  fontSize: '0.64rem',
  fontWeight: 700,
  background: 'rgba(77,166,255,0.12)',
  border: '1px solid rgba(77,166,255,0.28)',
  color: 'var(--photon)',
  whiteSpace: 'nowrap',
}

function MetaPill({ children }) {
  return (
    <span style={{ padding: '3px 8px', borderRadius: 999, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-mut)', fontSize: '0.64rem' }}>
      {children}
    </span>
  )
}

function CommandCard({ cmd }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', borderRadius: 14, overflow: 'hidden', marginBottom: 10 }}>
      <button
        onClick={() => setExpanded(v => !v)}
        style={{ width: '100%', display: 'flex', alignItems: 'flex-start', gap: 12, padding: '14px 16px', background: 'none', border: 'none', cursor: 'pointer', textAlign: 'left' }}
      >
        <span style={{ marginTop: 2, color: 'var(--txt-mut)', flexShrink: 0 }}>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
            <span style={{ fontSize: '0.92rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{cmd.name}</span>
            {cmd.status && <span style={BADGE_STYLE}>{cmd.status}</span>}
            {cmd.badge && <span style={BADGE_STYLE}>{cmd.badge}</span>}
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
            {cmd.surface ? <MetaPill>{cmd.surface}</MetaPill> : null}
            {cmd.lane ? <MetaPill>{cmd.lane}</MetaPill> : null}
          </div>
          <code style={{ display: 'block', fontSize: '0.75rem', color: 'var(--cyan)', background: 'rgba(0,0,0,0.3)', padding: '6px 8px', borderRadius: 6, fontFamily: 'monospace', marginBottom: cmd.example ? 6 : 0, wordBreak: 'break-word' }}>
            {cmd.syntax}
          </code>
          {cmd.example ? (
            <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--txt-mut)', fontStyle: 'italic' }}>
              e.g. &ldquo;{cmd.example}&rdquo;
            </p>
          ) : null}
        </div>
      </button>

      {expanded ? (
        <div style={{ padding: '0 16px 16px 42px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ margin: 0, fontSize: '0.83rem', color: 'var(--txt-sec)', lineHeight: 1.65 }}>
            {cmd.description}
          </p>

          {cmd.parameters?.length ? (
            <div>
              <p style={{ margin: '0 0 6px', fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--txt-mut)' }}>Parameters</p>
              {cmd.parameters.map((p) => (
                <div key={p.name} style={{ display: 'flex', gap: 8, marginBottom: 4, fontSize: '0.8rem' }}>
                  <code style={{ color: 'var(--violet)', fontFamily: 'monospace', flexShrink: 0 }}>[{p.name}]</code>
                  <span style={{ color: 'var(--txt-sec)' }}>{p.description}</span>
                </div>
              ))}
            </div>
          ) : null}

          <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
            <div style={{ background: 'rgba(0,200,100,0.06)', border: '1px solid rgba(0,200,100,0.15)', borderRadius: 8, padding: '10px 12px' }}>
              <p style={{ margin: '0 0 4px', fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#4ade80' }}>Expected output</p>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.55 }}>{cmd.output}</p>
            </div>
            <div style={{ background: 'rgba(248,200,60,0.06)', border: '1px solid rgba(248,200,60,0.15)', borderRadius: 8, padding: '10px 12px' }}>
              <p style={{ margin: '0 0 4px', fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--amber)' }}>Guardrails</p>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.55 }}>{cmd.guardrails}</p>
            </div>
          </div>

          {cmd.tips ? (
            <div style={{ background: 'rgba(180,124,255,0.06)', border: '1px solid rgba(180,124,255,0.15)', borderRadius: 8, padding: '10px 12px' }}>
              <p style={{ margin: '0 0 4px', fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--violet)' }}>Pro tip</p>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.55 }}>{cmd.tips}</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

export default function CommandLibraryPage() {
  const [search, setSearch] = useState('')
  const [openCategory, setOpenCategory] = useState('Start here')

  const query = search.trim().toLowerCase()

  const filtered = useMemo(() => (
    COMMANDS.map((category) => ({
      ...category,
      commands: category.commands.filter((cmd) => {
        const haystack = [
          cmd.name,
          cmd.description,
          cmd.syntax,
          cmd.example || '',
          cmd.output,
          cmd.guardrails,
          cmd.tips || '',
          cmd.surface || '',
          cmd.lane || '',
          cmd.status || '',
        ].join(' ').toLowerCase()
        return !query || haystack.includes(query)
      }),
    })).filter((category) => !query || category.commands.length > 0)
  ), [query])

  const totalVisibleCommands = filtered.reduce((sum, category) => sum + category.commands.length, 0)

  return (
    <div style={{ padding: '28px 20px 80px', maxWidth: 1020, margin: '0 auto' }}>
      <div className="glass-card-solid" style={{ padding: 20, borderRadius: 18, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <BookOpen size={22} color="var(--violet)" />
          <h1 style={{ margin: 0, fontSize: '1.7rem', fontWeight: 800, color: 'var(--txt-pri)' }}>Command Library</h1>
        </div>
        <p style={{ margin: '0 0 14px', fontSize: '0.92rem', color: 'var(--txt-sec)', lineHeight: 1.65, maxWidth: 720 }}>
          The clean prompt library for Mammoth Mind, ATLAS, live web research, and operator workflows. Everything here reflects the current surfaces instead of older placeholder or coming-soon copy.
        </p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <MetaPill>{COMMANDS.length} categories</MetaPill>
          <MetaPill>{totalVisibleCommands} visible commands</MetaPill>
          <MetaPill>Guide + repo-aware</MetaPill>
          <MetaPill>ATLAS lane-aware</MetaPill>
          <MetaPill>Thread + file workflows</MetaPill>
        </div>
      </div>

      <div className="glass-card-solid" style={{ padding: 18, borderRadius: 18, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <Brain size={16} color="var(--cyan)" />
          <strong style={{ color: 'var(--txt-pri)', fontSize: '0.9rem' }}>Rich quick starts</strong>
        </div>
        <div style={{ display: 'grid', gap: 10, gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))' }}>
          {QUICK_STARTS.map((item) => (
            <button
              key={item}
              onClick={() => setSearch(item)}
              style={{ padding: '12px 14px', borderRadius: 12, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.79rem', lineHeight: 1.55, textAlign: 'left', cursor: 'pointer' }}
            >
              {item}
            </button>
          ))}
        </div>
      </div>

      <div style={{ position: 'relative', marginBottom: 16 }}>
        <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--txt-mut)' }} />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search commands, surfaces, lanes, or outputs..."
          style={{ width: '100%', padding: '11px 12px 11px 36px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12, color: 'var(--txt-pri)', fontSize: '0.88rem', outline: 'none', boxSizing: 'border-box' }}
        />
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 22 }}>
        {COMMANDS.map((category) => (
          <button
            key={category.category}
            onClick={() => {
              setOpenCategory(category.category)
              setSearch('')
            }}
            style={{
              padding: '8px 12px',
              borderRadius: 999,
              border: `1px solid ${openCategory === category.category ? category.accent : 'rgba(255,255,255,0.08)'}`,
              background: openCategory === category.category ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.02)',
              color: openCategory === category.category ? 'var(--txt-pri)' : 'var(--txt-sec)',
              fontSize: '0.74rem',
              cursor: 'pointer',
            }}
          >
            {category.category}
          </button>
        ))}
      </div>

      {filtered.map((category) => {
        const Icon = category.icon
        const isOpen = Boolean(query) || openCategory === category.category

        return (
          <div key={category.category} style={{ marginBottom: 20 }}>
            <button
              onClick={() => setOpenCategory(isOpen && !query ? null : category.category)}
              style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 10, padding: '14px 16px', background: 'rgba(255,255,255,0.03)', border: `1px solid ${isOpen ? category.accent : 'rgba(255,255,255,0.07)'}`, borderRadius: isOpen ? '14px 14px 0 0' : 14, cursor: 'pointer', textAlign: 'left' }}
            >
              <Icon size={16} color={category.accent} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ margin: 0, fontSize: '0.96rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{category.category}</p>
                <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--txt-mut)' }}>{category.description}</p>
              </div>
              <span style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', flexShrink: 0 }}>
                {category.commands.length} {category.commands.length === 1 ? 'command' : 'commands'}
              </span>
              <span style={{ color: 'var(--txt-mut)', flexShrink: 0 }}>
                {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </span>
            </button>

            {isOpen ? (
              <div style={{ border: `1px solid ${category.accent}`, borderTop: 'none', borderRadius: '0 0 14px 14px', padding: '12px 12px 4px', background: 'rgba(255,255,255,0.01)' }}>
                {category.commands.map((cmd) => (
                  <CommandCard key={`${category.category}-${cmd.name}`} cmd={cmd} />
                ))}
              </div>
            ) : null}
          </div>
        )
      })}

      {!filtered.length ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--txt-mut)', fontSize: '0.88rem' }}>
          No commands found for &ldquo;{search}&rdquo;. Try a file name, a lane, /guide, Tutor, Build, research, or attachments.
        </div>
      ) : null}

      <div className="glass-card-solid" style={{ padding: 18, borderRadius: 18, marginTop: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <FileText size={16} color="var(--photon)" />
          <strong style={{ color: 'var(--txt-pri)', fontSize: '0.9rem' }}>Prompt formula to remember</strong>
        </div>
        <div style={{ color: 'var(--photon)', fontSize: '0.84rem', lineHeight: 1.65 }}>
          I want to <strong>[goal]</strong>. Use <strong>[surface or lane]</strong>. Respond with <strong>[format]</strong>. Keep it <strong>[constraint]</strong>. If it matters, tell me how to verify it.
        </div>
      </div>
    </div>
  )
}
