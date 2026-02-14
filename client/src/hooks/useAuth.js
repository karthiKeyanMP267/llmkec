import { useEffect, useMemo, useState } from 'react'
import { AUTH_URL } from '../config'

const STORAGE_KEY = 'auth-session'

const loadSession = () => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? JSON.parse(saved) : null
  } catch {
    return null
  }
}

export function useAuth() {
  const [session, setSession] = useState(() => loadSession())
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!session) return
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session))
  }, [session])

  useEffect(() => {
    if (!session) return
    const originalFetch = window.fetch
    window.fetch = (input, init = {}) => {
      const headers = new Headers(init.headers || {})
      headers.set('X-Role', session.role)
      if (Array.isArray(session.allowedServers)) {
        headers.set('X-Allowed-Servers', session.allowedServers.join(','))
      }
      if (session.token && !headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${session.token}`)
      }
      return originalFetch(input, { ...init, headers })
    }
    return () => {
      window.fetch = originalFetch
    }
  }, [session])

  const login = async (email, password) => {
    setLoading(true)
    setStatus('Checking credentials...')
    setError('')
    try {
      const res = await fetch(`${AUTH_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok || !data?.ok) {
        setError(data?.error || 'Invalid credentials')
        return { ok: false }
      }
      const nextSession = { email, role: data.role, allowedServers: data.allowedServers, token: data.token, expiresIn: data.expiresIn }
      setSession(nextSession)
      return { ok: true, session: nextSession }
    } catch (err) {
      setError('Unable to reach auth server')
      console.error(err)
      return { ok: false }
    } finally {
      setLoading(false)
      setStatus('')
    }
  }

  const logout = () => {
    setSession(null)
    setStatus('')
    setError('')
    localStorage.removeItem(STORAGE_KEY)
  }

  return useMemo(
    () => ({ session, status, error, loading, setError, login, logout }),
    [session, status, error, loading, setError, login, logout],
  )
}
