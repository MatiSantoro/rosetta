import { Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { isAuthenticated, onAuthEvent } from './lib/auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import NewJob from './pages/NewJob'
import JobDetail from './pages/JobDetail'
import AuthCallback from './pages/AuthCallback'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const [checked, setChecked]   = useState(false)
  const [authed, setAuthed]     = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    isAuthenticated().then(ok => {
      setAuthed(ok)
      setChecked(true)
      if (!ok) navigate('/login', { replace: true })
    })
  }, [navigate])

  useEffect(() => {
    return onAuthEvent(
      () => { setAuthed(true); navigate('/', { replace: true }) },
      () => { setAuthed(false); navigate('/login', { replace: true }) },
    )
  }, [navigate])

  if (!checked) return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
      <div className="w-5 h-5 rounded-full border-2 border-[var(--accent)] border-t-transparent"
           style={{ animation: 'spin 0.8s linear infinite' }} />
    </div>
  )
  return authed ? <>{children}</> : null
}

export default function App() {
  return (
    <Routes>
      <Route path="/login"         element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route path="/"         element={<Dashboard />} />
        <Route path="/jobs/new" element={<NewJob />} />
        <Route path="/jobs/:id" element={<JobDetail />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
