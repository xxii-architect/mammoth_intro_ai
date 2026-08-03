import { useState, useEffect, useRef } from 'react'
import { Terminal, Play, Copy, Trash2, Globe, GitBranch, Hammer, Bot, FlaskConical, CheckCircle } from 'lucide-react'
import { openTerminalWS } from '../api/client'

const QUICK_ACTIONS = [
  { label: 'Git Status',    cmd: 'git status',                  Icon: GitBranch, color: 'var(--violet)' },
  { label: 'Agent List',    cmd: 'python -m cli.main agent-list', Icon: Bot,       color: 'var(--photon)' },
  { label: 'CLI Status',    cmd: 'python -m cli.main status',   Icon: CheckCircle, color: '#22c55e' },
  { label: 'CLI Health',    cmd: 'python -m cli.main health',   Icon: FlaskConical, color: '#22c55e' },
  { label: 'Git Log',       cmd: 'git log --oneline -20',       Icon: GitBranch, color: '#eab308' },
  { label: 'Git Branch',    cmd: 'git branch',                  Icon: GitBranch, color: 'var(--cyan)' },
  { label: 'npm Build',     cmd: 'npm run build',               Icon: Hammer,    color: '#eab308' },
]

export default function TerminalPage() {
  const [lines, setLines] = useState([{ text: 'MammothOS Terminal — WebSocket connected.', type: 'stdout' }])
  const [input, setInput] = useState('')
  const [connected, setConnected] = useState(false)
  const wsRef   = useRef(null)
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

  const send = (cmd) => {
    if (!cmd.trim()) return
    addLine(`$ ${cmd}`, 'stdout')
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ cmd }))
    } else {
      addLine('⚠ Not connected to backend terminal.', 'stderr')
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
    return '#4ade80'
  }

  return (
    <div className="page-enter" style={{ padding: 24, display: 'flex', flexDirection: 'column', height: 'calc(100vh - 100px)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Terminal size={20} color="var(--cyan)" /> Terminal
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: connected ? '#22c55e' : '#ef4444' }} />
          <span style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: connected ? '#22c55e' : '#ef4444' }}>
            {connected ? 'CONNECTED' : 'DISCONNECTED'}
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
        {QUICK_ACTIONS.map(a => (
          <button key={a.cmd} onClick={() => send(a.cmd)} className="glass-card-solid"
            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', borderRadius: 8, border: '1px solid var(--border)', cursor: 'pointer', fontSize: '0.82rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-sec)', background: 'var(--card)' }}>
            <a.Icon size={14} color={a.color} /> {a.label}
          </button>
        ))}
      </div>

      <div className="glass-card-solid" style={{ flex: 1, display: 'flex', flexDirection: 'column', borderRadius: 12, overflow: 'hidden' }}>
        {/* title bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {['#ef4444','#eab308','#22c55e'].map(c => <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />)}
            <span style={{ fontSize: '0.7rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', marginLeft: 8 }}>mammoth@ws:/ws/terminal</span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={() => navigator.clipboard.writeText(lines.map(l => l.text).join('\n'))}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)' }}><Copy size={14} /></button>
            <button onClick={() => setLines([])}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)' }}><Trash2 size={14} /></button>
          </div>
        </div>

        {/* output */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 16, fontFamily: 'JetBrains Mono,monospace', fontSize: '0.78rem', lineHeight: 1.7, background: '#050608' }}>
          {lines.map((l, i) => (
            <div key={i} style={{ color: lineColor(l.type) }}>{l.text}</div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* input */}
        <form onSubmit={submit} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 16px', borderTop: '1px solid var(--border)', background: '#050608' }}>
          <span style={{ color: 'var(--cyan)', fontFamily: 'JetBrains Mono,monospace', fontWeight: 700 }}>$</span>
          <input value={input} onChange={e => setInput(e.target.value)} placeholder="Enter allowed command…"
            style={{ flex: 1, background: 'none', border: 'none', color: '#4ade80', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.85rem', outline: 'none' }} />
          <button type="submit" style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--cyan)' }}>
            <Play size={14} />
          </button>
        </form>
      </div>
    </div>
  )
}
