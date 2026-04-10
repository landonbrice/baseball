import { createContext, useContext, useState, useEffect } from 'react'
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || ''
const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null)
  const [coach, setCoach] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      if (session) exchangeToken(session.access_token)
      else setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
      if (session) exchangeToken(session.access_token)
      else { setCoach(null); setLoading(false) }
    })

    return () => subscription.unsubscribe()
  }, [])

  async function exchangeToken(accessToken) {
    try {
      const res = await fetch(`${API_BASE}/api/coach/auth/exchange`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json',
        },
      })
      if (!res.ok) throw new Error(`Auth exchange failed: ${res.status}`)
      const data = await res.json()
      setCoach(data)
    } catch (err) {
      console.error('Auth exchange error:', err)
      setCoach(null)
    } finally {
      setLoading(false)
    }
  }

  async function login(email, password) {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) throw error
  }

  async function logout() {
    await supabase.auth.signOut()
    setCoach(null)
    setSession(null)
  }

  function getAccessToken() {
    return session?.access_token || ''
  }

  return (
    <AuthContext.Provider value={{ coach, session, loading, login, logout, getAccessToken }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useCoachAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useCoachAuth must be used within AuthProvider')
  return ctx
}
