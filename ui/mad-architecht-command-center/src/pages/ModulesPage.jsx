import { useState, useEffect, useRef } from 'react'
import { Package, RefreshCw, Globe, FolderOpen, GitBranch, Zap } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../lib/authContext'

const statusColor = {
  active: '#22c55e',
  ready: '#60a5fa',
  loading: '#eab308',
  error: '#ef4444',
  disabled: '#4a5568',
  idle: '#60a5fa',
  needs_setup: '#f97316',
  configured: '#60a5fa',
  connected: '#22c55e',
  needs_context: '#eab308',
  registered: '#94a3b8',
  discovered: '#94a3b8',
  integrated: '#60a5fa',
  unknown: '#94a3b8',
  not_registered: '#f97316',
}

const mcpCategoryIcon = { browser: Globe, repo: FolderOpen, git: GitBranch }

function McpServerCard({ server }) {
  const Icon = mcpCategoryIcon[server.category] || Zap
  const label = server.status || 'unknown'
  const color = statusColor[label] || statusColor.unknown
  return (
    <div className="glass-card-solid" style={{ padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Icon size={16} color="var(--photon)" />
          <p style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--txt-pri)' }}>{server.label}</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 20, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)' }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: color }} />
          <span style={{ fontSize: '0.68rem', fontFamily: 'JetBrains Mono,monospace', color }}>{label}</span>
        </div>
      </div>
      <p style={{ fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.5, marginBottom: 8 }}>{server.description}</p>
      <p style={{ fontSize: '0.74rem', color: 'var(--txt-sec)', marginBottom: 8 }}>
        {server.health_verified ? 'Live MCP handshake verified for this context.' : 'Connection health not verified; an installed launcher is not a working server.'}
        {' '}Access: {server.access || 'unknown'}. {server.requires_repo ? 'Requires an authorized repository selection in Mammoth Mind.' : ''}
      </p>
      {server.tools?.length > 0 && (
        <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 6 }}>
          Tools: {server.tools.join(', ')}
        </p>
      )}
      {server.notes?.length > 0 && (
        <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', fontStyle: 'italic' }}>
          {server.notes[0]}
        </p>
      )}
      {label === 'needs_setup' && (
        <p style={{ fontSize: '0.68rem', color: '#f97316', marginTop: 6 }}>
          Launcher unavailable on the backend: <code>{server.command}</code>. Configure this bridge before using its tools.
        </p>
      )}
    </div>
  )
}

export default function ModulesPage() {
  const auth = useAuth()
  return <ModulesRegistry key={auth?.user?.id || 'local'} />
}

