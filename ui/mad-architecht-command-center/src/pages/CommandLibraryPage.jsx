import { useState } from 'react'
import { Search, ChevronDown, ChevronRight, BookOpen, Brain, FileText, Calendar, FolderOpen, Microscope, Zap, Shield, Globe } from 'lucide-react'

const COMMANDS = [
  {
    category: 'ATLAS Tutor Chat',
    icon: Brain,
    accent: 'var(--violet)',
    description: 'Commands for the ATLAS FAB button and full tutor chat page.',
    commands: [
      {
        name: 'Ask a concept question',
        syntax: 'What is [concept]?',
        example: 'What is photosynthesis?',
        description: 'Ask ATLAS to explain any topic, concept, or idea clearly. ATLAS adapts its explanation to your learning level.',
        parameters: [
          { name: 'concept', description: 'The topic, term, or idea you want explained.' },
        ],
        output: 'A structured explanation with key points, real-world examples, and a quick summary.',
        guardrails: 'ATLAS will not invent facts. If uncertain, it will say so and guide you to verify.',
        tips: 'Be specific. "What is the difference between RAM and a hard drive?" works better than just "explain computers".',
      },
      {
        name: 'Ask for a study plan',
        syntax: 'Create a study plan for [subject] over [timeframe]',
        example: 'Create a study plan for calculus over 4 weeks',
        description: 'ATLAS will generate a structured week-by-week learning roadmap tailored to your goal.',
        parameters: [
          { name: 'subject', description: 'Topic or course you want to study.' },
          { name: 'timeframe', description: 'Number of days, weeks, or months available.' },
        ],
        output: 'A week-by-week or day-by-day plan with milestones, recommended resources, and checkpoints.',
        guardrails: 'Plans are suggestions only. ATLAS will not make curriculum decisions for accredited programs.',
        tips: 'Include your current skill level for a better-calibrated plan. "I know basic algebra already" helps.',
      },
      {
        name: 'Quiz me on a topic',
        syntax: 'Quiz me on [topic] — [easy/medium/hard]',
        example: 'Quiz me on the American Civil War — medium',
        description: 'ATLAS generates quiz questions at your chosen difficulty and gives feedback on your answers.',
        parameters: [
          { name: 'topic', description: 'The subject you want to be tested on.' },
          { name: 'difficulty', description: 'easy, medium, or hard.' },
        ],
        output: 'A set of questions, answer feedback, and a final score summary.',
        guardrails: 'Quiz content is AI-generated and may not match specific exam formats. Treat as practice, not official prep.',
        tips: 'After each answer, ask ATLAS to explain why you got it wrong for reinforced learning.',
      },
      {
        name: 'Summarize a lesson',
        syntax: 'Summarize [lesson title or paste text]',
        example: 'Summarize: [paste your notes here]',
        description: 'ATLAS condenses your notes or a lesson into key takeaways and bullet-point summaries.',
        parameters: [
          { name: 'lesson content', description: 'Paste the text or name the lesson title.' },
        ],
        output: 'A bulleted key-point summary, main concepts, and a one-sentence overview.',
        guardrails: 'Works best with under 2,000 words of input. Very long texts may be summarized in sections.',
        tips: 'Ask ATLAS to "summarize this for a 5th grader" or "summarize like a textbook" for different styles.',
      },
      {
        name: 'Explain like I\'m a beginner',
        syntax: 'Explain [topic] like I\'m a beginner',
        example: 'Explain machine learning like I\'m a beginner',
        description: 'Forces ATLAS into simple language mode — no jargon, pure fundamentals.',
        parameters: [
          { name: 'topic', description: 'The concept you want broken down simply.' },
        ],
        output: 'A plain-language explanation with analogies and no assumed prior knowledge.',
        guardrails: 'Simplified explanations may omit advanced edge cases. ATLAS will note when depth is being reduced.',
        tips: 'You can also say "explain it like I\'m 10" or "like I just started learning today".',
      },
      {
        name: 'Compare two concepts',
        syntax: 'Compare [concept A] and [concept B]',
        example: 'Compare supervised and unsupervised learning',
        description: 'ATLAS generates a side-by-side breakdown of similarities, differences, and when to use each.',
        parameters: [
          { name: 'concept A', description: 'First topic for comparison.' },
          { name: 'concept B', description: 'Second topic for comparison.' },
        ],
        output: 'A comparison table or structured breakdown with pros/cons and use-case guidance.',
        guardrails: 'Comparisons are general. Domain-specific edge cases may require professional verification.',
        tips: 'Great for choosing between two frameworks, methods, or historical events.',
      },
    ],
  },
  {
    category: 'Research & Reports',
    icon: Microscope,
    accent: 'var(--cyan)',
    description: 'Use ATLAS to conduct research and generate structured reports.',
    commands: [
      {
        name: 'Start a research project',
        syntax: 'Research [topic] and summarize what you find',
        example: 'Research climate change solutions and summarize what you find',
        description: 'ATLAS gathers and synthesizes knowledge on your topic into an organized research summary.',
        parameters: [
          { name: 'topic', description: 'The subject or question you want researched.' },
        ],
        output: 'An organized research summary with key findings, context, and topic sections.',
        guardrails: 'By default this is model-guided synthesis. For live sources, use the /research or /web commands in the Internet Access section below.',
        tips: 'For deeper results, ask ATLAS to "break the research into sub-topics" first, then run /research on the highest-priority sub-topic.',
      },
      {
        name: 'Generate a report outline',
        syntax: 'Create an outline for a report on [topic]',
        example: 'Create an outline for a report on the history of the internet',
        description: 'ATLAS drafts a structured report outline with sections, sub-sections, and suggested talking points.',
        parameters: [
          { name: 'topic', description: 'The subject your report covers.' },
        ],
        output: 'A hierarchical report outline ready to fill in with research.',
        guardrails: 'Outlines are starting frameworks. Review and adapt before using for official assignments.',
        tips: 'Specify length or audience: "for a 10-page college paper" or "for a 5-minute presentation".',
      },
      {
        name: 'Draft a research question',
        syntax: 'Help me write a research question about [broad topic]',
        example: 'Help me write a research question about social media and mental health',
        description: 'ATLAS helps you refine a vague area of interest into a focused, answerable research question.',
        parameters: [
          { name: 'broad topic', description: 'A general area or theme you\'re exploring.' },
        ],
        output: 'Three to five focused research question options with brief rationale for each.',
        guardrails: 'Research questions are suggestions. Academic validity depends on your institution\'s guidelines.',
        tips: 'Tell ATLAS your level (high school, college, professional) for better calibration.',
      },
    ],
  },
  {
    category: 'Internet Access (Live Web)',
    icon: Globe,
    accent: 'var(--photon)',
    description: 'Use slash commands for current-source retrieval and web-grounded summaries.',
    commands: [
      {
        name: 'Run live internet research',
        syntax: '/research [query]',
        example: '/research deepseek flash v4 release notes',
        description: 'Runs a web research pass and returns a concise brief with evidence-oriented context.',
        parameters: [
          { name: 'query', description: 'The research topic, question, or target source domain.' },
        ],
        output: 'A source-aware summary with key findings and practical takeaways.',
        guardrails: 'Web sources can be wrong, stale, or biased. Verify critical claims with primary documentation before taking action.',
        tips: 'Add scope like "official docs", "release notes", or a domain name to reduce noisy results.',
      },
      {
        name: 'Fetch and summarize one URL',
        syntax: '/web [url]',
        example: '/web https://docs.python.org/3/whatsnew/3.12.html',
        description: 'Fetches a specific public URL and returns an extracted summary for quick review.',
        parameters: [
          { name: 'url', description: 'A public page URL you want ATLAS to parse and summarize.' },
        ],
        output: 'Cleaned page summary with the most relevant points for your current task.',
        guardrails: 'Some sites block automated fetches or require login; those pages can fail or return partial content.',
        tips: 'Best for documentation pages when you already trust the source and want faster extraction.',
      },
    ],
  },
  {
    category: 'Document Creation',
    icon: FileText,
    accent: 'var(--photon)',
    description: 'Generate structured documents, essays, and written content with ATLAS. (Full automation coming soon — currently in guided draft mode.)',
    commands: [
      {
        name: 'Draft an essay',
        syntax: 'Write a [length] essay on [topic] from the perspective of [angle]',
        example: 'Write a 3-paragraph essay on renewable energy from an economic perspective',
        description: 'ATLAS drafts a structured essay with an introduction, body paragraphs, and conclusion.',
        parameters: [
          { name: 'length', description: 'Paragraph count, word count, or descriptive length (short/medium/long).' },
          { name: 'topic', description: 'The subject of the essay.' },
          { name: 'angle', description: 'Optional perspective or argument lens.' },
        ],
        output: 'A full essay draft with intro, body, and conclusion.',
        guardrails: 'AI-generated essays are drafts only. Review for accuracy, citation, and academic integrity before submission.',
        tips: 'Ask ATLAS to "list key arguments first" before writing to review the direction.',
      },
      {
        name: 'Write a professional email',
        syntax: 'Write a professional email to [recipient/role] about [subject]',
        example: 'Write a professional email to my professor about requesting an extension',
        description: 'ATLAS drafts a clear, appropriately toned email for professional or academic communication.',
        parameters: [
          { name: 'recipient', description: 'Who the email is addressed to.' },
          { name: 'subject', description: 'What the email is about.' },
        ],
        output: 'A complete email with subject line, greeting, body, and closing.',
        guardrails: 'Review before sending. Personalize any placeholders ATLAS leaves in the draft.',
        tips: 'Add context like "I missed last Tuesday\'s class" for a more accurate draft.',
      },
      {
        name: 'Create a structured notes template',
        syntax: 'Create a notes template for [subject or lecture type]',
        example: 'Create a notes template for a science lecture with diagrams',
        description: 'ATLAS generates a reusable structured template for capturing notes during lectures or reading.',
        parameters: [
          { name: 'subject', description: 'The subject or type of content being captured.' },
        ],
        output: 'A fillable notes template with labeled sections and guidance prompts.',
        guardrails: 'Templates are general frameworks. Adjust section names to match your course format.',
        tips: 'Great for Cornell notes, lecture notes, or reading response templates.',
      },
    ],
  },
  {
    category: 'Study Tools',
    icon: Zap,
    accent: 'var(--ember)',
    description: 'Active recall, flashcards, and memory tools powered by ATLAS.',
    commands: [
      {
        name: 'Generate flashcards',
        syntax: 'Create flashcards for [topic or paste your notes]',
        example: 'Create flashcards for the periodic table elements 1–20',
        description: 'ATLAS generates Q&A-style flashcard pairs ready for active recall practice.',
        parameters: [
          { name: 'topic or notes', description: 'Topic name or pasted content to generate cards from.' },
        ],
        output: 'A numbered list of question/answer pairs formatted for study.',
        guardrails: 'Flashcard content reflects ATLAS\'s training knowledge. Verify against your course materials.',
        tips: 'After reviewing, ask ATLAS to "quiz me on these flashcards" to test yourself.',
      },
      {
        name: 'Explain why I got something wrong',
        syntax: 'I answered [your answer] to [question] — why is the correct answer [correct answer]?',
        example: 'I answered "mitosis" to what cell division produces gametes — why is meiosis correct?',
        description: 'ATLAS explains the reasoning behind the correct answer and what mistake led to the wrong one.',
        parameters: [
          { name: 'your answer', description: 'What you said or thought.' },
          { name: 'question', description: 'The original question.' },
          { name: 'correct answer', description: 'The right answer you want to understand.' },
        ],
        output: 'An explanation of the correct answer, why it\'s right, and what the confusion was.',
        guardrails: 'Best used for conceptual understanding, not substituting for teacher feedback on graded work.',
        tips: 'Follow up with "can you give me a similar example to practice?" to reinforce the concept.',
      },
      {
        name: 'Set a learning goal',
        syntax: 'I want to learn [skill/topic] by [date or timeframe]. Help me set a goal.',
        example: 'I want to learn Python basics by the end of the month. Help me set a goal.',
        description: 'ATLAS helps you define a clear, achievable learning goal with milestones and checkpoints.',
        parameters: [
          { name: 'skill/topic', description: 'What you want to learn.' },
          { name: 'timeframe', description: 'Your target completion date or window.' },
        ],
        output: 'A SMART learning goal statement plus a milestone breakdown.',
        guardrails: 'Goals are suggestions and not tracked automatically yet. Manual check-ins are recommended.',
        tips: 'Come back to ATLAS periodically and say "check in on my Python goal" to review progress.',
      },
    ],
  },
  {
    category: 'File & Project Organization',
    icon: FolderOpen,
    accent: 'var(--amber)',
    description: 'Commands for organizing your learning materials. Full automation coming in a future update.',
    commands: [
      {
        name: 'Organize my notes by topic',
        syntax: 'Help me organize these notes into topics: [paste notes]',
        example: 'Help me organize these notes into topics: [paste your messy notes]',
        description: 'ATLAS reads your notes and suggests a logical grouping and folder structure.',
        parameters: [
          { name: 'notes', description: 'Your raw or unorganized notes pasted into the chat.' },
        ],
        output: 'A suggested topic breakdown with each note sorted into a category.',
        guardrails: 'ATLAS organizes conceptually — actual file creation requires manual steps until automation ships.',
        tips: 'Paste lecture notes, reading summaries, or study materials directly into the chat.',
        badge: 'Guided (manual steps for now)',
      },
      {
        name: 'Create a project plan',
        syntax: 'Create a project plan for [project name] due [date] with [team size or solo]',
        example: 'Create a project plan for my history research paper due in 2 weeks, solo',
        description: 'ATLAS drafts a task breakdown, timeline, and checklist for a learning project or assignment.',
        parameters: [
          { name: 'project name', description: 'What the project or assignment is called.' },
          { name: 'due date', description: 'When it\'s due.' },
          { name: 'team size', description: 'Solo or group size if relevant.' },
        ],
        output: 'A project plan with tasks, owner assignments, and a timeline.',
        guardrails: 'Plans are frameworks. Actual task management requires your own tracking tools for now.',
        tips: 'Say "break each task into sub-steps" for a more detailed execution plan.',
        badge: 'Guided (manual steps for now)',
      },
    ],
  },
  {
    category: 'Calendar & Events',
    icon: Calendar,
    accent: 'var(--cyan)',
    description: 'Add quizzes, study sessions, and reminders to your calendar. Full calendar integration coming soon.',
    commands: [
      {
        name: 'Schedule a study session',
        syntax: 'Schedule a [duration] study session on [topic] for [date/time]',
        example: 'Schedule a 2-hour study session on organic chemistry for Friday at 6pm',
        description: 'ATLAS will help you format a calendar entry for your study session. (Automated calendar sync coming soon.)',
        parameters: [
          { name: 'duration', description: 'How long the session should be.' },
          { name: 'topic', description: 'What you\'re studying.' },
          { name: 'date/time', description: 'When to schedule it.' },
        ],
        output: 'A calendar-ready event description you can add to Google Calendar, Outlook, or another tool.',
        guardrails: 'Calendar integration is not yet automated. You\'ll need to manually add the event.',
        tips: 'Ask ATLAS to "suggest the best times to study this week" for a full schedule recommendation.',
        badge: 'Coming soon: auto-calendar',
      },
      {
        name: 'Add a quiz deadline',
        syntax: 'Add a quiz on [topic] for [date] to my schedule',
        example: 'Add a quiz on the Civil War for next Monday to my schedule',
        description: 'ATLAS formats a reminder or calendar event for an upcoming quiz or test.',
        parameters: [
          { name: 'topic', description: 'The quiz subject.' },
          { name: 'date', description: 'When the quiz is.' },
        ],
        output: 'A formatted calendar entry and a brief reminder note to place in your planner.',
        guardrails: 'No automated calendar sync yet. Copy the event details to your preferred calendar app.',
        tips: 'Pair this with "create a 3-day study plan leading up to my quiz" for best results.',
        badge: 'Coming soon: auto-calendar',
      },
    ],
  },
  {
    category: 'Accuracy Guardrails Explained',
    icon: Shield,
    accent: 'var(--amber)',
    description: 'How ATLAS keeps its answers honest and what to do when you\'re not sure about a response.',
    commands: [
      {
        name: 'What ATLAS will always do',
        syntax: '(Built-in behavior — no command needed)',
        example: '',
        description: 'ATLAS is designed to be honest about uncertainty. It will flag when it\'s unsure, avoid making up facts, and remind you to verify critical information.',
        parameters: [],
        output: 'Transparent, labeled answers with confidence cues.',
        guardrails: 'ATLAS never claims certainty it doesn\'t have. Watch for phrases like "I\'m not sure but..." or "please verify this."',
        tips: 'If ATLAS hedges, that\'s a feature not a bug — it means double-check with a trusted source.',
      },
      {
        name: 'What ATLAS will not do',
        syntax: '(Permanent restrictions)',
        example: '',
        description: 'ATLAS will not generate harmful content, write malicious code, impersonate real people, bypass ethical guardrails, or make promises about exam results.',
        parameters: [],
        output: 'A respectful refusal with a brief explanation and an alternative suggestion if possible.',
        guardrails: 'These restrictions are not adjustable by the user. They are platform-level safety rules.',
        tips: 'If ATLAS refuses a request, try rephrasing it as a learning question instead of a task request.',
      },
      {
        name: 'How to get better answers',
        syntax: '(Prompt tips)',
        example: '',
        description: 'The more context you give ATLAS, the better its response. Include your level, the subject, what you already know, and what kind of output you want.',
        parameters: [
          { name: 'context', description: 'Your skill level, the subject, and what you already know.' },
          { name: 'format preference', description: 'Say "in bullet points", "as a table", or "in plain language".' },
          { name: 'scope', description: 'Say "keep it short" or "go deep" to control detail.' },
        ],
        output: 'Higher accuracy, more useful, and better-formatted responses.',
        guardrails: 'Context improves answer quality but does not guarantee factual correctness. For current events, use /research or /web and verify sources.',
        tips: 'Start your message with "I\'m a [level] student studying [subject] and I want to [goal]" for best results.',
      },
    ],
  },
]

