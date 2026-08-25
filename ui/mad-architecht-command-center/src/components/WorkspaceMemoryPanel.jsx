import { useEffect, useState } from 'react'
import { Brain, RefreshCw, UserCircle2, Zap } from 'lucide-react'
import { api } from '../api/client'

function Pill({ children, tone = 'neutral' }) {
  const styles = {
    neutral: { background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', color: 'var(--txt-sec)' },
    info: { background: 'rgba(77,166,255,0.08)', border: '1px solid rgba(77,166,255,0.2)', color: 'var(--photon)' },
    success: { background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)', color: '#22c55e' },
    violet: { background: 'rgba(180,124,255,0.08)', border: '1px solid rgba(180,124,255,0.25)', color: 'var(--violet)' },
  }
  const style = styles[tone] || styles.neutral
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '5px 9px', borderRadius: 999, fontSize: '0.66rem',
      fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', ...style,
    }}>
      {children}
    </span>
  )
}

function MemoryNode({ node }) {
  const timeStr = node.updated_at
    ? new Date(node.updated_at).toLocaleString([], { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
    : null
  return (
    <div style={{
      padding: '10px 12px', borderRadius: 10,
      border: '1px solid rgba(180,124,255,0.18)',
      background: 'linear-gradient(135deg, rgba(180,124,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 4 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--violet)', boxShadow: '0 0 8px var(--violet)', flexShrink: 0 }} />
          <span style={{ color: 'var(--txt-pri)', fontSize: '0.78rem', fontWeight: 700 }}>
            {node.label || node.title || node.id}
          </span>
        </div>
        <span style={{ fontSize: '0.62rem', color: 'rgba(180,124,255,0.6)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {node.type || 'signal'}
        </span>
      </div>
      {timeStr && (
        <div style={{ fontSize: '0.62rem', color: 'var(--txt-mut)', fontFamily: 'JetBrains Mono,monospace' }}>
          {timeStr}
        </div>
      )}
    </div>
  )
}

export default function WorkspaceMemoryPanel() {
  const [workspace, setWorkspace] = useState(null)
  const [learner, setLearner] = useState(null)
  const [loading, setLoading] = useState(true)
  const [memActive, setMemActive] = useState(false)

  const refresh = async () => {
    setLoading(true)
    try {
      const [workspaceRes, learnerRes] = await Promise.all([
        api('/account/workspace'),
        api('/atlas/learner'),
      ])
      setWorkspace(workspaceRes || null)
      setLearner(learnerRes || null)
      setMemActive(true)
      setTimeout(() => setMemActive(false), 1800)
    } catch {
      setWorkspace(null)
      setLearner(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  const account = Array.isArray(workspace?.accounts)
    ? workspace.accounts.find((item) => item.is_active) || workspace.accounts[0]
    : null
  const profile = account?.profile || {}
  const learnerModel = learner?.learner_model || {}
  const graph = learnerModel.memory_graph || {}
  const nodeCount = Array.isArray(graph.nodes) ? graph.nodes.length : 0
  const edgeCount = Array.isArray(graph.edges) ? graph.edges.length : 0
  const recentNodes = Array.isArray(graph.nodes) ? graph.nodes.slice(-4).reverse() : []

  return (
    <div className="glass-card-solid" style={{ padding: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
            <Brain size={15} color="var(--violet)" />
            {memActive && (
              <span style={{
                position: 'absolute', inset: -3, borderRadius: '50%',
                border: '1px solid rgba(180,124,255,0.6)',
                animation: 'memory-ping 1.8s ease-out forwards',
                pointerEvents: 'none',
              }} />
            )}
          </div>
          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700 }}>
            ATLAS Memory
          </div>
          {!loading && (learner || workspace) && (
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              padding: '2px 7px', borderRadius: 999,
              border: '1px solid rgba(34,197,94,0.3)',
              background: 'rgba(34,197,94,0.07)',
              fontSize: '0.6rem', fontWeight: 700,
              color: '#22c55e', letterSpacing: '0.08em',
            }}>
              <span className="live-dot" style={{ width: 5, height: 5, borderRadius: '50%', background: '#22c55e' }} />
              LIVE
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={refresh}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.68rem' }}
        >
          <RefreshCw size={12} /> Refresh
        </button>
      </div>

      {loading ? (
        <div style={{ color: 'var(--txt-mut)', fontSize: '0.75rem' }}>Waking memory engine…</div>
      ) : (
        <div style={{ display: 'grid', gap: 12 }}>
          {/* Profile row */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <UserCircle2 size={16} color="var(--photon)" style={{ flexShrink: 0, marginTop: 2 }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ color: 'var(--txt-pri)', fontSize: '0.84rem', fontWeight: 700 }}>
                {profile.display_name || 'Operator'}
              </div>
              <div style={{ color: 'var(--txt-sec)', fontSize: '0.72rem', lineHeight: 1.55, overflowWrap: 'anywhere' }}>
                {profile.email || 'No workspace email set'}{profile.organization ? ` · ${profile.organization}` : ''}
              </div>
            </div>
          </div>

          {/* Tier + learner pills */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            <Pill tone="info">{workspace?.active_account_id || 'default'} active</Pill>
            <Pill tone="success">{account?.tier || 'explorer'}</Pill>
            {learnerModel.version && <Pill tone="violet">learner v{learnerModel.version}</Pill>}
          </div>

          {/* Memory stats */}
          {(nodeCount > 0 || edgeCount > 0) && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
              {[
                { label: 'Nodes', value: nodeCount, color: 'var(--violet)' },
                { label: 'Edges', value: edgeCount, color: 'var(--photon)' },
                { label: 'Recent', value: recentNodes.length, color: '#22c55e' },
              ].map((stat) => (
                <div key={stat.label} style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)', textAlign: 'center' }}>
                  <div style={{ color: 'var(--txt-mut)', fontSize: '0.6rem', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>{stat.label}</div>
                  <div style={{ color: stat.color, fontSize: '1.1rem', fontWeight: 800, fontFamily: 'JetBrains Mono,monospace' }}>{stat.value}</div>
                </div>
              ))}
            </div>
          )}

          {/* Recent memory nodes */}
          {recentNodes.length > 0 && (
            <div style={{ display: 'grid', gap: 6 }}>
              <div style={{ fontSize: '0.66rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Zap size={11} color="var(--violet)" /> Recent memory signals
              </div>
              {recentNodes.map((node) => (
                <MemoryNode key={node.id || node.label} node={node} />
              ))}
            </div>
          )}

          {/* Learning style pills */}
          {learnerModel.onboarding && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {learnerModel.onboarding.learning_style && <Pill>{learnerModel.onboarding.learning_style}</Pill>}
              {learnerModel.onboarding.preferred_pacing && <Pill>{learnerModel.onboarding.preferred_pacing}</Pill>}
              {Array.isArray(learnerModel.onboarding.focus_areas) && learnerModel.onboarding.focus_areas.slice(0, 3).map((item) => (
                <Pill key={item} tone="violet">{item}</Pill>
              ))}
            </div>
          )}

          {!workspace && !learner && (
            <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(180,124,255,0.15)', background: 'rgba(180,124,255,0.04)', fontSize: '0.75rem', color: 'var(--txt-sec)' }}>
              Memory will hydrate once the backend responds. Sessions are still being remembered.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
