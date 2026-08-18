import { BookOpen, Bot, Terminal, ShieldCheck, Sparkles } from 'lucide-react'

const sectionStyle = {
  padding: 16,
  marginBottom: 16,
  borderRadius: 12,
}

const terminalExamples = [
  {
    title: 'Check runtime status',
    command: 'python -m cli.main status',
    note: 'Fast health snapshot for the MammothOS runtime.',
  },
  {
    title: 'Run an ATLAS coding prompt',
    command: 'python -m cli.main atlas code generate "build a MammothOS notes panel"',
    note: 'Best for coding-oriented requests that should use the ATLAS coding workflow.',
  },
  {
    title: 'Scaffold a UI slice',
    command: 'python -m cli.main atlas ui component "create a neon command-center activity card"',
    note: 'Use UIBuilderAgent from inside the UI terminal without dropping back to PowerShell.',
  },
]

const promptPatterns = [
  {
    title: 'Good short prompt',
    body: 'Upgrade NotesPanel to MammothOS style with neon accents and approval-safe edits.',
  },
  {
    title: 'Best structured prompt',
    body: 'Upgrade NotesPanel to MammothOS style. Scope: ui\\mad-architecht-command-center\\src\\notes\\NotesPanel.tsx and shared tokens. Keep preview first on. Preserve existing note actions.',
  },
  {
    title: 'Plan + Execute prompt',
    body: 'Plan and implement a user tutorial flow for the agent panel, terminal usage, and manual page. Keep backend-first wiring and approval-safe edits.',
  },
]

const firstRunChecklist = [
  {
    step: '1) Open Manual first',
    detail: 'Read prompt shape + safety rules, then keep this page open while you run your first task.',
  },
  {
    step: '2) Run one Terminal playbook command',
    detail: 'Use the Terminal page to run one ATLAS CLI command from the in-app shell.',
  },
  {
    step: '3) Run one Agent template',
    detail: 'Pick a template from Agent Console, keep Preview First on, then run it.',
  },
  {
    step: '4) Review output + next action',
    detail: 'Confirm output is source-aware, then either apply approvals or rerun with tighter scope.',
  },
]

export default function ManualPage() {
  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <h1 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: 20, display: 'flex', alignItems: 'center', gap: 8 }}>
        <BookOpen size={20} color="var(--cyan)" /> Operator Manual
      </h1>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '2px solid var(--cyan)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <Sparkles size={16} color="var(--photon)" />
          <strong>Fast answer</strong>
        </div>
        <div style={{ color: 'var(--txt-sec)', lineHeight: 1.7, fontSize: '0.88rem' }}>
          Yes — you can run ATLAS CLI commands inside the UI terminal, and the coding agent can absolutely build polished manual,
          tutorial, and workflow UX once you give it a clear objective and scope.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sparkles size={16} color="var(--photon)" /> First-run tutorial
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
            <Terminal size={16} color="var(--cyan)" /> Terminal usage
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

        <div className="glass-card-solid" style={sectionStyle}>
          <h2 style={{ fontSize: '0.92rem', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Bot size={16} color="var(--violet)" /> How to prompt agents
          </h2>
          <div style={{ color: 'var(--txt-sec)', fontSize: '0.82rem', lineHeight: 1.7, marginBottom: 12 }}>
            A short sentence is valid. Better prompts usually include: the outcome you want, the files or surface area, and any safety or style constraints.
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {promptPatterns.map((item) => (
              <div key={item.title} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 12 }}>
                <div style={{ fontSize: '0.78rem', color: 'var(--txt-pri)', fontWeight: 600, marginBottom: 6 }}>{item.title}</div>
                <div style={{ color: 'var(--photon)', fontSize: '0.78rem', lineHeight: 1.6 }}>{item.body}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="glass-card-solid" style={{ ...sectionStyle, borderLeft: '2px solid var(--violet)' }}>
        <h2 style={{ fontSize: '0.92rem', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
          <ShieldCheck size={16} color="var(--violet)" /> Recommended workflow
        </h2>
        <ol style={{ margin: 0, paddingLeft: 20, color: 'var(--txt-sec)', lineHeight: 1.8, fontSize: '0.84rem' }}>
          <li>Use the Terminal page for concrete CLI actions like status, atlas code, atlas ui, and build commands.</li>
          <li>Use the Agent page for natural-language objectives, especially if you want Plan + Execute or preview-first coding edits.</li>
          <li>Keep Preview first on for changes that write files or mutate project state.</li>
          <li>Use the Manual page as the user-facing starter guide until a richer onboarding/tutorial flow ships.</li>
        </ol>
      </div>
    </div>
  )
}
