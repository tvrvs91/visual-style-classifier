import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authApi } from '../api.js'
import { useAuth } from '../AuthContext.jsx'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const onSubmit = async (e) => {
    e.preventDefault()
    setError(''); setLoading(true)
    try {
      const { data } = await authApi.register(email, password)
      login(data.token, data.email)
      navigate('/')
    } catch (err) {
      setError(err.response?.data?.message || 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Create account</h1>
        <form onSubmit={onSubmit}>
          <input type="email" placeholder="Email" value={email}
                 onChange={(e) => setEmail(e.target.value)} required />
          <input type="password" placeholder="Password (min 6 chars)" value={password}
                 onChange={(e) => setPassword(e.target.value)} minLength={6} required />
          <button type="submit" disabled={loading}>{loading ? '…' : 'Register'}</button>
          {error && <div className="form-error">{error}</div>}
        </form>
        <div className="auth-foot">
          Already have an account? <Link to="/login">Log in</Link>
        </div>
      </div>
    </div>
  )
}
