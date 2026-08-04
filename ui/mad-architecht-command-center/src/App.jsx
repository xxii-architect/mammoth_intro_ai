import { useState, useEffect, useRef, useCallback } from 'react'
import {
  LayoutDashboard, Bot, Terminal, FileText, Package, HeartPulse,
  DollarSign, BookOpen, ClipboardList, Settings, PanelLeft, Search, GraduationCap,
  Activity,
  Sparkles, CreditCard, ShieldCheck,
} from 'lucide-react'

import HomePage        from './pages/HomePage'
import AgentPage       from './pages/AgentPage'
import TerminalPage    from './pages/TerminalPage'
import NotesPage       from './pages/NotesPage'
import ModulesPage     from './pages/ModulesPage'
import HealthPage      from './pages/HealthPage'
import LessonsPage     from './pages/LessonsPage'
import BuildLogPage    from './pages/BuildLogPage'
import LogSalePage     from './pages/LogSalePage'
import SettingsPage    from './pages/SettingsPage'
import AtlasTutorPage  from './pages/AtlasTutorPage'
import LandingPage    from './pages/LandingPage'
import CompliancePage from './pages/CompliancePage'
import PricingPage    from './pages/PricingPage'
import DiagnosticsPage from './pages/DiagnosticsPage'

const THEMES = {
  darker:   { '--shell': '#050608', '--card': '#0d1117', '--card-hover': '#161b22' },
  dark:     { '--shell': '#0d1117', '--card': '#161b22', '--card-hover': '#1f2937' },
  midnight: { '--shell': '#080c14', '--card': '#0f1520', '--card-hover': '#1a2233' },
}

const NAV = [
  { section: 'Workspace' },
  { id: 'home',     label: 'Home',        Icon: LayoutDashboard },
  { id: 'agent',    label: 'Agent',       Icon: Bot },
  { id: 'terminal', label: 'Terminal',    Icon: Terminal },
  { section: 'Tools' },
  { id: 'notes',    label: 'Notes',       Icon: FileText },
  { id: 'modules',  label: 'Modules',     Icon: Package },
  { id: 'health',   label: 'Health',      Icon: HeartPulse },
  { id: 'logsale',  label: 'Log Sale',    Icon: DollarSign, accent: 'var(--cyan)' },
  { section: 'Product' },
  { id: 'landing',    label: 'Landing Page',       Icon: Sparkles,    accent: 'var(--cyan)' },
  { id: 'pricing',    label: 'Pricing',            Icon: CreditCard },
  { id: 'compliance', label: 'Legal & Compliance', Icon: ShieldCheck },
  { section: 'Learn' },
  { id: 'lessons',  label: 'Lessons',     Icon: BookOpen },
  { id: 'atlas',    label: 'ATLAS Tutor', Icon: GraduationCap, accent: 'var(--violet)' },
  { id: 'buildlog', label: 'Build Log',   Icon: ClipboardList },
  { section: 'System' },
  { id: 'diagnostics', label: 'Diagnostics', Icon: Activity, accent: 'var(--cyan)' },
  { id: 'settings', label: 'Settings',    Icon: Settings },
]

const PAGE_COMPONENTS = {
  home:     HomePage,
  agent:    AgentPage,
  terminal: TerminalPage,
  notes:    NotesPage,
  modules:  ModulesPage,
  health:   HealthPage,
  logsale:  LogSalePage,
  lessons:  LessonsPage,
  atlas:    AtlasTutorPage,
  buildlog: BuildLogPage,
  settings: SettingsPage,
  landing:    LandingPage,
  pricing:    PricingPage,
  compliance: CompliancePage,
  diagnostics: DiagnosticsPage,
}

