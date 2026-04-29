import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authApi } from '../api.js'
import { useAuth } from '../AuthContext.jsx'
import { useToast } from '../ToastContext.jsx'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()

  const onSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    try {
      const { data } = await authApi.login(email, password)
      login(data.token, data.email)
      toast.success(`Welcome, ${data.email}`)
      navigate('/')
    } catch (err) {
      toast.error(err.response?.data?.message || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1>Log in</h1>
        <form onSubmit={onSubmit}>
          <input type="email" placeholder="Email" value={email}
                 onChange={(e) => setEmail(e.target.value)} required />
          <input type="password" placeholder="Password" value={password}
                 onChange={(e) => setPassword(e.target.value)} required />
          <button type="submit" disabled={loading}>{loading ? '…' : 'Enter'}</button>
        </form>
        <div className="auth-foot">
          No account? <Link to="/register">Register</Link>
        </div>
      </div>
    </div>
  )
}
