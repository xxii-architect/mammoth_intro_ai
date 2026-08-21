import { useState } from 'react'
import { guestSignInEnabled, signInAsGuest, signInWithEmail, signUpWithEmail } from '../lib/supabase'

export default function LoginPage() {
  const supportEmail = import.meta.env.VITE_MAMMOTH_SUPPORT_EMAIL || 'hello@truexxiisupply.com'
  const privacyEmail = import.meta.env.VITE_MAMMOTH_PRIVACY_EMAIL || 'privacy@truexxiisupply.com'
  const betaTesterEnabled = true
  const [mode, setMode] = useState('signin')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [notice,   setNotice]   = useState('')
  const [loading,  setLoading]  = useState(false)

  const handleSignIn = async (e) => {
    e.preventDefault()
    setError('')
    setNotice('')
    setLoading(true)
    const { error: authError } = await signInWithEmail(email.trim(), password)
    if (authError) setError(authError.message)
    setLoading(false)
  }

  const handleSignUp = async (e, { betaTester = false } = {}) => {
    e.preventDefault()
    setError('')
    setNotice('')
    setLoading(true)
    const normalizedEmail = email.trim().toLowerCase()
    const { data, error: authError } = await signUpWithEmail(normalizedEmail, password, {
      data: {
        beta_tester_requested: betaTester,
      },
    })
    if (authError) {
      setError(authError.message)
      setLoading(false)
      return
    }
    if (data?.session) {
      setNotice(betaTester
        ? 'Beta tester account created. If your email is on the beta tester allowlist, broader safe visibility will unlock after sign-in.'
        : 'Account created successfully.')
    } else {
      setNotice(betaTester
        ? 'Beta tester signup submitted. Check your email to confirm the account if your Supabase project requires confirmation.'
        : 'Signup submitted. Check your email to confirm the account if confirmation is required.')
    }
    setLoading(false)
  }

  const handleSubmit = async (e) => {
    if (mode === 'signup') {
      await handleSignUp(e, { betaTester: false })
      return
    }
    await handleSignIn(e)
  }

  const handleGuestSignIn = async () => {
    setError('')
    setNotice('')
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

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              onClick={() => { setMode('signin'); setError(''); setNotice('') }}
              style={{
                flex: 1,
                padding: '9px 10px',
                borderRadius: 8,
                border: `1px solid ${mode === 'signin' ? 'rgba(180,124,255,0.5)' : 'rgba(255,255,255,0.12)'}`,
                background: mode === 'signin' ? 'rgba(180,124,255,0.14)' : 'rgba(255,255,255,0.04)',
                color: '#fff',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => { setMode('signup'); setError(''); setNotice('') }}
              style={{
                flex: 1,
                padding: '9px 10px',
                borderRadius: 8,
                border: `1px solid ${mode === 'signup' ? 'rgba(0,245,212,0.45)' : 'rgba(255,255,255,0.12)'}`,
                background: mode === 'signup' ? 'rgba(0,245,212,0.1)' : 'rgba(255,255,255,0.04)',
                color: '#fff',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              Sign Up
            </button>
          </div>

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

          {notice && (
            <p style={{ margin: 0, fontSize: '0.76rem', color: 'rgba(45,212,191,0.95)', textAlign: 'center', lineHeight: 1.5 }}>
              {notice}
            </p>
          )}
          {error && (
            <p style={{ margin: 0, fontSize: '0.76rem', color: '#f87171', textAlign: 'center' }}>
              {error}
            </p>
          )}

          {mode === 'signin' ? (
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
          ) : (
            <>
              <button
                type="button"
                disabled={loading}
                onClick={(e) => handleSignUp(e, { betaTester: false })}
                style={{
                  marginTop: 6,
                  padding: '11px',
                  borderRadius: 8,
                  border: 'none',
                  background: loading
                    ? 'rgba(0,245,212,0.25)'
                    : 'linear-gradient(90deg, var(--photon), var(--cyan))',
                  color: '#050608',
                  fontWeight: 700,
                  fontSize: '0.88rem',
                  cursor: loading ? 'not-allowed' : 'pointer',
                  letterSpacing: '0.02em',
                }}
              >
                {loading ? 'Creating account…' : 'Create account'}
              </button>
              {betaTesterEnabled && (
                <button
                  type="button"
                  disabled={loading}
                  onClick={(e) => handleSignUp(e, { betaTester: true })}
                  style={{
                    padding: '11px',
                    borderRadius: 8,
                    border: '1px solid rgba(180,124,255,0.22)',
                    background: 'rgba(180,124,255,0.08)',
                    color: '#fff',
                    fontWeight: 700,
                    fontSize: '0.84rem',
                    cursor: loading ? 'not-allowed' : 'pointer',
                    letterSpacing: '0.02em',
                  }}
                >
                  {loading ? 'Submitting beta signup…' : 'Beta tester sign up'}
                </button>
              )}
            </>
          )}

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

        <div style={{
          marginTop: 16,
          padding: '12px 14px',
          borderRadius: 10,
          border: '1px solid rgba(180,124,255,0.18)',
          background: 'rgba(180,124,255,0.06)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--violet)' }}>
              Tester onboarding
            </span>
          </div>
          <div style={{ color: 'rgba(255,255,255,0.72)', fontSize: '0.73rem', lineHeight: 1.65 }}>
            <p style={{ margin: '0 0 8px' }}>
              Use the email you were invited with, or create a new tester account here. Each tester signs into their own account, so progress and notes stay separate from the owner and other coworkers.
            </p>
            <p style={{ margin: '0 0 8px' }}>
              Beta tester sign up can request broader safe visibility, but it only activates when that email is placed on the beta tester allowlist.
            </p>
            <p style={{ margin: 0 }}>
              For now, the owner keeps Agent, Terminal, and Settings locked so testing stays safe. If something looks odd, start with Lessons or ATLAS Tutor, then use the Manual page for the fastest testing flow.
            </p>
          </div>
        </div>

        <div style={{ marginTop: 16, padding: '10px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}>
          <p style={{ margin: 0, fontSize: '0.68rem', color: 'rgba(255,255,255,0.65)', lineHeight: 1.6, textAlign: 'left' }}>
            This platform is under active development and may change without notice. By signing in, you acknowledge that you are using a prototype environment and agree to comply with all applicable laws, platform policies, and privacy obligations while using it.
          </p>
        </div>

        <div style={{ marginTop: 12, padding: '10px 12px', borderRadius: 8, border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.02)' }}>
          <p style={{ margin: 0, fontSize: '0.68rem', color: 'rgba(255,255,255,0.65)', lineHeight: 1.6 }}>
            Support and partnerships: {supportEmail}
          </p>
          <p style={{ margin: '4px 0 0', fontSize: '0.68rem', color: 'rgba(255,255,255,0.65)', lineHeight: 1.6 }}>
            Privacy requests: {privacyEmail}
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