function AtlasFAB({ currentPage }) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState('tutor')
  const [strictGuard, setStrictGuard] = useState(true)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  const send = async () => {
    if (!input.trim() || busy) return
    const msg = input.trim()
    const selectedText = window.getSelection ? window.getSelection().toString().trim().slice(0, 400) : ''
    let lessonContext = {}
    try {
      const raw = localStorage.getItem('atlas_fab_context')
      if (raw) lessonContext = JSON.parse(raw)
    } catch (_) {
      lessonContext = {}
    }
    setInput('')
    setBusy(true)
    setHistory(h => [...h, { role: 'user', message: msg }])
    try {
      const res = await fetch('/api/atlas/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: msg,
          mode,
          strict_guard: strictGuard,
          regenerate_on_guard: true,
          page_context: {
            current_page: currentPage,
            selected_text: selectedText,
            lesson: lessonContext,
          },
        }),
      })
      const data = await res.json()
      if (Array.isArray(data.chat_history)) {
        setHistory(data.chat_history)
      } else {
        setHistory(h => [...h, { role: 'assistant', message: data.reply || data.error || 'No response.' }])
      }
    } catch (e) {
      setHistory(h => [...h, { role: 'assistant', message: `⚠ ${e.message}` }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 9000,
          width: 52, height: 52, borderRadius: '50%',
          background: 'var(--violet)',
          border: '2px solid rgba(180,124,255,0.5)',
          boxShadow: '0 0 20px rgba(180,124,255,0.5)',
          animation: 'pulse-violet 2.5s infinite',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: '1.3rem',
        }}
        title="ATLAS Tutor"
      >
        🐘
      </button>

      {open && (
        <div style={{
          position: 'fixed', bottom: 86, right: 24, zIndex: 8999,
          width: 360, height: 480,
          background: 'rgba(13,17,23,0.96)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(180,124,255,0.3)',
          borderRadius: 16,
          boxShadow: '0 8px 48px rgba(0,0,0,0.6), 0 0 24px rgba(180,124,255,0.15)',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(180,124,255,0.08)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '1rem' }}>🐘</span>
              <div>
                <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600, color: 'var(--violet)' }}>ATLAS Tutor</p>
                <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--txt-mut)' }}>AI-powered coding mentor</p>
              </div>
            </div>
            <button onClick={() => setOpen(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)', fontSize: '1rem', padding: 4 }}>✕</button>
          </div>

          <div style={{ padding: '8px 12px', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <select
              value={mode}
              onChange={e => setMode(e.target.value)}
              style={{ flex: 1, minWidth: 120, padding: '6px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-pri)', fontSize: '0.72rem' }}
            >
              <option value="tutor">Tutor mode</option>
              <option value="build">Plan + Build mode</option>
            </select>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--txt-sec)', fontSize: '0.68rem', whiteSpace: 'nowrap' }}>
              <input
                type="checkbox"
                checked={strictGuard}
                onChange={e => setStrictGuard(e.target.checked)}
              />
              No-cheat guard
            </label>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 10 }}>
            {history.length === 0 && (
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.82rem', textAlign: 'center', marginTop: 40 }}>
                <p style={{ marginBottom: 8 }}>👋 Hi Vernon!</p>
                <p>Ask me anything about your current lesson, code, or MammothOS.</p>
              </div>
            )}
            {history.slice(-30).map((msg, i) => (
              <div key={i} style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
              }}>
                <div style={{
                  padding: '8px 12px',
                  borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                  background: msg.role === 'user' ? 'rgba(77,166,255,0.2)' : 'rgba(180,124,255,0.12)',
                  border: `1px solid ${msg.role === 'user' ? 'rgba(77,166,255,0.3)' : 'rgba(180,124,255,0.25)'}`,
                  fontSize: '0.82rem', color: 'var(--txt-pri)', lineHeight: 1.55,
                  whiteSpace: 'pre-wrap',
                }}>
                  {msg.message}
                </div>
                {msg.model && (
                  <p style={{ margin: '2px 4px', fontSize: '0.62rem', color: 'var(--txt-mut)' }}>{msg.model}</p>
                )}
              </div>
            ))}
            {busy && (
              <div style={{ display: 'flex', gap: 4, padding: 8, alignSelf: 'flex-start' }}>
                {[0, 1, 2].map(i => <span key={i} className="thinking-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--violet)', display: 'inline-block' }} />)}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div style={{ padding: '10px 12px', borderTop: '1px solid var(--border)', display: 'flex', gap: 8 }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              placeholder="Ask ATLAS…"
              style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.05)', color: 'var(--txt-pri)', fontSize: '0.82rem', outline: 'none', fontFamily: 'Inter,sans-serif' }}
            />
            <button onClick={send} disabled={busy}
              style={{ padding: '8px 14px', borderRadius: 8, border: 'none', background: busy ? 'rgba(180,124,255,0.3)' : 'var(--violet)', color: '#fff', fontWeight: 700, cursor: busy ? 'not-allowed' : 'pointer', fontSize: '0.82rem' }}>
              {busy ? '…' : '↑'}
            </button>
          </div>
        </div>
      )}
    </>
  )
}

