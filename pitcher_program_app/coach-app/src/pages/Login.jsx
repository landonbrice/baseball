import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useCoachAuth } from '../hooks/useCoachAuth'

export default function Login() {
  const { login, coach } = useCoachAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Redirect if already logged in
  if (coach) { navigate('/', { replace: true }); return null }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message || 'Login failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-maroon flex items-center justify-center">
      <div className="bg-white rounded-lg shadow-lg p-8 w-full max-w-sm">
        <h1 className="text-xl font-bold text-maroon text-center mb-6">Coach Dashboard</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-charcoal mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm focus:outline-none focus:ring-2 focus:ring-maroon/30"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-charcoal mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full px-3 py-2 border border-cream-dark rounded text-sm focus:outline-none focus:ring-2 focus:ring-maroon/30"
              required
            />
          </div>
          {error && <p className="text-sm text-crimson">{error}</p>}
          <button
            type="submit"
            disabled={submitting}
            className="w-full py-2 bg-maroon text-white rounded font-medium text-sm hover:bg-maroon-light disabled:opacity-50"
          >
            {submitting ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  )
}