function ModulesRegistry() {
  const [modules, setModules]   = useState([])
  const [mcpServers, setMcpServers] = useState([])
  const [search, setSearch]     = useState('')
  const [loading, setLoading]   = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [errors, setErrors] = useState([])
  const [checkedAt, setCheckedAt] = useState('')
  const requestId = useRef(0)

  const loadModules = async ({ background = false } = {}) => {
    const id = ++requestId.current
    if (!background) setLoading(true)
    setRefreshing(background)
    try {
      const [modulesData, mcpData] = await Promise.allSettled([
        api('/modules'),
        api('/mcp/servers'),
      ])
      if (id !== requestId.current) return
      const failures = []
      if (modulesData.status === 'fulfilled' && Array.isArray(modulesData.value) && modulesData.value.every(item => item && typeof item.name === 'string' && item.id)) {
        setModules(modulesData.value)
      } else {
        setModules([])
        failures.push(`Agent modules unavailable: ${modulesData.status === 'rejected' ? modulesData.reason.message : 'invalid registry response'}`)
      }
      if (mcpData.status === 'fulfilled' && Array.isArray(mcpData.value?.servers)) {
        setMcpServers(mcpData.value.servers)
      } else {
        setMcpServers([])
        failures.push(`MCP bridges unavailable: ${mcpData.status === 'rejected' ? mcpData.reason.message : 'invalid bridge response'}`)
      }
      setErrors(failures)
      setCheckedAt(new Date().toLocaleTimeString())
    } finally {
      if (id === requestId.current) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }

  useEffect(() => {
    loadModules()
    const timer = setInterval(() => loadModules({ background: true }), 30000)
    return () => { clearInterval(timer); requestId.current += 1 }
  }, [])

  const filtered = modules.filter(m =>
    m.name.toLowerCase().includes(search.toLowerCase()) ||
    (m.description || '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
          <Package size={20} color="var(--photon)" /> Modules Registry
        </h1>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 10 }}>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search modules…"
            style={{ padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--txt-pri)', fontSize: '0.85rem', outline: 'none', width: 200 }} />
          <button
            disabled={refreshing || loading}
            onClick={() => loadModules({ background: true })}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', padding: '7px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer' }}
          >
            <RefreshCw size={14} style={{ opacity: refreshing ? 0.6 : 1 }} />
            {refreshing ? 'Refreshing' : 'Refresh'}
          </button>
        </div>
        {errors.map(error => <div role="alert" key={error} style={{ color: '#f87171', padding: 12 }}>{error}</div>)}
        <p style={{ color: 'var(--txt-sec)', fontSize: '0.76rem', marginBottom: 16 }}>
          Backend snapshots refresh every 30 seconds{checkedAt ? ` · Checked ${checkedAt}` : ''}. Registered or integrated does not mean running or health-verified.
        </p>
      </div>

      {/* MCP Servers section */}
      {mcpServers.length > 0 && (
        <div style={{ marginBottom: 28 }}>
          <h2 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Zap size={14} color="var(--photon)" /> MCP Tool Bridges
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 12 }}>
            {mcpServers.map(s => <McpServerCard key={s.id} server={s} />)}
          </div>
        </div>
      )}

      {loading ? (
        <div style={{ color: 'var(--txt-mut)', fontSize: '0.9rem' }}>Loading modules…</div>
      ) : (
        <>
          <h2 style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Package size={14} color="var(--photon)" /> Agent Modules
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(280px,1fr))', gap: 12 }}>
            {filtered.map(m => {
              const st = m.status
              return (
                <div key={m.id} className="glass-card-solid" style={{ padding: 16 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                    <div>
                      <p style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--txt-pri)' }}>{m.name}</p>
                      <p style={{ fontSize: '0.72rem', fontFamily: 'JetBrains Mono,monospace', color: 'var(--txt-mut)', marginTop: 2 }}>{m.version}</p>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 10px', borderRadius: 20, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)' }}>
                      <div style={{ width: 6, height: 6, borderRadius: '50%', background: statusColor[st] || '#4a5568' }} />
                      <span style={{ fontSize: '0.68rem', fontFamily: 'JetBrains Mono,monospace', color: statusColor[st] || '#4a5568' }}>{st === 'active' && m.observed_active ? 'recent activity' : st}</span>
                    </div>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--txt-sec)', lineHeight: 1.5, marginBottom: 8 }}>{m.description}</p>
                  {m.workflow_ready !== undefined && (
                    <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 10 }}>
                      Workflow: {m.workflow_path === 'mammoth_chat' ? 'wired into Mammoth Mind' : m.workflow_path === 'atlas_lesson' ? 'wired into ATLAS lesson flow' : m.workflow_stage === 'routed' ? 'wired into plan/execute' : m.workflow_stage === 'autonomous' ? 'wired into autonomous flow' : 'registered only'}
                    </p>
                  )}
                  {m.capabilities?.length > 0 && (
                    <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 8 }}>
                      Capabilities: {m.capabilities.join(', ')}
                    </p>
                  )}
                  {m.quality_tier && (
                    <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 8 }}>
                      Quality: {m.quality_tier} ({m.quality_score}/100){m.interface_mode ? ` • ${m.interface_mode}` : ''}
                    </p>
                  )}
                  {(m.last_activity_at || m.last_heartbeat_at) && (
                    <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)', marginBottom: 8 }}>
                      Runtime: {m.observed_active ? 'active signal observed' : 'no recent active signal'}
                      {m.last_activity_at ? ` • activity ${new Date(m.last_activity_at).toLocaleString()}` : ''}
                      {m.last_heartbeat_at ? ` • heartbeat ${new Date(m.last_heartbeat_at).toLocaleString()}` : ''}
                    </p>
                  )}
                  {m.quality_findings?.length > 0 && (
                    <p style={{ fontSize: '0.68rem', color: 'var(--txt-mut)' }}>
                      Notes: {m.quality_findings.join(' ')}
                    </p>
                  )}
                </div>
              )
            })}
            {filtered.length === 0 && <div style={{ color: 'var(--txt-mut)', fontSize: '0.9rem' }}>No modules match.</div>}
          </div>
        </>
      )}
    </div>
  )
}