const BADGE_STYLE = {
  padding: '2px 8px',
  borderRadius: 999,
  fontSize: '0.65rem',
  fontWeight: 700,
  background: 'rgba(255,165,0,0.12)',
  border: '1px solid rgba(255,165,0,0.3)',
  color: 'var(--amber)',
  whiteSpace: 'nowrap',
}

function CommandCard({ cmd }) {
  const [expanded, setExpanded] = useState(false)
  return (
    <div
      style={{
        background: 'rgba(255,255,255,0.03)',
        border: '1px solid rgba(255,255,255,0.07)',
        borderRadius: 12,
        overflow: 'hidden',
        marginBottom: 10,
      }}
    >
      <button
        onClick={() => setExpanded(e => !e)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'flex-start',
          gap: 12,
          padding: '14px 16px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        <span style={{ marginTop: 2, color: 'var(--txt-mut)', flexShrink: 0 }}>
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            <span style={{ fontSize: '0.9rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{cmd.name}</span>
            {cmd.badge && <span style={BADGE_STYLE}>{cmd.badge}</span>}
          </div>
          <code style={{
            display: 'block',
            fontSize: '0.75rem',
            color: 'var(--cyan)',
            background: 'rgba(0,0,0,0.3)',
            padding: '4px 8px',
            borderRadius: 6,
            fontFamily: 'monospace',
            marginBottom: cmd.example ? 6 : 0,
            wordBreak: 'break-word',
          }}>
            {cmd.syntax}
          </code>
          {cmd.example && (
            <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--txt-mut)', fontStyle: 'italic' }}>
              e.g. &ldquo;{cmd.example}&rdquo;
            </p>
          )}
        </div>
      </button>

      {expanded && (
        <div style={{ padding: '0 16px 16px 42px', display: 'flex', flexDirection: 'column', gap: 12 }}>
          <p style={{ margin: 0, fontSize: '0.83rem', color: 'var(--txt-sec)', lineHeight: 1.65 }}>
            {cmd.description}
          </p>

          {cmd.parameters && cmd.parameters.length > 0 && (
            <div>
              <p style={{ margin: '0 0 6px', fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--txt-mut)' }}>Parameters</p>
              {cmd.parameters.map(p => (
                <div key={p.name} style={{ display: 'flex', gap: 8, marginBottom: 4, fontSize: '0.8rem' }}>
                  <code style={{ color: 'var(--violet)', fontFamily: 'monospace', flexShrink: 0 }}>[{p.name}]</code>
                  <span style={{ color: 'var(--txt-sec)' }}>{p.description}</span>
                </div>
              ))}
            </div>
          )}

          <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))' }}>
            <div style={{ background: 'rgba(0,200,100,0.06)', border: '1px solid rgba(0,200,100,0.15)', borderRadius: 8, padding: '10px 12px' }}>
              <p style={{ margin: '0 0 4px', fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: '#4ade80' }}>Expected Output</p>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.55 }}>{cmd.output}</p>
            </div>
            <div style={{ background: 'rgba(248,200,60,0.06)', border: '1px solid rgba(248,200,60,0.15)', borderRadius: 8, padding: '10px 12px' }}>
              <p style={{ margin: '0 0 4px', fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--amber)' }}>Guardrails</p>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.55 }}>{cmd.guardrails}</p>
            </div>
          </div>

          {cmd.tips && (
            <div style={{ background: 'rgba(180,124,255,0.06)', border: '1px solid rgba(180,124,255,0.15)', borderRadius: 8, padding: '10px 12px' }}>
              <p style={{ margin: '0 0 4px', fontSize: '0.65rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', color: 'var(--violet)' }}>💡 Pro Tip</p>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--txt-sec)', lineHeight: 1.55 }}>{cmd.tips}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default function CommandLibraryPage() {
  const [search, setSearch] = useState('')
  const [openCategory, setOpenCategory] = useState(null)

  const query = search.trim().toLowerCase()
  const filtered = COMMANDS.map(cat => ({
    ...cat,
    commands: cat.commands.filter(cmd =>
      !query ||
      cmd.name.toLowerCase().includes(query) ||
      cmd.description.toLowerCase().includes(query) ||
      cmd.syntax.toLowerCase().includes(query) ||
      (cmd.example || '').toLowerCase().includes(query)
    ),
  })).filter(cat => !query || cat.commands.length > 0)

  return (
    <div style={{ padding: '28px 20px 80px', maxWidth: 900, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <BookOpen size={22} color="var(--violet)" />
          <h1 style={{ margin: 0, fontSize: '1.7rem', fontWeight: 800, color: 'var(--txt-pri)' }}>Command Library</h1>
        </div>
        <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--txt-sec)', lineHeight: 1.6, maxWidth: 620 }}>
          A full reference for ATLAS prompts, slash commands, and workflow features. Click any command to see syntax, parameters, expected output, and guardrails.
        </p>
      </div>

      {/* Search */}
      <div style={{ position: 'relative', marginBottom: 24 }}>
        <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--txt-mut)' }} />
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search commands, topics, or syntax..."
          style={{
            width: '100%',
            padding: '10px 12px 10px 36px',
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.1)',
            borderRadius: 10,
            color: 'var(--txt-pri)',
            fontSize: '0.88rem',
            outline: 'none',
            boxSizing: 'border-box',
          }}
        />
      </div>

      {/* Categories */}
      {filtered.map(cat => {
        const Icon = cat.icon
        const isOpen = openCategory === cat.category || Boolean(query)
        return (
          <div key={cat.category} style={{ marginBottom: 20 }}>
            <button
              onClick={() => setOpenCategory(isOpen && !query ? null : cat.category)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: '14px 16px',
                background: 'rgba(255,255,255,0.03)',
                border: `1px solid ${isOpen ? cat.accent : 'rgba(255,255,255,0.07)'}`,
                borderRadius: isOpen ? '12px 12px 0 0' : 12,
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'border-color 0.15s',
              }}
            >
              <Icon size={16} color={cat.accent} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{cat.category}</p>
                <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--txt-mut)' }}>{cat.description}</p>
              </div>
              <span style={{ fontSize: '0.7rem', color: 'var(--txt-mut)', flexShrink: 0 }}>
                {cat.commands.length} {cat.commands.length === 1 ? 'command' : 'commands'}
              </span>
              <span style={{ color: 'var(--txt-mut)', flexShrink: 0 }}>
                {isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              </span>
            </button>
            {isOpen && (
              <div style={{ border: `1px solid ${cat.accent}`, borderTop: 'none', borderRadius: '0 0 12px 12px', padding: '12px 12px 4px', background: 'rgba(255,255,255,0.01)' }}>
                {cat.commands.map(cmd => (
                  <CommandCard key={cmd.name} cmd={cmd} />
                ))}
              </div>
            )}
          </div>
        )
      })}

      {filtered.length === 0 && (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--txt-mut)', fontSize: '0.88rem' }}>
          No commands found for &ldquo;{search}&rdquo;. Try a different keyword.
        </div>
      )}
    </div>
  )
}
