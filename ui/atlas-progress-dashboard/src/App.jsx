const stats = [
  { label: 'XP', value: '1,420', detail: '+120 this week' },
  { label: 'Lessons', value: '18', detail: '3 in progress' },
  { label: 'Streak', value: '7 days', detail: 'Keep the momentum' },
]

const activity = [
  { title: 'ATLAS lesson passed', subtitle: 'Python functions', time: '12m ago' },
  { title: 'New prompt logged', subtitle: 'UI scaffold requested', time: '27m ago' },
  { title: 'Sandbox run succeeded', subtitle: 'Generated code validated', time: '1h ago' },
]

const lessons = [
  { title: 'Adaptive quiz', status: 'Ready' },
  { title: 'Code review loop', status: 'In progress' },
  { title: 'Progress dashboard', status: 'Next' },
]

export default function App() {
  return (
    <div className="app-shell">
      <header className="hero-card">
        <div>
          <p className="eyebrow">MammothOS / ATLAS</p>
          <h1>ATLAS Progress Dashboard</h1>
          <p className="hero-copy">
            Generated from the prompt: <strong>ATLAS progress dashboard</strong>
          </p>
        </div>
        <button className="primary-btn">Run a new lesson</button>
      </header>

      <section className="stats-grid">
        {stats.map((item) => (
          <article className="stat-card" key={item.label}>
            <p className="stat-label">{item.label}</p>
            <h2>{item.value}</h2>
            <p className="stat-detail">{item.detail}</p>
          </article>
        ))}
      </section>

      <section className="content-grid">
        <article className="panel">
          <div className="panel-header">
            <h3>Recent activity</h3>
            <span>Live</span>
          </div>
          <ul className="stack-list">
            {activity.map((item) => (
              <li key={item.title}>
                <div>
                  <strong>{item.title}</strong>
                  <p>{item.subtitle}</p>
                </div>
                <span>{item.time}</span>
              </li>
            ))}
          </ul>
        </article>

        <article className="panel">
          <div className="panel-header">
            <h3>Next lessons</h3>
            <span>Suggested</span>
          </div>
          <ul className="stack-list">
            {lessons.map((item) => (
              <li key={item.title}>
                <div>
                  <strong>{item.title}</strong>
                </div>
                <span>{item.status}</span>
              </li>
            ))}
          </ul>
        </article>
      </section>
    </div>
  )
}
