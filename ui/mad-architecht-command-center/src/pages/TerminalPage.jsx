import { useState, useEffect, useRef, useCallback } from 'react'
import { Terminal, Play, Copy, Trash2, GitBranch, Hammer, Bot, FlaskConical, CheckCircle, WifiOff, BookOpen, Server, Package, Activity, RefreshCw } from 'lucide-react'
import { authorizedFetch, openTerminalWS } from '../api/client'
import { getAccessToken } from '../lib/supabase'
import OnboardingGuide from '../components/OnboardingGuide'

const QUICK_ACTIONS = [
  { label: 'Git Status', cmd: 'git status', Icon: GitBranch, color: 'var(--violet)', note: 'working tree' },
  { label: 'Git Log', cmd: 'git log --oneline -20', Icon: GitBranch, color: '#eab308', note: 'recent history' },
  { label: 'Git Branch', cmd: 'git branch', Icon: GitBranch, color: 'var(--cyan)', note: 'branch list' },
  { label: 'Agent List', cmd: 'python -m cli.main agent-list', Icon: Bot, color: 'var(--photon)', note: 'available lanes' },
  { label: 'CLI Status', cmd: 'python -m cli.main status', Icon: CheckCircle, color: '#22c55e', note: 'runtime snapshot' },
  { label: 'CLI Health', cmd: 'python -m cli.main health', Icon: FlaskConical, color: '#22c55e', note: 'health report' },
  { label: 'ATLAS Status', cmd: 'python -m cli.main atlas status', Icon: Bot, color: 'var(--violet)', note: 'atlas wiring' },
  { label: 'Service Status', cmd: 'systemctl status mammothos', Icon: Server, color: '#f97316', note: 'server process' },
  { label: 'Server Logs', cmd: 'journalctl -u mammothos -n 50 --no-pager', Icon: Activity, color: '#f97316', note: 'recent log lines' },
  { label: 'Disk Usage', cmd: 'df -h', Icon: Server, color: 'var(--cyan)', note: 'disk space' },
  { label: 'Memory', cmd: 'free -h', Icon: Activity, color: '#a3e635', note: 'ram usage' },
  { label: 'Pip List', cmd: 'pip list', Icon: Package, color: '#a855f7', note: 'installed packages' },
  { label: 'npm Build', cmd: 'npm run build', Icon: Hammer, color: '#eab308', note: 'frontend verify' },
  { label: 'Restart Service', cmd: 'systemctl restart mammothos', Icon: RefreshCw, color: '#ef4444', note: '⚠ live restart' },
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
    cmd: 'python -m cli.main atlas code scan src/mammoth_os/agents/coding_agent.py',
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
    label: 'Service Status',
    cmd: 'systemctl status mammothos',
    note: 'Check if the MammothOS backend service is running on the server.',
  },
  {
    label: 'Restart Service',
    cmd: 'systemctl restart mammothos',
    note: 'Restart the live MammothOS backend. Takes ~5s — refresh the UI after.',
  },
  {
    label: 'Tail Service Logs',
    cmd: 'journalctl -u mammothos -n 100 --no-pager',
    note: 'Last 100 lines from the systemd service log — useful for diagnosing crashes.',
  },
  {
    label: 'Git Pull Latest',
    cmd: 'git pull origin main',
    note: 'Pull the latest commits from main — run before restarting the service.',
  },
  {
    label: 'Disk Usage',
    cmd: 'df -h',
    note: 'Check available disk space on the server. Important for upload/storage health.',
  },
  {
    label: 'Memory Usage',
    cmd: 'free -h',
    note: 'See how much RAM the server is using. Helpful when agents feel slow.',
  },
  {
    label: 'Pip List',
    cmd: 'pip list',
    note: 'List installed Python packages — confirm dependencies are present.',
  },
  {
    label: 'Python Version',
    cmd: 'python --version',
    note: 'Confirm the Python version in use on the server.',
  },
  {
    label: 'Frontend build check',
    cmd: 'npm run build',
    note: 'Validates UI changes compile cleanly after agent-generated edits.',
  },
  {
    label: 'Health page source scan',
    cmd: 'python -m cli.main atlas code scan ui/mad-architecht-command-center/src/pages/HealthPage.jsx',
    note: 'Useful before asking agents to split system health and personal health.',
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
  const [history, setHistory]       = useState([])
  const [historyIdx, setHistoryIdx] = useState(-1)
  const wsRef     = useRef(null)
  const bottomRef = useRef(null)
  const inputRef  = useRef(null)

  const addLine = (text, type = 'stdout') =>
    setLines(prev => [...prev, { text, type }])

  useEffect(() => {
    let cancelled = false

    const connect = async () => {
      try {
        const token = await getAccessToken()
        if (cancelled) return
        const ws = openTerminalWS(token)
        wsRef.current = ws

        ws.onopen = () => {
          setConnected(true)
          setHttpMode(false)
          addLine('✓ WebSocket connected to /ws/terminal', 'stdout')
        }
        ws.onmessage = (e) => {
          try {
            const data = JSON.parse(e.data)
            addLine(data.line, data.type)
          } catch { /* ignore malformed */ }
        }
        ws.onclose = (e) => {
          setConnected(false)
          if (e.code === 1008) {
            addLine('✗ Auth rejected — check MAMMOTH_OWNER_EMAIL is set in server .env', 'stderr')
            addLine('  Falling back to HTTP mode. Some commands may still work.', 'stderr')
            setHttpMode(true)
          } else {
            addLine('⚠ WebSocket disconnected. Reconnecting in 3s…', 'stderr')
            setTimeout(connect, 3000)
          }
        }
        ws.onerror = () => {
          addLine('⚠ WebSocket error — backend may be offline or refusing connection.', 'stderr')
        }
      } catch (e) {
        if (cancelled) return
        addLine(`Could not connect: ${e.message}`, 'stderr')
        setHttpMode(true)
      }
    }
    connect()
    return () => {
      cancelled = true
      wsRef.current?.close()
    }
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines])

  const sendHTTP = async (cmd) => {
    if (!cmd.trim() || httpBusy) return
    setHttpBusy(true)
    addLine(`$ ${cmd}`, 'cmd')
    try {
      const res = await authorizedFetch('/terminal/exec', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmd }),
      })
      const data = await res.json()
      if (data.cwd) addLine(`[cwd] ${data.cwd}`, 'stdout')
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

  const send = useCallback((cmd) => {
    if (!cmd.trim()) return
    // push to history
    setHistory(prev => {
      const next = prev.filter(c => c !== cmd)
      return [...next, cmd].slice(-100)
    })
    setHistoryIdx(-1)
    if (httpMode || !connected) {
      if (!httpMode) {
        setHttpMode(true)
        addLine('ℹ WebSocket offline — auto-switching to HTTP fallback mode.', 'stderr')
      }
      sendHTTP(cmd)
    } else {
      sendWS(cmd)
    }
  }, [httpMode, connected])

  const submit = (e) => {
    e.preventDefault()
    send(input)
    setInput('')
  }

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHistoryIdx(prev => {
        const next = Math.min(prev + 1, history.length - 1)
        if (next >= 0) setInput(history[history.length - 1 - next])
        return next
      })
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHistoryIdx(prev => {
        const next = Math.max(prev - 1, -1)
        setInput(next < 0 ? '' : history[history.length - 1 - next])
        return next
      })
    }
  }

  const lineColor = (type) => {
    if (type === 'stderr') return '#f87171'
    if (type === 'exit')   return '#a3e635'
    if (type === 'cmd')    return '#e2e8f0'
    return '#4ade80'
  }

  const statusTone = connected ? '#22c55e' : (httpMode ? 'var(--cyan)' : '#ef4444')
  const modeLabel = connected ? 'Live WebSocket lane' : httpMode ? 'HTTP fallback lane' : 'Disconnected lane'

  return (
    <div className="page-enter" style={{ padding: '16px 24px', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 64px)', overflow: 'hidden', gap: 8 }}>
      {/* Compact header bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexShrink: 0 }}>
        <h1 style={{ fontSize: '1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8, margin: 0 }}>
          <Terminal size={18} color="var(--cyan)" /> Terminal
          <span style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', fontWeight: 400, marginLeft: 4 }}>
            live operator shell · ATLAS CLI routing
          </span>
        </h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {!connected && (
            <button onClick={() => setHttpMode(m => !m)}
              style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 6, border: `1px solid ${httpMode ? 'var(--cyan)' : 'var(--border)'}`, background: httpMode ? 'rgba(0,212,255,0.1)' : 'transparent', color: httpMode ? 'var(--cyan)' : 'var(--txt-sec)', fontSize: '0.7rem', cursor: 'pointer', fontFamily: 'JetBrains Mono,monospace' }}>
              <WifiOff size={11} /> {httpMode ? 'HTTP' : 'HTTP fallback'}
            </button>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: statusTone }} />
            <span style={{ fontSize: '0.7rem', fontFamily: 'JetBrains Mono,monospace', color: statusTone, fontWeight: 700 }}>
              {connected ? 'WS LIVE' : httpMode ? 'HTTP' : 'OFFLINE'}
            </span>
          </div>
        </div>
      </div>

      <OnboardingGuide variant="banner" currentPage="terminal" setPage={setPage} />

      {/* Compact quick actions */}
      <div style={{ flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 6, overflowX: 'auto', paddingBottom: 4 }}>
          {QUICK_ACTIONS.map(a => (
            <button key={a.cmd} onClick={() => send(a.cmd)}
              style={{ display: 'flex', alignItems: 'center', gap: 7, padding: '7px 11px', borderRadius: 8, border: '1px solid var(--border)', cursor: 'pointer', fontFamily: 'JetBrains Mono,monospace', background: 'rgba(255,255,255,0.04)', opacity: httpBusy ? 0.6 : 1, flexShrink: 0, whiteSpace: 'nowrap', transition: 'all 0.15s' }}
              title={a.note}>
              <a.Icon size={13} color={a.color} />
              <span style={{ color: 'var(--txt-pri)', fontSize: '0.75rem', fontWeight: 600 }}>{a.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Collapsible playbook */}
      <div className="glass-card-solid" style={{ flexShrink: 0, borderLeft: '2px solid var(--cyan)' }}>
        <button
          onClick={() => setPlaybookOpen(o => !o)}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', padding: '9px 14px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-pri)' }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.8rem', fontWeight: 600 }}>
            <BookOpen size={13} color="var(--cyan)" /> Terminal Playbook
            <span style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', fontWeight: 400, fontFamily: 'JetBrains Mono,monospace' }}>
              · {COMMAND_PLAYBOOK.length} commands · ↑↓ history
            </span>
          </span>
          <span style={{ fontSize: '0.7rem', color: 'var(--txt-sec)', fontFamily: 'JetBrains Mono,monospace' }}>
            {playbookOpen ? '▲' : '▼ expand'}
          </span>
        </button>
        {playbookOpen && (
          <div style={{ padding: '0 14px 12px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 8, maxHeight: '28vh', overflowY: 'auto', paddingRight: 2 }}>
              {COMMAND_PLAYBOOK.map((item) => (
                <button
                  key={item.cmd}
                  onClick={() => { setInput(item.cmd); send(item.cmd) }}
                  className="glass-card-solid"
                  style={{ textAlign: 'left', padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', cursor: 'pointer', background: 'rgba(255,255,255,0.03)', minWidth: 0 }}
                >
                  <div style={{ color: 'var(--txt-pri)', fontSize: '0.78rem', marginBottom: 4, fontWeight: 700 }}>{item.label}</div>
                  <code style={{ color: 'var(--photon)', fontSize: '0.68rem', whiteSpace: 'pre-wrap', wordBreak: 'break-all', display: 'block', marginBottom: 5 }}>{item.cmd}</code>
                  <div style={{ color: 'var(--txt-sec)', fontSize: '0.68rem', lineHeight: 1.45 }}>{item.note}</div>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="glass-card-solid" style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', borderRadius: 12, overflow: 'hidden' }}>
        {/* title bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {['#ef4444', '#eab308', '#22c55e'].map(c => <div key={c} style={{ width: 10, height: 10, borderRadius: '50%', background: c }} />)}
            <span style={{ fontSize: '0.7rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', marginLeft: 8 }}>
              {httpMode ? 'mammoth@http:/api/terminal/exec' : 'mammoth@ws:/ws/terminal'}
            </span>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <span style={{ fontSize: '0.65rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace', alignSelf: 'center' }}>
              {history.length > 0 ? `${history.length} in history` : ''}
            </span>
            <button onClick={() => navigator.clipboard.writeText(lines.map(l => l.text).join('\n'))}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)' }} title="Copy all output"><Copy size={14} /></button>
            <button onClick={() => setLines([])}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)' }} title="Clear terminal"><Trash2 size={14} /></button>
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
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder='Try: systemctl status mammothos  — ↑↓ for history'
            style={{ flex: 1, background: 'none', border: 'none', color: '#4ade80', fontFamily: 'JetBrains Mono,monospace', fontSize: '0.85rem', outline: 'none' }}
            autoFocus
          />
          <button type="submit" disabled={httpBusy} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--cyan)', opacity: httpBusy ? 0.5 : 1 }}>
            <Play size={14} />
          </button>
        </form>
      </div>
    </div>
  )
}