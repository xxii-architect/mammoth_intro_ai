import { useState, useEffect, useRef, Suspense, lazy } from 'react'
import {
  LayoutDashboard, Bot, Terminal, FileText, Package, HeartPulse,
  DollarSign, BookOpen, ClipboardList, Settings, PanelLeft, GraduationCap, Brain,
  Activity, Sparkles, CreditCard, ShieldCheck, MessageSquare, LogOut, User,
} from 'lucide-react'

import { useAuth, useIsAdminHost } from './lib/authContext'
import { signOut } from './lib/supabase'
import { api } from './api/client'
import LoginPage from './pages/LoginPage'

const HomePage = lazy(() => import('./pages/HomePage'))
const AgentPage = lazy(() => import('./pages/AgentPage'))
const ChatPage = lazy(() => import('./pages/ChatPage'))
const TerminalPage = lazy(() => import('./pages/TerminalPage'))
const ManualPage = lazy(() => import('./pages/ManualPage'))
const NotesPage = lazy(() => import('./pages/NotesPage'))
const ModulesPage = lazy(() => import('./pages/ModulesPage'))
const HealthPage = lazy(() => import('./pages/HealthPage'))
const LessonsPage = lazy(() => import('./pages/LessonsPage'))
const BuildLogPage = lazy(() => import('./pages/BuildLogPage'))
const LogSalePage = lazy(() => import('./pages/LogSalePage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))
const AtlasTutorPage = lazy(() => import('./pages/AtlasTutorPage'))
const FlashcardsPage = lazy(() => import('./pages/FlashcardsPage'))
const LandingPage = lazy(() => import('./pages/LandingPage'))
const CompliancePage = lazy(() => import('./pages/CompliancePage'))
const PricingPage = lazy(() => import('./pages/PricingPage'))
const DiagnosticsPage = lazy(() => import('./pages/DiagnosticsPage'))
const LessonNotesPage = lazy(() => import('./pages/LessonNotesPage'))
const ProjectsPage = lazy(() => import('./pages/ProjectsPage'))
const AccountPage = lazy(() => import('./pages/AccountPage'))
const CommandLibraryPage = lazy(() => import('./pages/CommandLibraryPage'))
const BetaFeedbackPage = lazy(() => import('./pages/BetaFeedbackPage'))
const ArtifactLibraryPage = lazy(() => import('./pages/ArtifactLibraryPage'))
const TaskInboxPage = lazy(() => import('./pages/TaskInboxPage'))

const ACTIVE_TIME_STORAGE_KEY = 'mammoth.app.active_seconds'

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
  aurora:   {
    '--shell': '#f4f7fb',
    '--card': '#ffffff',
    '--card-hover': '#eaf0f8',
    '--photon': '#2563eb',
    '--cyan': '#0ea5a4',
    '--violet': '#7c3aed',
    '--txt-pri': '#0f172a',
    '--txt-sec': '#475569',
    '--txt-mut': '#64748b',
    '--border': 'rgba(15,23,42,0.12)',
  },
}

const NAV = [
  { section: 'Workspace' },
  { id: 'home',     label: 'Home',        Icon: LayoutDashboard },
  { id: 'account',  label: 'Account',     Icon: User },
  { id: 'agent',    label: 'Agent',       Icon: Bot },
  { id: 'chat',     label: 'Mammoth Mind', Icon: MessageSquare, accent: 'var(--photon)' },
  { id: 'terminal', label: 'Terminal',    Icon: Terminal },
  { id: 'manual',   label: 'Manual',      Icon: BookOpen },
  { id: 'commandlib', label: 'Command Library', Icon: BookOpen, accent: 'var(--cyan)' },

  { section: 'Tools' },
  { id: 'notes',    label: 'Notes',       Icon: FileText },
  { id: 'artifacts', label: 'Artifacts',   Icon: FileText, accent: 'var(--cyan)' },
  { id: 'taskinbox', label: 'Task Inbox', Icon: ClipboardList, accent: 'var(--photon)' },
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
  { id: 'lessonnotes', label: 'Lesson Notes', Icon: FileText, accent: 'var(--cyan)' },
  { id: 'projects',    label: 'Projects',     Icon: ClipboardList, accent: 'var(--photon)' },
  { id: 'betafeedback', label: 'Beta Feedback', Icon: MessageSquare, accent: 'var(--cyan)' },
  { id: 'buildlog',   label: 'Build Log',   Icon: ClipboardList },

  { section: 'System' },
  { id: 'diagnostics', label: 'Diagnostics', Icon: Activity, accent: 'var(--cyan)' },
  { id: 'settings',    label: 'Settings',    Icon: Settings },
]

const PAGE_COMPONENTS = {
  home:        HomePage,
  account:     AccountPage,
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
  lessonnotes: LessonNotesPage,
  projects:    ProjectsPage,
  commandlib:  CommandLibraryPage,
  betafeedback: BetaFeedbackPage,
  artifacts:   ArtifactLibraryPage,
  taskinbox:   TaskInboxPage,
  settings:    SettingsPage,
  landing:     LandingPage,
  pricing:     PricingPage,
  compliance:  CompliancePage,
  diagnostics: DiagnosticsPage,
}

function parseEmailList(raw) {
  return new Set(
    String(raw || '')
      .split(',')
      .map((item) => item.trim().toLowerCase())
      .filter(Boolean),
  )
}

const FRONTEND_ADMIN_EMAILS = parseEmailList(
  import.meta.env.VITE_MAMMOTH_ADMIN_EMAILS || import.meta.env.VITE_MAMMOTH_ADMIN_EMAILS_LIST || '',
)
const FRONTEND_OWNER_EMAILS = new Set([
  ...parseEmailList(import.meta.env.VITE_MAMMOTH_OWNER_EMAILS || ''),
  'truexxiisupply@gmail.com',
])
const FRONTEND_BETA_TESTER_EMAILS = parseEmailList(
  [
    import.meta.env.VITE_MAMMOTH_BETA_TESTER_EMAILS,
    import.meta.env.VITE_MAMMOTH_BETA_EMAILS_LIST,
  ].filter(Boolean).join(','),
)

function compactNavSections(items) {
  const cleaned = []
  for (let i = 0; i < items.length; i += 1) {
    const item = items[i]
    if (!item.section) {
      cleaned.push(item)
      continue
    }
    let hasItems = false
    for (let j = i + 1; j < items.length; j += 1) {
      if (items[j].section) break
      if (items[j].id) {
        hasItems = true
        break
      }
    }
    if (hasItems) cleaned.push(item)
  }
  return cleaned
}

const TIER_RANK = {
  explorer: 0,
  pro: 1,
  enterprise: 2,
  developer: 3,
}

const PAGE_ACCESS_RULES = {
  home: {
    kind: 'tier',
    minimumTier: 'pro',
    badge: 'Paid preview',
    title: 'Workspace Dashboard',
    message: 'This dashboard is reserved for paid tiers while the public learner experience stays focused on lessons, tutoring, and product walkthroughs.',
    highlights: [
      'Workspace-level activity and rollout context',
      'Paid-tier operational snapshots and expansion controls',
      'A clearer view of what a Pro workspace unlocks',
    ],
  },
  agent: {
    kind: 'owner',
    badge: 'Owner only',
    title: 'Agent Workbench',
    message: 'The Agent workbench can execute mutation-capable workflows. It is reserved for the owner account while tester access is being hardened.',
    highlights: [
      'Coordinated planner, reasoner, and coding flows',
      'Mutation-capable execution lanes',
      'Reserved to prevent unintended platform changes during coworker testing',
    ],
  },
  chat: {
    kind: 'tier',
    minimumTier: 'pro',
    badge: 'Paid preview',
    title: 'Mammoth Mind',
    message: 'This richer orchestration chat surface is positioned as a paid upgrade so people can see the value before it becomes a live entitlement.',
    highlights: [
      'Cross-agent orchestration and structured follow-through',
      'Deeper workflow memory than the base learner tutor',
      'An upgrade CTA that keeps the packaging story explicit',
    ],
  },
  terminal: {
    kind: 'owner',
    badge: 'Owner only',
    title: 'Terminal Surface',
    message: 'Terminal commands can impact local platform and device state. Access is currently reserved for the owner account only.',
    highlights: [
      'Direct command execution surface',
      'High-impact workflow capability',
      'Reserved to prevent unintended local/system mutations',
    ],
  },
  notes: {
    kind: 'tier',
    minimumTier: 'pro',
    badge: 'Paid preview',
    title: 'Notes Workspace',
    message: 'Persistent workspace notes are part of the deeper product tier. Showing the page as a preview makes the upgrade path obvious without pretending it is live for Explorer.',
    highlights: [
      'Persistent research and operator note surfaces',
      'Context capture tied to paid workflows',
      'A clearer premium value story than hiding navigation',
    ],
  },
  modules: {
    kind: 'tier',
    minimumTier: 'pro',
    badge: 'Paid preview',
    title: 'Modules Catalog',
    message: 'Module visibility is useful as a product preview even when the workspace has not unlocked the higher tier yet.',
    highlights: [
      'See the module ecosystem before purchasing access',
      'Preview workflow stages and future rollout surfaces',
      'Keep the UI honest about what becomes active after upgrade',
    ],
  },
  health: {
    kind: 'tier',
    minimumTier: 'pro',
    badge: 'Paid preview',
    title: 'Health Signals',
    message: 'Operational health belongs in the paid operator story. Keep the screen visible, but label it clearly as a preview until the workspace tier unlocks it.',
    highlights: [
      'Provider, runtime, and service health snapshots',
      'A premium observability surface for operators',
      'A cleaner packaging story than hiding diagnostics completely',
    ],
  },
  logsale: {
    kind: 'tier',
    minimumTier: 'pro',
    badge: 'Paid preview',
    title: 'Revenue + Sales Logging',
    message: 'Sales logging is positioned as a workspace upgrade so users can understand the commercial layer before it becomes live for their account.',
    highlights: [
      'Business and personal ledger support',
      'Operator-facing revenue workflow previews',
      'A visible upsell surface instead of a hidden menu item',
    ],
  },
  buildlog: {
    kind: 'tier',
    minimumTier: 'pro',
    badge: 'Paid preview',
    title: 'Build Log',
    message: 'Build history and operator execution review are part of the paid workflow package. Let people see the surface, then guide them to upgrade.',
    highlights: [
      'Build trace visibility and execution history',
      'A clearer premium operations story',
      'A lightweight preview that preserves trust',
    ],
  },
  diagnostics: {
    kind: 'tier',
    minimumTier: 'enterprise',
    badge: 'Enterprise preview',
    title: 'Diagnostics Export',
    message: 'Diagnostics and replay bundles are higher-trust operator surfaces. Show the page as part of the enterprise promise, but gate the live export tools.',
    highlights: [
      'Replay bundles and export-grade diagnostics',
      'Enterprise observability and support workflows',
      'A visible roadmap surface for serious buyers',
    ],
  },
  settings: {
    kind: 'owner',
    badge: 'Owner control',
    title: 'Workspace Settings',
    message: 'This page changes entitlements, developer-access, and workspace controls. It is restricted to the owner account for now.',
    highlights: [
      'Tier overrides and developer full access',
      'Workspace account and operator control changes',
      'Reserved for the tenant owner during tester rollout',
    ],
  },
}

function effectiveTier(entitlements) {
  const tier = String(entitlements?.effective_tier || entitlements?.tier || 'explorer').trim().toLowerCase()
  return TIER_RANK[tier] !== undefined ? tier : 'explorer'
}

function meetsTier(entitlements, minimumTier) {
  return TIER_RANK[effectiveTier(entitlements)] >= TIER_RANK[minimumTier]
}

function resolvePageAccess(page, { adminAccess, ownerAccess, betaTesterAccess, entitlements }) {
  const rule = PAGE_ACCESS_RULES[page]
  if (!rule) return null
  if (rule.kind === 'owner') return ownerAccess ? null : rule
  if (adminAccess === true) return null
  if (betaTesterAccess === true && rule.kind === 'tier') return null
  if (rule.kind === 'admin') return rule
  return meetsTier(entitlements, rule.minimumTier) ? null : rule
}

function AccessPreviewPage({ gate, entitlements, setPage }) {
  const tier = effectiveTier(entitlements)
  const tierLabel = tier === 'developer' ? 'developer full access' : tier

  return (
    <div className="page-enter" style={{ padding: '40px 28px 80px', maxWidth: 980, margin: '0 auto' }}>
      <div className="glass-card-solid" style={{ padding: 26, borderLeft: '3px solid var(--amber)', marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
          <ShieldCheck size={18} color="var(--amber)" />
          <span style={{ fontSize: '0.72rem', letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--amber)', fontWeight: 700 }}>
            {gate.badge}
          </span>
        </div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--txt-pri)', margin: '0 0 10px' }}>
          {gate.title}
        </h1>
        <p style={{ fontSize: '0.95rem', color: 'var(--txt-sec)', lineHeight: 1.7, margin: '0 0 18px' }}>
          {gate.message}
        </p>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 18 }}>
          <span style={{ padding: '6px 10px', borderRadius: 999, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.76rem' }}>
            Current access: {tierLabel}
          </span>
          {gate.minimumTier && (
            <span style={{ padding: '6px 10px', borderRadius: 999, border: '1px solid rgba(230,126,34,0.28)', background: 'rgba(230,126,34,0.1)', color: 'var(--amber)', fontSize: '0.76rem' }}>
              Unlocks at: {gate.minimumTier}
            </span>
          )}
          {gate.kind === 'admin' && (
            <span style={{ padding: '6px 10px', borderRadius: 999, border: '1px solid rgba(180,124,255,0.28)', background: 'rgba(180,124,255,0.1)', color: 'var(--violet)', fontSize: '0.76rem' }}>
              Requires owner/admin identity
            </span>
          )}
          {gate.kind === 'owner' && (
            <span style={{ padding: '6px 10px', borderRadius: 999, border: '1px solid rgba(236,201,75,0.28)', background: 'rgba(236,201,75,0.1)', color: 'var(--amber)', fontSize: '0.76rem' }}>
              Requires owner identity
            </span>
          )}
        </div>

        <div style={{ display: 'grid', gap: 10, marginBottom: 22 }}>
          {gate.highlights.map((highlight) => (
            <div key={highlight} style={{ display: 'flex', gap: 8, fontSize: '0.86rem', color: 'var(--txt-sec)', lineHeight: 1.6 }}>
              <span style={{ color: 'var(--amber)' }}>•</span>
              <span>{highlight}</span>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <button
            onClick={() => setPage('pricing')}
            style={{
              padding: '11px 16px',
              borderRadius: 10,
              border: 'none',
              background: 'linear-gradient(90deg, var(--ember), var(--amber))',
              color: '#fff',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            See plans & access
          </button>
          <button
            onClick={() => setPage('landing')}
            style={{
              padding: '11px 16px',
              borderRadius: 10,
              border: '1px solid rgba(255,255,255,0.1)',
              background: 'rgba(255,255,255,0.03)',
              color: 'var(--txt-pri)',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Back to product overview
          </button>
        </div>
      </div>
    </div>
  )
}

function persistArtifactRecord(entry) {
  if (!entry || typeof window === 'undefined') return
  try {
    const raw = localStorage.getItem('mammoth_artifact_library_v1')
    const existing = raw ? JSON.parse(raw) : []
    const next = Array.isArray(existing) ? existing : []
    const item = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      created_at: new Date().toISOString(),
      title: entry.title || 'Saved artifact',
      summary: entry.summary || 'Saved from MammothOS workspace.',
      body: entry.body || '',
      path: entry.path || '',
      source: entry.source || 'workspace',
      format: entry.format || 'txt',
    }
    localStorage.setItem('mammoth_artifact_library_v1', JSON.stringify([item, ...next].slice(0, 30)))
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.warn(`[artifact-library] Failed to persist record: ${message}`)
  }
}

function AtlasFAB({ currentPage, isMobile = false }) {
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [history, setHistory] = useState([])
  const [busy, setBusy] = useState(false)
  const [savingFormat, setSavingFormat] = useState('')
  const [saveStatus, setSaveStatus] = useState('')
  const [mode, setMode] = useState('assistant')
  const [strictGuard, setStrictGuard] = useState(true)
  const bottomRef = useRef(null)
  const isMammothMindSurface = currentPage === 'chat'
  const fabLabel = isMammothMindSurface ? 'Mammoth Mind' : 'ATLAS Tutor'
  const fabSubLabel = isMammothMindSurface ? 'Native multi-agent chat' : 'AI-powered coding mentor'
  const lastAssistantIndex = (() => {
    for (let i = history.length - 1; i >= 0; i -= 1) {
      if (history[i]?.role === 'assistant') return i
    }
    return -1
  })()

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [history])

  const send = async () => {
    if (!input.trim() || busy) return
    const msg = input.trim()
    const lessonSurfacePages = new Set(['lessons', 'atlas', 'flashcards', 'lessonnotes', 'projects'])
    const isLessonSurface = lessonSurfacePages.has(currentPage)
    const selectedText = isLessonSurface && window.getSelection ? window.getSelection().toString().trim().slice(0, 400) : ''
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
      const data = await api(isMammothMindSurface ? '/mammoth/chat' : '/atlas/chat', {
        method: 'POST',
        body: {
          message: msg,
          mode,
          strict_guard: strictGuard,
          regenerate_on_guard: true,
          page_context: {
            current_page: currentPage,
            current_page_type: isLessonSurface ? 'learning' : 'workspace',
            current_page_is_lesson_surface: isLessonSurface,
            selected_text: selectedText,
            lesson: isLessonSurface ? lessonContext : {},
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

  const saveReport = async (message, format) => {
    const ext = format === 'md' ? 'md' : 'txt'
    const stamp = new Date().toISOString().replace(/[:.]/g, '-')
    const filePath = `generated_reports/${isMammothMindSurface ? 'mammoth-mind' : 'atlas-fab'}-report-${stamp}.${ext}`
    const body = ext === 'md'
      ? `# ${fabLabel} Report\n\nGenerated: ${new Date().toLocaleString()}\n\nSource page: ${currentPage}\n\n---\n\n${message}\n`
      : `${fabLabel} Report\nGenerated: ${new Date().toLocaleString()}\nSource page: ${currentPage}\n\n${message}\n`
    setSavingFormat(ext)
    setSaveStatus('')
    try {
      const result = await api('/atlas/apply', {
        method: 'POST',
        body: {
          operation: 'create_file',
          file_path: filePath,
          content: body,
          approval_mode: false,
        },
      })
      persistArtifactRecord({
        title: `${fabLabel} report`,
        summary: `Saved ${ext.toUpperCase()} report from ${currentPage}.`,
        body: message,
        path: result?.result?.path || filePath,
        source: isMammothMindSurface ? 'mammoth-mind' : 'atlas-fab',
        format: ext,
      })
      setSaveStatus(`Saved ${ext.toUpperCase()} report to ${result?.result?.path || filePath}`)
      window.setTimeout(() => setSaveStatus(''), 2600)
    } catch (e) {
      const errMsg = e instanceof Error ? e.message : 'Could not save report'
      setSaveStatus(`[!] ${errMsg}`)
    } finally {
      setSavingFormat('')
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          position: 'fixed', bottom: 24, right: 24, zIndex: 9000,
          width: 64, height: 64, borderRadius: '50%',
          background: isMammothMindSurface ? 'linear-gradient(135deg, var(--photon), var(--cyan))' : 'var(--violet)',
          border: `2px solid ${isMammothMindSurface ? 'rgba(77,166,255,0.45)' : 'rgba(180,124,255,0.5)'}`,
          boxShadow: isMammothMindSurface ? '0 0 20px rgba(77,166,255,0.45)' : '0 0 20px rgba(180,124,255,0.5)',
          animation: 'pulse-violet 2.5s infinite',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#fff', fontSize: '1.3rem',
        }}
        title={fabLabel}
      >
        {isMammothMindSurface ? (
          <MessageSquare size={28} style={{ filter: 'drop-shadow(0 0 8px rgba(255,255,255,0.35))' }} />
        ) : (
          <LogoMark
            src={BRANDING.atlasLogo}
            alt="ATLAS logo"
            fallback="🐘"
            size={42}
            style={{ filter: 'drop-shadow(0 0 8px rgba(180,124,255,0.6))' }}
          />
        )}
      </button>

      {open && (
        <div style={{
          position: 'fixed',
          bottom: isMobile ? 0 : 86,
          right: isMobile ? 0 : 24,
          left: isMobile ? 0 : 'auto',
          zIndex: 8999,
          width: isMobile ? '100vw' : 360,
          height: isMobile ? '92dvh' : 480,
          background: 'var(--card)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(180,124,255,0.3)',
          borderRadius: isMobile ? '16px 16px 0 0' : 16,
          boxShadow: '0 8px 48px rgba(0,0,0,0.6), 0 0 24px rgba(180,124,255,0.15)',
          display: 'flex', flexDirection: 'column',
          overflow: 'hidden',
        }}>
          <div style={{ padding: '12px 16px', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'rgba(180,124,255,0.08)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              {isMammothMindSurface ? (
                <MessageSquare size={24} color="var(--photon)" />
              ) : (
                <LogoMark src={BRANDING.atlasLogo} alt="ATLAS logo" fallback="🐘" size={24} />
              )}
              <div>
                <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600, color: isMammothMindSurface ? 'var(--photon)' : 'var(--violet)' }}>{fabLabel}</p>
                <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--txt-mut)' }}>{fabSubLabel}</p>
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
          {saveStatus && (
            <div style={{
              padding: '8px 12px',
              borderBottom: '1px solid rgba(255,255,255,0.08)',
              color: saveStatus.startsWith('[!]') ? '#fbbf24' : '#86efac',
              background: saveStatus.startsWith('[!]') ? 'rgba(245,158,11,0.08)' : 'rgba(34,197,94,0.08)',
              fontSize: '0.7rem',
              lineHeight: 1.45,
            }}>
              {saveStatus}
            </div>
          )}

          <div style={{ flex: 1, overflowY: 'auto', padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {history.length === 0 && (
              <div style={{ textAlign: 'center', marginTop: 40 }}>
                <div style={{ marginBottom: 8 }}>
                  {isMammothMindSurface ? (
                    <MessageSquare size={44} color="var(--photon)" />
                  ) : (
                    <LogoMark src={BRANDING.atlasLogo} alt="ATLAS logo" fallback="🐘" size={48} />
                  )}
                </div>
                  <p style={{ fontSize: '0.78rem', color: 'var(--txt-mut)', margin: 0 }}>
                    {isMammothMindSurface
                      ? 'Ask Mammoth Mind for quick help, planning, or coding follow-through. Use /research <query> or /web <url> for internet lookups.'
                      : 'Ask ATLAS anything about your current lesson or code. Use /research <query> or /web <url> for internet lookups.'}
                  </p>
                </div>
            )}
            {history.map((msg, i) => {
              const canSave = msg.role === 'assistant' && i === lastAssistantIndex && String(msg.message || '').trim()
              return (
                <div key={i} style={{ alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%' }}>
                  <div style={{
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
                  {canSave && (
                    <div style={{ display: 'flex', gap: 6, marginTop: 6, flexWrap: 'wrap' }}>
                      <button
                        onClick={() => saveReport(msg.message, 'md')}
                        disabled={Boolean(savingFormat)}
                        style={{
                          fontSize: '0.66rem',
                          padding: '5px 8px',
                          borderRadius: 999,
                          border: '1px solid rgba(77,166,255,0.24)',
                          background: 'rgba(77,166,255,0.08)',
                          color: 'var(--photon)',
                          cursor: savingFormat ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {savingFormat === 'md' ? 'Saving .md…' : 'Save .md'}
                      </button>
                      <button
                        onClick={() => saveReport(msg.message, 'txt')}
                        disabled={Boolean(savingFormat)}
                        style={{
                          fontSize: '0.66rem',
                          padding: '5px 8px',
                          borderRadius: 999,
                          border: '1px solid rgba(180,124,255,0.24)',
                          background: 'rgba(180,124,255,0.08)',
                          color: 'var(--violet)',
                          cursor: savingFormat ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {savingFormat === 'txt' ? 'Saving .txt…' : 'Save .txt'}
                      </button>
                    </div>
                  )}
                </div>
              )
            })}
            {busy && (
              <div style={{ alignSelf: 'flex-start', fontSize: '0.78rem', color: 'var(--txt-mut)', padding: '8px 11px', display: 'flex', alignItems: 'center', gap: 8 }}>
                {isMammothMindSurface ? <MessageSquare size={16} color="var(--photon)" /> : <LogoMark src={BRANDING.atlasLogo} alt="ATLAS logo" fallback="🐘" size={16} />}
                {isMammothMindSurface ? 'thinking…' : 'thinking…'}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <div style={{ padding: '10px 12px', borderTop: '1px solid rgba(255,255,255,0.08)', display: 'flex', gap: 8 }}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
              placeholder={isMammothMindSurface ? 'Ask Mammoth Mind... (or /research, /web)' : 'Ask ATLAS... (or /research, /web)'}
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
  const [sidebarOpen, setSidebarOpen] = useState(() => typeof window !== 'undefined' && window.innerWidth >= 768)
  const [isMobile, setIsMobile] = useState(() => typeof window !== 'undefined' && window.innerWidth < 768)
  const [adminAccess, setAdminAccess] = useState(null)
  const [entitlements, setEntitlements] = useState(null)
  const [backendWarning, setBackendWarning] = useState('')
  const { session, user, loading, isGuest } = useAuth()
  const isAdminHost = useIsAdminHost()
  const supabaseConfigured = Boolean(import.meta.env.VITE_SUPABASE_URL && import.meta.env.VITE_SUPABASE_ANON_KEY)
  const userEmail = String(user?.email || '').trim().toLowerCase()
  const fallbackAdminFromEmail = userEmail ? FRONTEND_ADMIN_EMAILS.has(userEmail) : false
  const fallbackOwnerFromEmail = userEmail ? FRONTEND_OWNER_EMAILS.has(userEmail) : false
  const fallbackBetaTesterFromEmail = userEmail ? FRONTEND_BETA_TESTER_EMAILS.has(userEmail) : false
  const ownerAccess = isAdminHost || fallbackOwnerFromEmail
  const betaTesterAccess = fallbackBetaTesterFromEmail
  const canAccessProjectTools = isAdminHost || adminAccess === true
  const visibleNav = compactNavSections(NAV)

  useEffect(() => {
    let alive = true

    if (!session) {
      setAdminAccess(isAdminHost)
      setEntitlements(null)
      setBackendWarning('')
      return () => {
        alive = false
      }
    }

    api('/entitlements')
      .then(data => {
        if (!alive) return
        setEntitlements(data)
        setAdminAccess(isAdminHost || fallbackAdminFromEmail || Boolean(data?.admin_controls_enabled))
        setBackendWarning('')
      })
      .catch((error) => {
        if (!alive) return
        setEntitlements(null)
        setAdminAccess(isAdminHost || fallbackAdminFromEmail)
        const message = String(error?.message || '')
        if (message.includes('Backend returned HTML instead of JSON')) {
          setBackendWarning(message)
        }
      })

    return () => {
      alive = false
    }
  }, [session, isAdminHost, fallbackAdminFromEmail])

  useEffect(() => {
    const vars = THEMES[theme] || THEMES.darker
    Object.entries(vars).forEach(([k, v]) => document.documentElement.style.setProperty(k, v))
  }, [theme])

  useEffect(() => {
    if (typeof window === 'undefined') return undefined

    let lastTick = Date.now()
    const flushActiveTime = () => {
      const now = Date.now()
      const elapsedSeconds = Math.max(0, Math.round((now - lastTick) / 1000))
      lastTick = now

      if (!elapsedSeconds) return
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return

      let current = 0
      try {
        current = Number(window.localStorage.getItem(ACTIVE_TIME_STORAGE_KEY) || 0)
      } catch {
        return
      }
      const next = Number.isFinite(current) ? current + elapsedSeconds : elapsedSeconds
      try {
        window.localStorage.setItem(ACTIVE_TIME_STORAGE_KEY, String(next))
      } catch {
        // Ignore storage writes in restricted browser modes.
      }
    }

    const intervalId = window.setInterval(flushActiveTime, 30000)
    window.addEventListener('beforeunload', flushActiveTime)
    return () => {
      flushActiveTime()
      window.clearInterval(intervalId)
      window.removeEventListener('beforeunload', flushActiveTime)
    }
  }, [])

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
  const gate = session && adminAccess === null ? null : resolvePageAccess(page, { adminAccess, ownerAccess, betaTesterAccess, entitlements })

  return (
    <div style={{ display: 'flex', height: '100dvh', background: 'var(--shell)', color: 'var(--txt-sec)', fontFamily: 'Inter, sans-serif', overflow: 'hidden' }}>

      {/* Mobile sidebar overlay backdrop */}
      {isMobile && sidebarOpen && (
        <div
          onClick={() => setSidebarOpen(false)}
          style={{ position: 'fixed', inset: 0, zIndex: 998, background: 'rgba(0,0,0,0.55)' }}
        />
      )}
      {/* Sidebar */}
      <div style={{
        width: sidebarOpen ? 220 : 0,
        minWidth: sidebarOpen ? 220 : 0,
        transition: 'width 0.2s, min-width 0.2s',
        overflow: 'hidden',
        background: 'var(--card)',
        borderRight: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', flexDirection: 'column',
        ...(isMobile && sidebarOpen ? { position: 'fixed', top: 0, left: 0, height: '100dvh', zIndex: 999 } : {}),
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
          {canAccessProjectTools && (
            <span style={{ marginLeft: 'auto', fontSize: '0.66rem', color: '#b47cff', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
              {isAdminHost ? 'Admin View' : 'Operator Access'}
            </span>
          )}
        </div>
        {backendWarning && (
          <div style={{ padding: '10px 16px', borderBottom: '1px solid rgba(248,113,113,0.25)', background: 'rgba(248,113,113,0.08)', color: '#fecaca', fontSize: '0.76rem', lineHeight: 1.45 }}>
            {backendWarning}
          </div>
        )}
        <div style={{ flex: 1, overflow: 'auto', background: 'var(--shell)' }}>
          <Suspense fallback={<div style={{ padding: 28, color: 'var(--txt-sec)' }}>Loading page…</div>}>
            {gate ? <AccessPreviewPage gate={gate} entitlements={entitlements} setPage={setPage} /> : <PageComponent setPage={setPage} />}
          </Suspense>
        </div>
      </div>

      <AtlasFAB currentPage={page} isMobile={isMobile} />
    </div>
  )
}
