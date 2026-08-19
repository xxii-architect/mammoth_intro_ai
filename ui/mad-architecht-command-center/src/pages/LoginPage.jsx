import { useState } from 'react'
import { guestSignInEnabled, signInAsGuest, signInWithEmail } from '../lib/supabase'

export default function LoginPage() {
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const handleSignIn = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    const { error: authError } = await signInWithEmail(email.trim(), password)
    if (authError) setError(authError.message)
    setLoading(false)
  }

  const handleGuestSignIn = async () => {
    setError('')
    setLoading(true)
    const { error: authError } = await signInAsGuest()
    if (authError) {
      const message = authError.message.includes('Anonymous sign-ins are disabled')
        ? 'Guest access is not enabled in Supabase for this deployment.'
        : authError.message
      setError(message)
    }
    setLoading(false)
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: '#050608',
      fontFamily: 'Inter, sans-serif',
    }}>
      <div style={{
        width: '100%',
        maxWidth: 380,
        padding: '40px 32px',
        background: '#0d1117',
        border: '1px solid rgba(255,255,255,0.08)',
        borderRadius: 16,
        boxShadow: '0 8px 48px rgba(0,0,0,0.6)',
      }}>
        {/* Brand */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 10 }}>
            <img
              src="/branding/mammoth-logo.png"
              alt="MammothOS logo"
              style={{ width: 42, height: 42, objectFit: 'contain', display: 'block' }}
            />
          </div>
          <h1 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 700, color: '#fff', letterSpacing: '0.04em' }}>
            MammothOS
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '0.76rem', color: 'rgba(255,255,255,0.4)' }}>
            Command Center · ATLAS access
          </p>
        </div>

        <form onSubmit={handleSignIn} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.72rem', color: 'rgba(255,255,255,0.5)', marginBottom: 5 }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoFocus
              placeholder="you@example.com"
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid rgba(255,255,255,0.12)',
                background: 'rgba(255,255,255,0.05)',
                color: '#fff',
                fontSize: '0.84rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.72rem', color: 'rgba(255,255,255,0.5)', marginBottom: 5 }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              placeholder="••••••••"
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 8,
                border: '1px solid rgba(255,255,255,0.12)',
                background: 'rgba(255,255,255,0.05)',
                color: '#fff',
                fontSize: '0.84rem',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          {error && (
            <p style={{ margin: 0, fontSize: '0.76rem', color: '#f87171', textAlign: 'center' }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              marginTop: 6,
              padding: '11px',
              borderRadius: 8,
              border: 'none',
              background: loading
                ? 'rgba(180,124,255,0.4)'
                : 'linear-gradient(90deg, #7c3aed, #b47cff)',
              color: '#fff',
              fontWeight: 700,
              fontSize: '0.88rem',
              cursor: loading ? 'not-allowed' : 'pointer',
              letterSpacing: '0.02em',
            }}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>

          {guestSignInEnabled && (
            <button
              type="button"
              disabled={loading}
              onClick={handleGuestSignIn}
              style={{
                padding: '11px',
                borderRadius: 8,
                border: '1px solid rgba(255,255,255,0.12)',
                background: 'rgba(255,255,255,0.04)',
                color: '#fff',
                fontWeight: 600,
                fontSize: '0.84rem',
                cursor: loading ? 'not-allowed' : 'pointer',
              }}
            >
              Continue as Guest
            </button>
          )}
        </form>

        <div style={{ marginTop: 16, padding: '10px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}>
          <p style={{ margin: 0, fontSize: '0.68rem', color: 'rgba(255,255,255,0.65)', lineHeight: 1.6, textAlign: 'left' }}>
            This platform is under active development and may change without notice. By signing in, you acknowledge that you are using a prototype environment and agree to comply with all applicable laws, platform policies, and privacy obligations while using it.
          </p>
        </div>

        <p style={{ marginTop: 16, textAlign: 'center', fontSize: '0.7rem', color: 'rgba(255,255,255,0.35)', lineHeight: 1.5 }}>
          {guestSignInEnabled
            ? 'Guest access uses Supabase anonymous auth and should be enabled in your Supabase Auth settings for live trial sessions.'
            : 'Guest access is disabled on this deployment. Sign in with an approved account while hosted access remains under review.'}
        </p>

        <p style={{ marginTop: 24, textAlign: 'center', fontSize: '0.68rem', color: 'rgba(255,255,255,0.25)' }}>
          xxii | architect · MammothOS
        </p>
      </div>
    </div>
  )
}
