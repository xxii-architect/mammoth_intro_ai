import { useState, useEffect, useRef } from 'react'
import { Terminal, Play, Copy, Trash2, GitBranch, Hammer, Bot, FlaskConical, CheckCircle, WifiOff, BookOpen } from 'lucide-react'
import { openTerminalWS } from '../api/client'
import OnboardingGuide from '../components/OnboardingGuide'

const QUICK_ACTIONS = [
  { label: 'Git Status',    cmd: 'git status',                   Icon: GitBranch,   color: 'var(--violet)' },
  { label: 'Agent List',    cmd: 'python -m cli.main agent-list', Icon: Bot,         color: 'var(--photon)' },
  { label: 'CLI Status',    cmd: 'python -m cli.main status',    Icon: CheckCircle,  color: '#22c55e' },
  { label: 'CLI Health',    cmd: 'python -m cli.main health',    Icon: FlaskConical, color: '#22c55e' },
  { label: 'ATLAS Status',  cmd: 'python -m cli.main atlas status', Icon: Bot, color: 'var(--violet)' },
  { label: 'Git Log',       cmd: 'git log --oneline -20',        Icon: GitBranch,    color: '#eab308' },
  { label: 'Git Branch',    cmd: 'git branch',                   Icon: GitBranch,    color: 'var(--cyan)' },
  { label: 'npm Build',     cmd: 'npm run build',                Icon: Hammer,       color: '#eab308' },
]

const COMMAND_PLAYBOOK = [
  {
    label: 'Runtime Status',
    cmd: 'python -m cli.main status',
    note: 'Checks overall CLI/runtime health quickly before running larger jobs.',
  },
  {
    label: 'ATLAS Status',
    cmd: 'python -m cli.main atlas status',
    note: 'Confirms ATLAS runtime wiring and model/provider readiness.',
  },
  {
    label: 'ATLAS Code Generate',
    cmd: 'python -m cli.main atlas code generate "build a MammothOS notes panel"',
    note: 'Runs the coding workflow from inside the UI terminal.',
  },
  {
    label: 'ATLAS Code Scan',
    cmd: 'python -m cli.main atlas code scan src\\mammoth_os\\agents\\coding_agent.py',
    note: 'Asks the coding workflow for a structured scan of one file.',
  },
  {
    label: 'ATLAS UI Component',
    cmd: 'python -m cli.main atlas ui component "create a neon command-center status card"',
    note: 'Uses UIBuilderAgent from the UI terminal.',
  },
  {
    label: 'ATLAS UI Palette',
    cmd: 'python -m cli.main atlas ui palette "Apply MammothOS command center dark theme and preserve existing layout"',
    note: 'Generates palette-oriented UI guidance for theming tasks.',
  },
  {
    label: 'Health page source scan',
    cmd: 'python -m cli.main atlas code scan ui\\mad-architecht-command-center\\src\\pages\\HealthPage.jsx',
    note: 'Useful before asking agents to split system health and personal health.',
  },
  {
    label: 'Log Sale page source scan',
    cmd: 'python -m cli.main atlas code scan ui\\mad-architecht-command-center\\src\\pages\\LogSalePage.jsx',
    note: 'Useful before asking agents to split personal and business finances.',
  },
  {
    label: 'Frontend build check',
    cmd: 'npm run build',
    note: 'Validates UI changes compile cleanly after agent-generated edits.',
  },
]

const BOOT_LINES = [
  { text: '[BOOT] MammothOS Terminal initializing...', type: 'stdout' },
  { text: '[BOOT] Loading command allow-list + runtime bridge...', type: 'stdout' },
  { text: '[BOOT] Attempting WebSocket handshake (/ws/terminal)...', type: 'stdout' },
]

