import { createContext, useContext, useEffect, useState } from 'react'
import { supabase } from './supabase'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(undefined) // undefined = loading
  const [user,    setUser]    = useState(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let alive = true
    let settled = false
    setSession(undefined)
    setError('')
    const fail = failure => {
      if (!alive || settled) return
      settled = true
      console.error('Session initialization failed', failure)
      setError('Could not check your sign-in session. Check your connection and retry.')
    }
    const timer = setTimeout(() => fail(new Error('Session initialization timed out')), 15000)
    Promise.resolve().then(() => supabase.auth.getSession()).then(({ data, error: sessionError }) => {
      if (sessionError) throw sessionError
      if (!alive || settled) return
      settled = true
      clearTimeout(timer)
      setSession(data?.session ?? null)
      setUser(data?.session?.user ?? null)
    }).catch(fail)

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, s) => {
      if (!alive || _event === 'INITIAL_SESSION') return
      settled = true
      clearTimeout(timer)
      setError('')
      setSession(s)
      setUser(s?.user ?? null)
    })

    return () => {
      alive = false
      clearTimeout(timer)
      subscription.unsubscribe()
    }
  }, [attempt])

  return (
    <AuthContext.Provider value={{ session, user, loading: session === undefined, isGuest: Boolean(user?.is_anonymous) }}>
      {error ? (
        <section role="alert" style={{ padding: 28, display: 'grid', gap: 14 }}>
          <h1>Sign-in check interrupted</h1>
          <p>{error}</p>
          <button type="button" onClick={() => setAttempt(value => value + 1)}>Retry sign-in check</button>
        </section>
      ) : children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}

/** True if the current host is admin.truexxiisupply.com */
export function useIsAdminHost() {
  return typeof window !== 'undefined' &&
    window.location.hostname === 'admin.truexxiisupply.com'
}
