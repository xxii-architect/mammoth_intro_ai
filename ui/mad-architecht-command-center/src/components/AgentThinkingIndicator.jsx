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
    color: 'var(--photon)',
    bg: 'rgba(77,166,255,0.08)',
    border: 'rgba(77,166,255,0.2)',
    glow: 'rgba(77,166,255,0.5)',
  },
  coding_agent: {
    label: 'Coding Agent',
    verb: 'reading the codebase',
    Icon: Wrench,
    color: 'var(--cyan)',
    bg: 'rgba(0,212,255,0.07)',
    border: 'rgba(0,212,255,0.22)',
    glow: 'rgba(0,212,255,0.5)',
  },
  reasoning_agent: {
    label: 'Reasoning Agent',
    verb: 'building a chain of thought',
    Icon: Brain,
    color: 'var(--violet)',
    bg: 'rgba(180,124,255,0.08)',
    border: 'rgba(180,124,255,0.25)',
    glow: 'rgba(180,124,255,0.5)',
  },
  shell_agent: {
    label: 'Shell Agent',
    verb: 'preparing a command plan',
    Icon: Terminal,
    color: '#22c55e',
    bg: 'rgba(34,197,94,0.07)',
    border: 'rgba(34,197,94,0.22)',
    glow: 'rgba(34,197,94,0.45)',
  },
  mammoth_guide: {
    label: 'MammothOS Guide',
    verb: 'scanning architecture context',
    Icon: Bot,
    color: 'var(--amber, #f59e0b)',
    bg: 'rgba(245,158,11,0.07)',
    border: 'rgba(245,158,11,0.22)',
    glow: 'rgba(245,158,11,0.45)',
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
    color: 'var(--txt-sec)',
    bg: 'rgba(255,255,255,0.04)',
    border: 'rgba(255,255,255,0.1)',
    glow: 'rgba(255,255,255,0.2)',
  }
  const { label, Icon, color, bg, border, glow } = presence
  const verb = STREAM_VERBS[streamStatus] || presence.verb

  return (
    <div
      style={{
        alignSelf: 'flex-start',
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 14px',
        borderRadius: 12,
        background: bg,
        border: `1px solid ${border}`,
        maxWidth: 340,
      }}
    >
      {/* Pulsing icon */}
      <div style={{ position: 'relative', flexShrink: 0, display: 'flex', alignItems: 'center' }}>
        <Icon size={16} color={color} />
        <span
          style={{
            position: 'absolute', inset: -5, borderRadius: '50%',
            background: `radial-gradient(circle, ${glow} 0%, transparent 70%)`,
            animation: 'pulse-violet 2s ease-in-out infinite',
            pointerEvents: 'none',
          }}
        />
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
