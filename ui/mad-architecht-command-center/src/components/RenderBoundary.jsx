import { Component } from 'react'

export default class RenderBoundary extends Component {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error, info) {
    console.error('MammothOS render failed', error, info)
  }

  render() {
    if (this.state.failed) {
      return (
        <section role="alert" style={{ padding: 28, color: 'var(--txt-pri)', display: 'grid', gap: 14 }}>
          <h2>This view could not load</h2>
          <p>Your saved work is retained. A connection problem or a platform update may have interrupted loading.</p>
          <button type="button" onClick={() => window.location.reload()}>Reload platform</button>
        </section>
      )
    }
    return this.props.children
  }
}
