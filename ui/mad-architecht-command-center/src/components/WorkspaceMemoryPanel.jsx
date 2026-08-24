import { useEffect, useState } from 'react'
import { Activity, Brain, RefreshCw, UserCircle2 } from 'lucide-react'
import { api } from '../api/client'

function Pill({ children, tone = 'neutral' }) {
  const styles = {
    neutral: { background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', color: 'var(--txt-sec)' },
    info: { background: 'rgba(77,166,255,0.08)', border: '1px solid rgba(77,166,255,0.2)', color: 'var(--photon)' },
    success: { background: 'rgba(34,197,94,0.08)', border: '1px solid rgba(34,197,94,0.2)', color: '#22c55e' },
  }
  const style = styles[tone] || styles.neutral
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '5px 9px',
      borderRadius: 999,
      fontSize: '0.66rem',
      fontWeight: 700,
      textTransform: 'uppercase',
      letterSpacing: '0.06em',
      ...style,
    }}>
      {children}
    </span>
  )
}

export default function WorkspaceMemoryPanel() {
  const [workspace, setWorkspace] = useState(null)
  const [learner, setLearner] = useState(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    setLoading(true)
    try {
      const [workspaceRes, learnerRes] = await Promise.all([
        api('/account/workspace'),
        api('/atlas/learner'),
      ])
      setWorkspace(workspaceRes || null)
      setLearner(learnerRes || null)
    } catch {
      setWorkspace(null)
      setLearner(null)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  const account = Array.isArray(workspace?.accounts)
    ? workspace.accounts.find((item) => item.is_active) || workspace.accounts[0]
    : null
  const profile = account?.profile || {}
  const learnerModel = learner?.learner_model || {}
  const graph = learnerModel.memory_graph || {}

  return (
    <div className="glass-card-solid" style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Brain size={15} color="var(--violet)" />
          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--txt-sec)', fontWeight: 700 }}>
            Workspace memory
          </div>
        </div>
        <button
          type="button"
          onClick={refresh}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 8px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.68rem' }}
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div style={{ color: 'var(--txt-mut)', fontSize: '0.75rem' }}>Loading workspace memory…</div>
      ) : (
        <div style={{ display: 'grid', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <UserCircle2 size={16} color="var(--photon)" style={{ flexShrink: 0, marginTop: 2 }} />
            <div style={{ minWidth: 0 }}>
              <div style={{ color: 'var(--txt-pri)', fontSize: '0.84rem', fontWeight: 700 }}>
                {profile.display_name || 'Operator'}
              </div>
              <div style={{ color: 'var(--txt-sec)', fontSize: '0.72rem', lineHeight: 1.55, overflowWrap: 'anywhere' }}>
                {profile.email || 'No workspace email set'}{profile.organization ? ` • ${profile.organization}` : ''}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            <Pill tone="info">{workspace?.active_account_id || 'default'} active</Pill>
            <Pill tone="success">{account?.tier || 'explorer'}</Pill>
            <Pill>{learnerModel.version ? `learner v${learnerModel.version}` : 'learner model'}</Pill>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8 }}>
            <div style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.64rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Graph nodes</div>
              <div style={{ color: 'var(--txt-pri)', fontSize: '0.95rem', fontWeight: 800 }}>{Array.isArray(graph.nodes) ? graph.nodes.length : 0}</div>
            </div>
            <div style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.64rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Graph edges</div>
              <div style={{ color: 'var(--txt-pri)', fontSize: '0.95rem', fontWeight: 800 }}>{Array.isArray(graph.edges) ? graph.edges.length : 0}</div>
            </div>
            <div style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <div style={{ color: 'var(--txt-mut)', fontSize: '0.64rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Recent signals</div>
              <div style={{ color: 'var(--txt-pri)', fontSize: '0.95rem', fontWeight: 800 }}>{Array.isArray(graph.nodes) ? graph.nodes.slice(-3).length : 0}</div>
            </div>
          </div>

          {Array.isArray(graph.nodes) && graph.nodes.length > 0 && (
            <div style={{ display: 'grid', gap: 6 }}>
              <div style={{ fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-mut)' }}>
                Recent memory nodes
              </div>
              {graph.nodes.slice(-3).reverse().map((node) => (
                <div key={node.id} style={{ padding: '8px 10px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.025)' }}>
                  <div style={{ color: 'var(--txt-pri)', fontSize: '0.76rem', fontWeight: 700 }}>{node.label || node.title || node.id}</div>
                  <div style={{ color: 'var(--txt-mut)', fontSize: '0.66rem', lineHeight: 1.45, marginTop: 2 }}>
                    {node.type || 'signal'} {node.updated_at ? `• ${new Date(node.updated_at).toLocaleString()}` : ''}
                  </div>
                </div>
              ))}
            </div>
          )}

          {learnerModel.onboarding && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              <Pill>{learnerModel.onboarding.learning_style || 'guided'}</Pill>
              <Pill>{learnerModel.onboarding.preferred_pacing || 'gentle'}</Pill>
              {Array.isArray(learnerModel.onboarding.focus_areas) && learnerModel.onboarding.focus_areas.slice(0, 2).map((item) => (
                <Pill key={item}>{item}</Pill>
              ))}
            </div>
          )}

          {!workspace && !learner && (
            <div style={{ color: 'var(--txt-mut)', fontSize: '0.75rem' }}>
              Workspace context is unavailable right now, but the panel will hydrate when the backend responds.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