export default function TerminalPage({ setPage }) {
  const [lines, setLines]           = useState(BOOT_LINES)
  const [input, setInput]           = useState('')
  const [connected, setConnected]   = useState(false)
  const [httpMode, setHttpMode]     = useState(false)
  const [httpBusy, setHttpBusy]     = useState(false)
  const [playbookOpen, setPlaybookOpen] = useState(false)
  const wsRef     = useRef(null)
  const bottomRef = useRef(null)

  const addLine = (text, type = 'stdout') =>
    setLines(prev => [...prev, { text, type }])

  useEffect(() => {
    const connect = () => {
      try {
        const ws = openTerminalWS()
        wsRef.current = ws

        ws.onopen = () => {
          setConnected(true)
          addLine('✓ WebSocket connected to /ws/terminal', 'stdout')
        }
        ws.onmessage = (e) => {
          const data = JSON.parse(e.data)
          addLine(data.line, data.type)
        }
        ws.onclose = () => {
          setConnected(false)
          addLine('⚠ WebSocket disconnected. Reconnecting in 3s…', 'stderr')
          setTimeout(connect, 3000)
        }
        ws.onerror = () => {
          addLine('⚠ WebSocket error — backend may be offline.', 'stderr')
        }
      } catch (e) {
        addLine(`Could not connect: ${e.message}`, 'stderr')
      }
    }
    connect()
    return () => wsRef.current?.close()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  const sendHTTP = async (cmd) => {
    if (!cmd.trim() || httpBusy) return
    setHttpBusy(true)
    addLine(`$ ${cmd}`, 'cmd')
    try {
      const res = await fetch('/api/terminal/exec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmd }),
      })
      const data = await res.json()
      if (data.stdout) data.stdout.split('\n').filter(Boolean).forEach(l => addLine(l, 'stdout'))
      if (data.stderr) data.stderr.split('\n').filter(Boolean).forEach(l => addLine(l, 'stderr'))
      addLine(`[exit ${data.exit_code ?? 0}]`, 'exit')
    } catch (e) {
      addLine(`HTTP error: ${e.message}`, 'stderr')
    } finally {
      setHttpBusy(false)
    }
  }

  const sendWS = (cmd) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ cmd }))
    } else {
      addLine('⚠ Not connected to backend terminal.', 'stderr')
    }
  }

  const send = (cmd) => {
    if (!cmd.trim()) return
    if (httpMode || !connected) {
      if (!httpMode) {
        setHttpMode(true)
        addLine('ℹ WebSocket offline — auto-switching to HTTP fallback mode.', 'stderr')
      }
      sendHTTP(cmd)
    } else {
      sendWS(cmd)
    }
  }

  const submit = (e) => {
    e.preventDefault()
    send(input)
    setInput('')
  }

  const lineColor = (type) => {
    if (type === 'stderr') return '#f87171'
    if (type === 'exit')   return '#a3e635'
    if (type === 'cmd')    return '#e2e8f0'
    return '#4ade80'
  }

  return (
    <div className="page-enter" style={{ padding: 24, display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Terminal size={20} color="var(--cyan)" /> Terminal
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {!connected && (
            <button onClick={() => setHttpMode(m => !m)}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 8, border: `1px solid ${httpMode ? 'var(--cyan)' : 'var(--border)'}`, background: httpMode ? 'rgba(0,212,255,0.1)' : 'transparent', color: httpMode ? 'var(--cyan)' : 'var(--txt-sec)', fontSize: '0.72rem', cursor: 'pointer', fontFamily: 'JetBrains Mono,monospace' }}>
              <WifiOff size={12} /> {httpMode ? 'HTTP MODE' : 'Use HTTP fallback'}
            </button>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: connected ? '#22c55e' : (httpMode ? 'var(--cyan)' : '#ef4444') }} />
            <span style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: connected ? '#22c55e' : (httpMode ? 'var(--cyan)' : '#ef4444') }}>
              {connected ? 'CONNECTED' : httpMode ? 'HTTP MODE' : 'DISCONNECTED'}
            </span>
          </div>
        </div>
      </div>

      <OnboardingGuide variant="banner" currentPage="terminal" setPage={setPage} />

      {/* Quick actions — single scrollable row, no wrapping */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, overflowX: 'auto', paddingBottom: 4, flexShrink: 0 }}>
        {QUICK_ACTIONS.map(a => (
          <button key={a.cmd} onClick={() => send(a.cmd)} className="glass-card-solid"
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 12px', borderRadius: 8, border: '1px solid var(--border)', cursor: 'pointer', fontSize: '0.8rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', background: 'var(--card)', opacity: httpBusy ? 0.6 : 1, flexShrink: 0 }}>
            <a.Icon size={13} color={a.color} /> {a.label}
          </button>
        ))}
      </div>

      {/* Collapsible playbook */}
      <div className="glass-card-solid" style={{ marginBottom: 10, borderLeft: '2px solid var(--cyan)', flexShrink: 0 }}>
        <button
          onClick={() => setPlaybookOpen(o => !o)}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '9px 14px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-pri)' }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.84rem', fontWeight: 600 }}>
            <BookOpen size={14} color="var(--cyan)" /> Terminal playbook
          </span>
          <span style={{ fontSize: '0.72rem', color: 'var(--txt-sec)', fontFamily: 'JetBrains Mono,monospace' }}>
            {playbookOpen ? '▲ hide' : '▼ show'}
          </span>
        </button>
        {playbookOpen && (
          <div style={{ padding: '0 14px 14px' }}>
            <div style={{ color: 'var(--txt-sec)', fontSize: '0.78rem', lineHeight: 1.7, marginBottom: 10 }}>
              ATLAS CLI commands are supported here too, including <code style={{ color: 'var(--photon)' }}>python -m cli.main atlas code ...</code>.
              Longer ATLAS code and UI commands get an extended backend timeout.
            </div>
            <div style={{ color: 'var(--txt-mut)', fontSize: '0.72rem', lineHeight: 1.6, marginBottom: 10 }}>
              Tip: click a card to run immediately. Use scans first, then generate/edit commands, then run build.
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {COMMAND_PLAYBOOK.map((item) => (
                <button
                  key={item.cmd}
                  onClick={() => { setInput(item.cmd); send(item.cmd) }}
                  className="glass-card-solid"
                  style={{ textAlign: 'left', padding: 10, borderRadius: 8, border: '1px solid var(--border)', cursor: 'pointer', background: 'rgba(255,255,255,0.03)' }}
                >
                  <div style={{ color: 'var(--txt-pri)', fontSize: '0.78rem', marginBottom: 4 }}>{item.label}</div>
                  <code style={{ color: 'var(--photon)', fontSize: '0.72rem', whiteSpace: 'pre-wrap' }}>{item.cmd}</code>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.72rem', marginTop: 4 }}>{item.note}</div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="glass-card-solid" style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRadius: 12, overflow: 'hidden' }}>
        {/* title bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {['#ef4444', '#eab308', '#22c55e'].map(c => <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />)}
            <span style={{ fontSize: '0.7rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', marginLeft: 8 }}>
              {httpMode ? 'mammoth@http:/api/terminal/exec' : 'mammoth@ws:/ws/terminal'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => navigator.clipboard.writeText(lines.map(l => l.text).join('\n'))}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)' }}><Copy size={14} /></button>
            <button onClick={() => setLines([])}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)' }}><Trash2 size={14} /></button>
          </div>
        </div>

        {/* output */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 16, fontFamily: 'JetBrains Mono,monospace', fontSize: '0.82rem', lineHeight: 1.8, background: '#050608' }}>
          {lines.map((l, i) => (
            <div key={i} style={{ color: lineColor(l.type) }}>{l.text}</div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* input */}
        <form onSubmit={submit} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px', borderTop: '1px solid var(--border)', background: '#050608' }}>
          <span style={{ color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace', fontWeight: 700 }}>$</span>
          <input value={input} onChange={e => setInput(e.target.value)} placeholder='Try: python -m cli.main atlas code generate "upgrade my notes panel"'
            style={{ flex: 1, background: 'none', border: 'none', color: '#4ade80', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.85rem', outline: 'none' }} />
          <button type="submit" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--cyan)' }}>
            <Play size={14} />
          </button>
        </form>
      </div>
    </div>
  )
}