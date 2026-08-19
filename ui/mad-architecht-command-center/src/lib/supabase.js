import { createClient } from '@supabase/supabase-js'

const url     = import.meta.env.VITE_SUPABASE_URL      || ''
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || ''
export const guestSignInEnabled = String(import.meta.env.VITE_ENABLE_GUEST_SIGN_IN || '').toLowerCase() === 'true'

export const supabase = createClient(url, anonKey, {
  auth: {
    persistSession:     true,
    autoRefreshToken:   true,
    detectSessionInUrl: true,
  },
})

export async function getSession() {
  const { data } = await supabase.auth.getSession()
  return data?.session ?? null
}

export async function getAccessToken() {
  const session = await getSession()
  return session?.access_token ?? null
}

export async function signInWithEmail(email, password) {
  return supabase.auth.signInWithPassword({ email, password })
}

export async function signInAsGuest() {
  if (!guestSignInEnabled) {
    return { data: null, error: new Error('Guest access is disabled for this deployment.') }
  }
  return supabase.auth.signInAnonymously()
}

export async function signOut() {
  return supabase.auth.signOut()
}
