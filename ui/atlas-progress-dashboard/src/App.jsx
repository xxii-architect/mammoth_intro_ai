import { useState } from 'react'
import { SUBSYSTEMS, GROUP_LABELS, STATUS_COLORS, CATEGORY_COLORS } from './config/subsystems'

const stats = [
  { label: 'XP', value: '1,420', detail: '+120 this week' },
  { label: 'Lessons', value: '18', detail: '3 in progress' },
  { label: 'Streak', value: '7 days', detail: 'Keep the momentum' },
  { label: 'Subsystems', value: '21', detail: 'All layers active' },
]

function SubsystemCard({ subsystem, onClick, active }) {
  const catColor = CATEGORY_COLORS[subsystem.category] || '#78c1ff'
  const statusColor = STATUS_COLORS[subsystem.status] || '#78c1ff'
  return (
    <article
      className={`subsystem-card${active ? ' subsystem-card--active' : ''}`}
      onClick={() => onClick(subsystem)}
      style={{ '--cat-color': catColor }}
    >
      <div className="subsystem-card__header">
        <span className="subsystem-card__category" style={{ color: catColor }}>
          {subsystem.category}
        </span>
        <span className="subsystem-card__status" style={{ color: statusColor }}>
          ● {subsystem.status}
        </span>
      </div>
      <h3 className="subsystem-card__name">{subsystem.name}</h3>
      <p className="subsystem-card__desc">{subsystem.description}</p>
      <div className="subsystem-card__footer">
        <span className="subsystem-card__owner">{subsystem.owner}</span>
        <span className="subsystem-card__date">{subsystem.lastUpdated}</span>
      </div>
    </article>
  )
}

function SubsystemDetail({ subsystem, onClose }) {
  if (!subsystem) return null
  const catColor = CATEGORY_COLORS[subsystem.category] || '#78c1ff'
  const statusColor = STATUS_COLORS[subsystem.status] || '#78c1ff'
  return (
    <aside className="subsystem-detail">
      <button className="detail-close" onClick={onClose}>✕ Close</button>
      <p className="eyebrow" style={{ color: catColor }}>{subsystem.category} · {subsystem.group === 'atlas' ? 'ATLAS + MammothOS' : 'Core Systems'}</p>
      <h2>{subsystem.name}</h2>
      <p className="detail-desc">{subsystem.description}</p>
      <dl className="detail-meta">
        <div><dt>Status</dt><dd style={{ color: statusColor }}>● {subsystem.status}</dd></div>
        <div><dt>Owner</dt><dd>{subsystem.owner}</dd></div>
        <div><dt>Last updated</dt><dd>{subsystem.lastUpdated}</dd></div>
        <div><dt>ID</dt><dd>{subsystem.id}</dd></div>
      </dl>
    </aside>
  )
}

export default function App() {
  const [active, setActive] = useState(null)
  const [filter, setFilter] = useState('all')

  const groups = ['core', 'atlas']
  const filtered = (group) =>
    SUBSYSTEMS.filter((s) => s.group === group && (filter === 'all' || s.status === filter))

  return (
    <div className={`app-shell${active ? ' app-shell--detail-open' : ''}`}>
      {/* ── Header ── */}
      <header className="hero-card">
        <div>
          <p className="eyebrow">MammothOS / ATLAS</p>
          <h1>Command Center</h1>
          <p className="hero-copy">21-layer cosmic architecture — all subsystems active</p>
        </div>
        <div className="hero-actions">
          <select
            className="filter-select"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="planned">Planned</option>
            <option value="complete">Complete</option>
          </select>
          <button className="primary-btn">Run a new lesson</button>
        </div>
      </header>

      {/* ── Stats ── */}
      <section className="stats-grid">
        {stats.map((item) => (
          <article className="stat-card" key={item.label}>
            <p className="stat-label">{item.label}</p>
            <h2>{item.value}</h2>
            <p className="stat-detail">{item.detail}</p>
          </article>
        ))}
      </section>

      {/* ── Main area ── */}
      <div className="main-area">
        <div className="subsystems-column">
          {groups.map((group) => (
            <section key={group} className="subsystem-group">
              <h2 className="group-label">{GROUP_LABELS[group]}</h2>
              <div className="subsystem-grid">
                {filtered(group).map((s) => (
                  <SubsystemCard
                    key={s.id}
                    subsystem={s}
                    onClick={setActive}
                    active={active?.id === s.id}
                  />
                ))}
                {filtered(group).length === 0 && (
                  <p className="empty-state">No subsystems match this filter.</p>
                )}
              </div>
            </section>
          ))}
        </div>

        {active && (
          <SubsystemDetail subsystem={active} onClose={() => setActive(null)} />
        )}
      </div>
    </div>
  )
}