export default function App() {
  const [page, setPage] = useState(() => localStorage.getItem('mmPage') || 'home')
  const [collapsed, setCollapsed] = useState(false)
  const [theme, setTheme] = useState(() => localStorage.getItem('mmTheme') || 'darker')

  useEffect(() => {
    const vars = THEMES[theme] || THEMES.darker
    Object.entries(vars).forEach(([k, v]) => document.documentElement.style.setProperty(k, v))
    localStorage.setItem('mmTheme', theme)
  }, [theme])

  useEffect(() => {
    localStorage.setItem('mmPage', page)
  }, [page])

  const nav = useCallback((id) => setPage(id), [])
  const sidebarW = collapsed ? 56 : 240
  const PageComponent = PAGE_COMPONENTS[page]

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'var(--shell)', fontFamily: 'Inter,system-ui,sans-serif', color: 'var(--txt-pri)', overflow: 'hidden' }}>

      {/* Header */}
      <header style={{
        position: 'fixed', top: 0, left: 0, right: 0, height: 52, zIndex: 100,
        background: 'rgba(13,17,23,0.85)', backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 16px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button onClick={() => setCollapsed(c => !c)}
            style={{ padding: 6, borderRadius: 8, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)' }}>
            <PanelLeft size={20} />
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--txt-pri)' }}>Mammoth</span>
            <span style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--photon)' }}>OS</span>
            <span style={{ fontSize: '0.65rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--photon)', border: '1px solid rgba(77,166,255,0.3)', borderRadius: 20, padding: '2px 6px', marginLeft: 4 }}>v2036</span>
          </div>
        </div>

        <span style={{ fontSize: '0.7rem', letterSpacing: '0.2em', color: 'var(--txt-mut)', fontWeight: 500, textTransform: 'uppercase' }}>
          Command Center
        </span>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div className="live-dot" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--cyan)' }} />
            <span style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--cyan)', fontWeight: 600 }}>LIVE</span>
          </div>
          <button style={{ display: 'flex', alignItems: 'center', gap: 6, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border)', borderRadius: 8, padding: '6px 10px', cursor: 'pointer', color: 'var(--txt-sec)' }}>
            <Search size={14} />
            <span style={{ fontSize: '0.7rem', fontFamily: 'JetBrains Mono,monospace' }}>Ctrl+K</span>
          </button>
        </div>
      </header>

      {/* Sidebar */}
      <aside style={{
        position: 'fixed', top: 52, left: 0, bottom: 0, width: sidebarW, zIndex: 90,
        background: 'rgba(13,17,23,0.85)', backdropFilter: 'blur(16px)',
        borderRight: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column',
        transition: 'width 0.25s ease', overflow: 'hidden',
      }}>
        <nav style={{ flex: 1, padding: '8px 0', overflowY: 'auto', overflowX: 'hidden' }}>
          {NAV.map((item, i) => {
            if (item.section) {
              return collapsed ? null : (
                <div key={i} style={{ fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--txt-mut)', padding: '16px 16px 4px' }}>
                  {item.section}
                </div>
              )
            }
            const active = page === item.id
            const accentColor = item.accent || 'var(--photon)'
            return (
              <div key={item.id} onClick={() => nav(item.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 16px',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  borderRadius: 8, margin: '1px 8px',
                  cursor: 'pointer', transition: 'all 0.15s',
                  borderLeft: `3px solid ${active ? accentColor : 'transparent'}`,
                  background: active ? 'rgba(255,255,255,0.07)' : 'transparent',
                  color: active ? accentColor : (item.accent || 'var(--txt-sec)'),
                  fontSize: '0.82rem', fontWeight: 500,
                }}>
                <item.Icon size={18} style={{ flexShrink: 0 }} />
                {!collapsed && <span style={{ whiteSpace: 'nowrap' }}>{item.label}</span>}
              </div>
            )
          })}
        </nav>

        {!collapsed && (
          <div>
            <div style={{ padding: 12, borderTop: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px' }}>
                <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'rgba(180,124,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--violet)', fontSize: '0.78rem', fontWeight: 700, flexShrink: 0 }}>V</div>
                <div>
                  <p style={{ fontSize: '0.78rem', fontWeight: 500, color: 'var(--txt-pri)', margin: 0 }}>Vernon Unzicker</p>
                  <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', margin: 0 }}>Operator</p>
                </div>
              </div>
            </div>
            <div style={{ padding: '8px 12px', borderTop: '1px solid var(--border)' }}>
              <p style={{ fontSize: '0.6rem', color: 'var(--txt-mut)', lineHeight: 1.5, margin: 0 }}>
                Educational AI software. Not professional instruction.
              </p>
              <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                <button onClick={() => nav('compliance')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.58rem', padding: 0, textDecoration: 'underline' }}>Terms</button>
                <button onClick={() => nav('compliance')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.58rem', padding: 0, textDecoration: 'underline' }}>Privacy</button>
                <button onClick={() => nav('landing')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-mut)', fontSize: '0.58rem', padding: 0, textDecoration: 'underline' }}>About</button>
              </div>
            </div>
          </div>
        )}
      </aside>

      {/* Main content */}
      <main style={{
        position: 'fixed', top: 52, bottom: 0, right: 0,
        left: sidebarW, overflowY: 'auto',
        transition: 'left 0.25s ease',
      }}>
        {PageComponent
          ? <PageComponent theme={theme} setTheme={setTheme} setPage={setPage} />
          : <div style={{ padding: 24, color: 'var(--txt-mut)' }}>Page not found.</div>}
      </main>

      <AtlasFAB currentPage={page} />
    </div>
  )
}