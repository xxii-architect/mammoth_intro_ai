/**
 * MammothEmpty — branded empty states for the Agent Console.
 *
 * Each context has a glyph, a headline, and a subtle hint line.
 * All copy is intentionally voice-consistent with MammothOS.
 */

const STATES = {
  output: {
    glyph: '🦣',
    headline: 'The mammoth is ready.',
    hint: 'Run an agent or Plan + Execute to see output here.',
  },
  agent_silent: {
    glyph: '📡',
    headline: 'Agent responded — but said nothing.',
    hint: 'The agent ran cleanly with no structured output. Check the Raw JSON toggle or adjust your prompt.',
  },
  plan_steps: {
    glyph: '🗺️',
    headline: 'No steps in the plan yet.',
    hint: 'The planner is working — steps appear here as they execute.',
  },
  plan_idle: {
    glyph: '🦴',
    headline: 'No plan has been run.',
    hint: 'Switch Mode to Plan + Execute and give the herd an objective.',
  },
  smoke_test: {
    glyph: '🧪',
    headline: 'No smoke test data.',
    hint: 'Hit "Run Smoke Test" to ping all agents and spot gaps.',
  },
  tasks: {
    glyph: '📋',
    headline: 'The task queue is clear.',
    hint: 'Nothing in the queue — all quiet on the tundra.',
  },
  approvals: {
    glyph: '✅',
    headline: 'No pending approvals.',
    hint: 'Agents are running autonomously. Pending actions will appear here.',
  },
  snapshots: {
    glyph: '📸',
    headline: 'No rollback snapshots yet.',
    hint: 'Snapshots are captured automatically when files are modified.',
  },
  activity: {
    glyph: '🌡️',
    headline: 'No activity recorded.',
    hint: 'Agent events and system signals will stream here in real time.',
  },
  history: {
    glyph: '🕰️',
    headline: 'Run history is empty.',
    hint: 'Each agent run is logged here so you can replay or audit it.',
  },
  autonomous: {
    glyph: '🤖',
    headline: 'No autonomous runs recorded.',
    hint: 'Orchestrated multi-agent runs will show up here after Plan + Execute.',
  },
  step_output: {
    glyph: '🔇',
    headline: 'This step produced no output.',
    hint: 'The agent completed without returning a summary. Try expanding Raw JSON.',
  },
  default: {
    glyph: '🦣',
    headline: 'Nothing from the herd.',
    hint: 'No data yet for this section.',
  },
}

export default function MammothEmpty({
  context = 'default',
  compact = false,
  hint,        // override hint text
  headline,    // override headline
}) {
  const cfg = STATES[context] || STATES.default
  const displayHint = hint ?? cfg.hint
  const displayHeadline = headline ?? cfg.headline

  if (compact) {
    return (
      <div style={{
        display: 'flex', alignItems: 'center', gap: 8,
        padding: '6px 0', color: 'var(--txt-mut)', fontSize: '0.73rem',
      }}>
        <span style={{ fontSize: '1rem', lineHeight: 1 }}>{cfg.glyph}</span>
        <span style={{ fontStyle: 'italic' }}>{displayHeadline}</span>
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      justifyContent: 'center', padding: '24px 16px', textAlign: 'center',
      gap: 8,
    }}>
      <span style={{ fontSize: '2rem', lineHeight: 1, marginBottom: 4 }}>{cfg.glyph}</span>
      <span style={{ fontSize: '0.85rem', color: 'var(--txt-sec)', fontWeight: 600 }}>
        {displayHeadline}
      </span>
      {displayHint && (
        <span style={{
          fontSize: '0.72rem', color: 'var(--txt-mut)',
          lineHeight: 1.55, maxWidth: 280,
        }}>
          {displayHint}
        </span>
      )}
    </div>
  )
}
