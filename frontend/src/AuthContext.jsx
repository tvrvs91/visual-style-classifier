import { createContext, useContext, useMemo, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [email, setEmail] = useState(() => localStorage.getItem('email'))

  const login = (t, e) => {
    localStorage.setItem('token', t)
    localStorage.setItem('email', e)
    setToken(t); setEmail(e)
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('email')
    setToken(null); setEmail(null)
  }

  const value = useMemo(() => ({ token, email, login, logout, isAuthed: !!token }),
    [token, email])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export const useAuth = () => useContext(AuthContext)
