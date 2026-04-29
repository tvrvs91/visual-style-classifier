import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'

const ToastContext = createContext(null)

let counter = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const timers = useRef(new Map())

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
    const tid = timers.current.get(id)
    if (tid) { clearTimeout(tid); timers.current.delete(id) }
  }, [])

  const push = useCallback((kind, message, ttl = 4000) => {
    const id = ++counter
    setToasts((prev) => [...prev, { id, kind, message }])
    timers.current.set(id, setTimeout(() => dismiss(id), ttl))
    return id
  }, [dismiss])

  const api = {
    success: (msg, ttl) => push('success', msg, ttl),
    error: (msg, ttl) => push('error', msg, ttl),
    info: (msg, ttl) => push('info', msg, ttl),
    dismiss,
  }

  useEffect(() => () => {
    timers.current.forEach((t) => clearTimeout(t))
    timers.current.clear()
  }, [])

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-stack" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`} onClick={() => dismiss(t.id)}>
            <span className="toast-dot" />
            <span className="toast-msg">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export const useToast = () => {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx
}
