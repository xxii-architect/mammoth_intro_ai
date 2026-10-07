/**
 * AgentThinkingIndicator
 * Shows which specific agent is active with its color, icon, and context label.
 * Used in ChatPage while waiting for a response.
 */
import { MessageSquare, Wrench, Brain, Terminal, Bot, Cpu } from 'lucide-react'

const AGENT_PRESENCE = {
  assistant: {
    label: 'Mammoth Assistant',
    verb: 'composing a response',
    Icon: MessageSquare,
  },
  coding_agent: {
    label: 'Coding Agent',
    verb: 'reading the codebase',
    Icon: Wrench,
  },
  reasoning_agent: {
    label: 'Reasoning Agent',
    verb: 'building a chain of thought',
    Icon: Brain,
  },
  shell_agent: {
    label: 'Shell Agent',
    verb: 'preparing a command plan',
    Icon: Terminal,
  },
  mammoth_guide: {
    label: 'MammothOS Guide',
    verb: 'scanning architecture context',
    Icon: Bot,
  },
}

const STREAM_VERBS = {
  patching: 'patching your files',
  reasoning: 'reasoning through the problem',
  thinking: 'processing your request',
  idle: 'working',
}

export default function AgentThinkingIndicator({ agentId, streamStatus, streaming }) {
  const presence = AGENT_PRESENCE[agentId] || {
    label: agentId ? agentId.replace(/_/g, ' ') : 'MammothOS',
    verb: 'working',
    Icon: Cpu,
  }
  const { label, Icon } = presence
  const color = 'var(--mm-color-agent-default)'
  const verb = STREAM_VERBS[streamStatus] || presence.verb

  return (
    <div
      style={{
        alignSelf: 'flex-start',
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 14px',
        borderRadius: 12,
        background: 'var(--mm-color-agent-soft)',
        border: '1px solid rgba(var(--mm-color-agent-rgb),0.25)',
        maxWidth: 340,
      }}
    >
      {/* Pulsing icon */}
      <div style={{ position: 'relative', flexShrink: 0, display: 'flex', alignItems: 'center' }}>
        <Icon size={16} color={color} />
      </div>

      {/* Text */}
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: '0.7rem', fontWeight: 700, color, letterSpacing: '0.04em', marginBottom: 1 }}>
          {label}
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
          {streaming ? verb : 'checking the herd…'}
          <span style={{ display: 'inline-flex', gap: 2, marginLeft: 4 }}>
            {[0, 1, 2].map(i => (
              <span
                key={i}
                style={{
                  display: 'inline-block', width: 3, height: 3,
                  borderRadius: '50%', background: 'var(--txt-mut)',
                  animation: `thinking-dot 1.2s ease-in-out ${i * 0.2}s infinite`,
                }}
              />
            ))}
          </span>
        </div>
      </div>
    </div>
  )
}
