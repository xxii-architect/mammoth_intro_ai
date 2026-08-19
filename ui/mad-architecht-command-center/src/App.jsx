import { useState, useEffect, useRef } from 'react'
import {
  LayoutDashboard, Bot, Terminal, FileText, Package, HeartPulse,
  DollarSign, BookOpen, ClipboardList, Settings, PanelLeft, GraduationCap, Brain,
  Activity, Sparkles, CreditCard, ShieldCheck, MessageSquare, LogOut,
} from 'lucide-react'

import { useAuth, useIsAdminHost } from './lib/authContext'
import { signOut } from './lib/supabase'
import { api } from './api/client'
import LoginPage from './pages/LoginPage'

import HomePage        from './pages/HomePage'
import AgentPage       from './pages/AgentPage'
import ChatPage        from './pages/ChatPage'
import TerminalPage    from './pages/TerminalPage'
import ManualPage      from './pages/ManualPage'
import NotesPage       from './pages/NotesPage'
import ModulesPage     from './pages/ModulesPage'
import HealthPage      from './pages/HealthPage'
import LessonsPage     from './pages/LessonsPage'
import BuildLogPage    from './pages/BuildLogPage'
import LogSalePage     from './pages/LogSalePage'
import SettingsPage    from './pages/SettingsPage'
import AtlasTutorPage  from './pages/AtlasTutorPage'
import FlashcardsPage  from './pages/FlashcardsPage'
import LandingPage     from './pages/LandingPage'
import CompliancePage  from './pages/CompliancePage'
import PricingPage     from './pages/PricingPage'
import DiagnosticsPage from './pages/DiagnosticsPage'

const BRANDING = {
  headerLogo: '/branding/mammoth-logo.png',
  atlasLogo: '/branding/atlas-logo.png',
}

function LogoMark({ src, alt, fallback, size = 20, style = {} }) {
  const [errored, setErrored] = useState(false)
  if (errored) {
    return <span style={{ fontSize: `${Math.max(16, Math.floor(size * 0.9))}px`, lineHeight: 1 }}>{fallback}</span>
  }
  return (
    <img
      src={src}
      alt={alt}
      width={size}
      height={size}
      onError={() => setErrored(true)}
      style={{ width: size, height: size, objectFit: 'contain', imageRendering: 'auto', ...style }}
    />
  )
}

const THEMES = {
  darker:   { '--shell': '#050608', '--card': '#0d1117', '--card-hover': '#161b22' },
  dark:     { '--shell': '#0d1117', '--card': '#161b22', '--card-hover': '#1f2937' },
  midnight: { '--shell': '#080c14', '--card': '#0f1520', '--card-hover': '#1a2233' },
}

const NAV = [
  { section: 'Workspace' },
  { id: 'home',     label: 'Home',        Icon: LayoutDashboard },
  { id: 'agent',    label: 'Agent',       Icon: Bot },
  { id: 'chat',     label: 'Chat',        Icon: MessageSquare, accent: 'var(--photon)' },
  { id: 'terminal', label: 'Terminal',    Icon: Terminal },
  { id: 'manual',   label: 'Manual',      Icon: BookOpen },

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
  { id: 'lessons',    label: 'Lessons',     Icon: BookOpen },
  { id: 'atlas',      label: 'ATLAS Tutor', Icon: GraduationCap, accent: 'var(--violet)' },
  { id: 'flashcards', label: 'Flashcards',  Icon: Brain, accent: 'var(--violet)' },
  { id: 'buildlog',   label: 'Build Log',   Icon: ClipboardList },

  { section: 'System' },
  { id: 'diagnostics', label: 'Diagnostics', Icon: Activity, accent: 'var(--cyan)' },
  { id: 'settings',    label: 'Settings',    Icon: Settings },
]

const PAGE_COMPONENTS = {
  home:        HomePage,
  agent:       AgentPage,
  chat:        ChatPage,
  terminal:    TerminalPage,
  manual:      ManualPage,
  notes:       NotesPage,
  modules:     ModulesPage,
  health:      HealthPage,
  logsale:     LogSalePage,
  lessons:     LessonsPage,
  atlas:       AtlasTutorPage,
  flashcards:  FlashcardsPage,
  buildlog:    BuildLogPage,
  settings:    SettingsPage,
  landing:     LandingPage,
  pricing:     PricingPage,
  compliance:  CompliancePage,
  diagnostics: DiagnosticsPage,
}

