// Plain-language catalog for the Agent Workspace. Backend intents stay unchanged;
// each task chip just picks the intent the agent already understands.

export const AGENT_CATALOG = [
  {
    id: 'research_agent',
    name: 'Research',
    handle: 'research',
    blurb: 'Digs into a topic and returns findings with sources.',
    tasks: [
      { label: 'Research a topic', intent: 'research_curriculum', placeholder: 'What do you want researched?' },
      { label: 'Compare options', intent: 'compare_gear', placeholder: 'Compare A vs B for… (what matters most?)' },
      { label: 'Deep-dive report', intent: 'research_long_form', placeholder: 'Topic for a long-form report with sections…' },
      { label: 'Survival & field skills', intent: 'research_survival', placeholder: 'Which skill or scenario?' },
      { label: 'Plants & foraging', intent: 'research_plants', placeholder: 'Which plant, region, or season?' },
      { label: 'Summarize', intent: 'summarize', placeholder: 'Paste text or describe what to summarize…' },
    ],
  },
  {
    id: 'plant_the_seed_agent',
    name: 'Idea Shaper',
    handle: 'seed',
    blurb: 'Turns a rough idea into a hypothesis, risks, and how to test it.',
    tasks: [{ label: 'Shape an idea', intent: 'plant_seed', placeholder: 'Describe the idea in a sentence or two…' }],
  },
  {
    id: 'reflection_agent',
    name: 'Reflection',
    handle: 'reflection',
    blurb: 'Pressure-tests a plan: blind spots, risks, what “done” looks like.',
    tasks: [{ label: 'Pressure-test a plan', intent: 'reflection', placeholder: 'What plan or decision should be challenged?' }],
  },
  {
    id: 'coding_agent',
    name: 'Coding',
    handle: 'coding',
    blurb: 'Writes, patches, reviews, and documents code with preview-first edits.',
    tasks: [
      { label: 'Write code', intent: 'generate_code', placeholder: 'What should be built? Name files if you know them.' },
      { label: 'Patch files', intent: 'patch_existing', placeholder: 'Which file(s), and what should change?' },
      { label: 'Refactor', intent: 'refactor_code', placeholder: 'What should be cleaned up, and what must not change?' },
      { label: 'Review code', intent: 'analyze_codebase', placeholder: 'Which area should be reviewed for risks?' },
      { label: 'Test plan', intent: 'run_tests', placeholder: 'What change needs a validation plan?' },
      { label: 'Write docs', intent: 'write_docs', placeholder: 'What should be documented, and for whom?' },
    ],
  },
  {
    id: 'market_intel_agent',
    name: 'Market Intel',
    handle: 'market',
    blurb: 'Audience, trends, and opportunities for a product or idea.',
    tasks: [{ label: 'Size up a market', intent: 'market_intel', placeholder: 'Which product, audience, or niche?' }],
  },
  {
    id: 'field_ops_agent',
    name: 'Field Ops',
    handle: 'fieldops',
    blurb: 'Practical checklists and step-by-step operating plans.',
    tasks: [{ label: 'Build a checklist', intent: 'field_ops', placeholder: 'What mission, trip, or rollout?' }],
  },
  {
    id: 'brand_voice_agent',
    name: 'Brand Voice',
    handle: 'brand',
    blurb: 'Rewrites copy in the True XXII voice: captions, taglines, summaries.',
    tasks: [{ label: 'Rewrite copy', intent: 'brand_voice', placeholder: 'Paste the copy, or describe what to write…' }],
  },
  {
    id: 'browser_agent',
    name: 'Browser',
    handle: 'browser',
    blurb: 'Opens a web page and reports what is on it.',
    tasks: [{ label: 'Read a web page', intent: 'browse_web', placeholder: 'https://… and what to look for' }],
  },
  {
    id: 'tutor_agent',
    name: 'Tutor',
    handle: 'tutor',
    blurb: 'Coaching checkpoints and feedback on submitted work.',
    tasks: [
      { label: 'Coach me', intent: 'lesson_coaching', placeholder: 'What are you learning right now?' },
      { label: 'Grade my work', intent: 'grade_submission', placeholder: 'Paste the work and what it was for…' },
    ],
  },
  {
    id: 'curriculum_agent',
    name: 'Curriculum',
    handle: 'curriculum',
    blurb: 'Frames a lesson or learning path for a topic.',
    tasks: [{ label: 'Frame a lesson', intent: 'lesson_curriculum', placeholder: 'Which topic and learner level?' }],
  },
]

export const CATALOG_BY_ID = Object.fromEntries(AGENT_CATALOG.map(entry => [entry.id, entry]))
export const CATALOG_BY_HANDLE = Object.fromEntries(AGENT_CATALOG.map(entry => [entry.handle, entry]))

export const TEAM_FITS = [
  { value: 'balanced', label: 'Auto-fit', hint: 'Only the agents your objective calls for' },
  { value: 'atlas', label: 'Business', hint: 'Adds market framing and an ops checklist' },
  { value: 'coding', label: 'Build', hint: 'Adds an implementation pass by the Coding agent' },
  { value: 'coding_only', label: 'Code only', hint: 'Just the Coding agent' },
  { value: 'autonomous', label: 'Autonomous prep', hint: 'Adds community update and maintenance checks' },
]

export function agentDisplay(agentId, registryAgent) {
  const entry = CATALOG_BY_ID[agentId]
  if (entry) return entry
  const raw = registryAgent?.name || agentId || 'Agent'
  const name = raw.replace(/_agent$/i, '').replace(/Agent$/, '').replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2').trim()
  return {
    id: agentId,
    name: name.charAt(0).toUpperCase() + name.slice(1),
    handle: String(agentId || '').replace(/_agent$/, ''),
    blurb: (registryAgent?.capabilities || []).join(', ').replace(/_/g, ' ') || 'Registered agent',
    tasks: [],
  }
}

export function agentStatusLabel(status, busy) {
  if (busy) return { label: 'Working', color: 'var(--mm-color-agent-default, #d08a52)' }
  const value = String(status || '').toUpperCase()
  if (value === 'ACTIVE' || value === 'IDLE' || value === 'READY') return { label: 'Ready', color: 'var(--mm-color-status-success, #34d399)' }
  if (value === 'ERROR' || value === 'FAILED' || value === 'OFFLINE') return { label: 'Offline', color: 'var(--mm-color-status-danger, #f87171)' }
  return { label: value ? value.toLowerCase() : 'unknown', color: 'var(--txt-mut)' }
}

// Leading "@handle" routes one message to another agent.
export function parseMention(text) {
  const match = /^@([a-z_]+)\s+([\s\S]+)$/i.exec(String(text || '').trim())
  if (!match) return null
  const entry = CATALOG_BY_HANDLE[match[1].toLowerCase()]
  return entry ? { agent: entry, text: match[2].trim() } : null
}
