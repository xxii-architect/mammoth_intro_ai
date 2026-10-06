import React from 'react'
import ReactDOM from 'react-dom/client'
import RenderBoundary from './components/RenderBoundary'
import './design/tokens.css'
import './index.css'

const root = ReactDOM.createRoot(document.getElementById('root'))
Promise.all([import('./App'), import('./lib/authContext')])
  .then(([{ default: App }, { AuthProvider }]) => {
    root.render(
      <React.StrictMode>
        <RenderBoundary>
          <AuthProvider><App /></AuthProvider>
        </RenderBoundary>
      </React.StrictMode>,
    )
  })
  .catch(error => {
    console.error('MammothOS startup failed', error)
    root.render(
      <section role="alert" style={{ padding: 28, display: 'grid', gap: 14 }}>
        <h1>MammothOS could not start</h1>
        <p>Check your connection and reload. If this continues, the deployment configuration needs attention.</p>
        <button type="button" onClick={() => window.location.reload()}>Reload platform</button>
      </section>,
    )
  })