function AtlasFAB({ currentPage }) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [mode, setMode] = useState('assistant')
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
      const data = await api('/atlas/chat', {
        method: 'POST',
        body: {
          message: msg,
          mode,
          strict_guard: strictGuard,
          regenerate_on_guard: true,
          page_context: {
            current_page: currentPage,
            selected_text: selectedText,
            lesson: lessonContext,
          },
        },
      })
      if (Array.isArray(data.chat_history)) {
        setHistory(data.chat_history)
      } else {
        setHistory(h => [...h, { role: 'assistant', message: data.reply || data.error || 'No response.' }])
      }
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : 'Connection error'
      setHistory(h => [...h, { role: 'assistant', message: '[!] ' + errMsg }])
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
          width: 64, height: 64, borderRadius: '50%',
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
        <LogoMark
          src={BRANDING.atlasLogo}
          alt="ATLAS logo"
          fallback="🐘"
          size={42}
          style={{ filter: 'drop-shadow(0 0 8px rgba(180,124,255,0.6))' }}
        />
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
              <LogoMark src={BRANDING.atlasLogo} alt="ATLAS logo" fallback="🐘" size={24} />
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
              style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 6, color: 'var(--txt-sec)', fontSize: '0.72rem', padding: '3px 6px', cursor: 'pointer' }}
            >
              <option value="assistant">Assistant</option>
              <option value="tutor">Tutor</option>
              <option value="strict">Strict</option>
            </select>
            <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.68rem', color: 'var(--txt-mut)', cursor: 'pointer', userSelect: 'none' }}>
              <input type="checkbox" checked={strictGuard} onChange={e => setStrictGuard(e.target.checked)} style={{ accentColor: 'var(--violet)' }} />
              Guard
            </label>
          </div>

          <div style={{ flex: 1, overflowY: 'auto', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {history.length === 0 && (
              <div style={{ textAlign: 'center', marginTop: 40 }}>
                <div style={{ marginBottom: 8 }}>
                  <LogoMark src={BRANDING.atlasLogo} alt="ATLAS logo" fallback="🐘" size={48} />
                </div>
                <p style={{ fontSize: '0.78rem', color: 'var(--txt-mut)', margin: 0 }}>Ask ATLAS anything about your current lesson or code.</p>
              </div>
            )}
            {history.map((msg, i) => (
              <div key={i} style={{
                alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '85%',
                background: msg.role === 'user' ? 'rgba(180,124,255,0.18)' : 'rgba(255,255,255,0.06)',
                border: msg.role === 'user' ? '1px solid rgba(180,124,255,0.3)' : '1px solid rgba(255,255,255,0.1)',
                borderRadius: msg.role === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                padding: '8px 11px',
                fontSize: '0.78rem',
                color: 'var(--txt-pri)',
                lineHeight: 1.5,
                whiteSpace: 'pre-wrap',
              }}>
                {msg.message}
              </div>
            ))}
            {busy && (
              <div style={{ alignSelf: 'flex-start', fontSize: '0.78rem', color: 'var(--txt-mut)', padding: '8px 11px', display: 'flex', alignItems: 'center', gap: 8 }}>
                <LogoMark src={BRANDING.atlasLogo} alt="ATLAS logo" fallback="🐘" size={16} />
                thinking…
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div style={{ padding: '10px 12px', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', gap: 8 }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
              placeholder="Ask ATLAS..."
              style={{
                flex: 1, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
                borderRadius: 8, color: 'var(--txt-pri)', fontSize: '0.8rem',
                padding: '8px 10px', outline: 'none',
              }}
            />
            <button
              onClick={send}
              disabled={busy}
              style={{
                padding: '8px 14px', borderRadius: 8, border: 'none',
                background: busy ? 'rgba(180,124,255,0.3)' : 'var(--violet)',
                color: '#fff', fontWeight: 700, cursor: busy ? 'not-allowed' : 'pointer', fontSize: '0.8rem',
              }}
            >
              {busy ? '…' : '↑'}
            </button>
          </div>
        </div>
      )}
    </>
  )
}

export default function App() {
  const [page, setPage] = useState('home')
  const [theme, setTheme] = useState('darker')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { session, user, loading, isGuest } = useAuth()
  const isAdminHost = useIsAdminHost()
  const supabaseConfigured = Boolean(import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_ANON_KEY)
  const adminOnlyIds = new Set(['settings', 'diagnostics', 'compliance', 'pricing'])
  const guestOnlyIds = new Set(['landing', 'pricing', 'compliance', 'lessons', 'atlas', 'flashcards', 'manual'])
  const visibleNav = isAdminHost
    ? NAV.filter(item => item.section || adminOnlyIds.has(item.id))
    : isGuest
      ? NAV.filter(item => item.section || guestOnlyIds.has(item.id))
      : NAV

  useEffect(() => {
    const vars = THEMES[theme] || THEMES.darker
    Object.entries(vars).forEach(([k, v]) => document.documentElement.style.setProperty(k, v))
  }, [theme])

  useEffect(() => {
    const visiblePageIds = new Set(visibleNav.filter(item => item.id).map(item => item.id))
    if (!visiblePageIds.has(page)) {
      setPage(isAdminHost ? 'settings' : isGuest ? 'atlas' : 'home')
    }
  }, [isAdminHost, isGuest, page, visibleNav])

  // Loading splash while Supabase checks session
  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#050608', color: 'rgba(255,255,255,0.4)', fontFamily: 'Inter, sans-serif', fontSize: '0.9rem' }}>
        🐘 Loading…
      </div>
    )
  }

  // If Supabase env keys are present but no session → show login
  if (supabaseConfigured && !session) {
    return <LoginPage />
  }

  const PageComponent = PAGE_COMPONENTS[page] || HomePage

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--shell)', color: 'var(--txt-sec)', fontFamily: 'Inter, sans-serif', overflow: 'hidden' }}>

      {/* Sidebar */}
      <div style={{
        width: sidebarOpen ? 220 : 0,
        minWidth: sidebarOpen ? 220 : 0,
        transition: 'width 0.2s, min-width 0.2s',
        overflow: 'hidden',
        background: 'var(--card)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', flexDirection: 'column',
      }}>
        <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <LogoMark src={BRANDING.headerLogo} alt="MammothOS logo" fallback="🐘" size={30} />
          <span style={{ fontWeight: 700, fontSize: '0.88rem', color: 'var(--txt-pri)', letterSpacing: '0.04em' }}>MammothOS</span>
        </div>

        <nav style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
          {visibleNav.map((item, i) => {
            if (item.section) {
              return (
                <p key={i} style={{ margin: '14px 16px 4px', fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--txt-mut)' }}>
                  {item.section}
                </p>
              )
            }
            const { id, label, Icon, accent } = item
            const active = page === id
            return (
              <button
                key={id}
                onClick={() => setPage(id)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: 9,
                  padding: '7px 16px', border: 'none', cursor: 'pointer', textAlign: 'left',
                  background: active ? 'rgba(255,255,255,0.07)' : 'transparent',
                  borderLeft: active ? '2px solid ' + (accent || 'var(--violet)') : '2px solid transparent',
                  color: active ? (accent || 'var(--txt-pri)') : 'var(--txt-sec)',
                  fontSize: '0.82rem', fontWeight: active ? 600 : 400,
                  transition: 'all 0.15s',
                }}
              >
                {Icon && <Icon size={15} style={{ color: active ? (accent || 'var(--violet)') : 'var(--txt-mut)', flexShrink: 0 }} />}
                {label}
              </button>
            )
          })}
        </nav>

        <div style={{ padding: '10px 12px', borderTop: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {/* Signed-in user identity */}
          {user && (
            <div style={{ fontSize: '0.68rem', color: 'rgba(255,255,255,0.3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user.email || (isGuest ? 'Guest session' : 'Signed in')}
            </div>
          )}
          <select
            value={theme}
            onChange={e => setTheme(e.target.value)}
            style={{ width: '100%', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, color: 'var(--txt-sec)', fontSize: '0.72rem', padding: '4px 6px', cursor: 'pointer' }}
          >
            {Object.keys(THEMES).map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          {/* Sign out button only shown when real Supabase session exists */}
          {session && supabaseConfigured && (
            <button
              onClick={async () => { await signOut(); window.location.reload() }}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                padding: '6px 10px', borderRadius: 6, border: '1px solid rgba(255,255,255,0.1)',
                background: 'transparent', color: 'rgba(255,255,255,0.35)', fontSize: '0.72rem',
                cursor: 'pointer',
              }}
            >
              <LogOut size={12} />
              Sign out
            </button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--txt-sec)', fontSize: '1rem', padding: 4 }}
            title="Toggle sidebar"
          >
            <PanelLeft size={18} />
          </button>
          <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--txt-pri)' }}>
            {NAV.find(n => n.id === page)?.label || 'MammothOS'}
          </span>
          {isAdminHost && (
            <span style={{ marginLeft: 'auto', fontSize: '0.66rem', color: '#b47cff', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              Admin View
            </span>
          )}
        </div>
        <div style={{ flex: 1, overflow: 'auto', background: 'var(--shell)' }}>
          <PageComponent setPage={setPage} />
        </div>
      </div>

      <AtlasFAB currentPage={page} />
    </div>
  )
}
