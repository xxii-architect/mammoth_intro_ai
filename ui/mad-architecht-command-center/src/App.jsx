import { useState, useCallback } from 'react'
import {
  LayoutDashboard, Bot, Terminal, FileText, Package, HeartPulse,
  DollarSign, BookOpen, ClipboardList, Settings, PanelLeft, Search,
} from 'lucide-react'

import HomePage     from './pages/HomePage'
import AgentPage    from './pages/AgentPage'
import TerminalPage from './pages/TerminalPage'
import NotesPage    from './pages/NotesPage'
import ModulesPage  from './pages/ModulesPage'
import HealthPage   from './pages/HealthPage'
import LessonsPage  from './pages/LessonsPage'
import BuildLogPage from './pages/BuildLogPage'
import LogSalePage  from './pages/LogSalePage'
import SettingsPage from './pages/SettingsPage'

// Nav definition
const NAV = [
  { section: 'Workspace' },
  { id: 'home',     label: 'Home',      Icon: LayoutDashboard },
  { id: 'agent',    label: 'Agent',     Icon: Bot },
  { id: 'terminal', label: 'Terminal',  Icon: Terminal },
  { section: 'Tools' },
  { id: 'notes',    label: 'Notes',     Icon: FileText },
  { id: 'modules',  label: 'Modules',   Icon: Package },
  { id: 'health',   label: 'Health',    Icon: HeartPulse },
  { id: 'logsale',  label: 'Log Sale',  Icon: DollarSign, accent: 'var(--cyan)' },
  { section: 'Learn' },
  { id: 'lessons',  label: 'Lessons',   Icon: BookOpen },
  { id: 'buildlog', label: 'Build Log', Icon: ClipboardList },
  { section: 'System' },
  { id: 'settings', label: 'Settings',  Icon: Settings },
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
  buildlog: BuildLogPage,
  settings: SettingsPage,
}

export default function App() {
  const [page, setPage] = useState('home')
  const [collapsed, setCollapsed] = useState(false)

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
            return (
              <div key={item.id} onClick={() => nav(item.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '8px 16px',
                  justifyContent: collapsed ? 'center' : 'flex-start',
                  borderRadius: 8, margin: '1px 8px',
                  cursor: 'pointer', transition: 'all 0.15s',
                  borderLeft: `3px solid ${active ? 'var(--photon)' : 'transparent'}`,
                  background: active ? 'rgba(77,166,255,0.1)' : 'transparent',
                  color: item.accent || (active ? 'var(--photon)' : 'var(--txt-sec)'),
                  fontSize: '0.82rem', fontWeight: 500,
                }}>
                <item.Icon size={18} style={{ flexShrink: 0 }} />
                {!collapsed && <span style={{ whiteSpace: 'nowrap' }}>{item.label}</span>}
              </div>
            )
          })}
        </nav>

        {!collapsed && (
          <div style={{ padding: 12, borderTop: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px' }}>
              <div style={{ width: 28, height: 28, borderRadius: '50%', background: 'rgba(180,124,255,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--violet)', fontSize: '0.78rem', fontWeight: 700, flexShrink: 0 }}>V</div>
              <div>
                <p style={{ fontSize: '0.78rem', fontWeight: 500, color: 'var(--txt-pri)', margin: 0 }}>Vernon Unzicker</p>
                <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', margin: 0 }}>Operator</p>
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
        {PageComponent ? <PageComponent /> : <div style={{ padding: 24, color: 'var(--txt-mut)' }}>Page not found.</div>}
      </main>
    </div>
  )
}
