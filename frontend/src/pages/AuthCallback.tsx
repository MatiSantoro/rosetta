import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { isAuthenticated, onAuthEvent } from '../lib/auth'

export default function AuthCallback() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Amplify v6 processes the ?code= param automatically on load.
    // Listen for the signedIn Hub event AND poll as a safety net.
    const unsubscribe = onAuthEvent(
      () => navigate('/', { replace: true }),
      () => navigate('/login', { replace: true }),
    )

    // Poll every 500 ms — Hub event may have already fired before this
    // component mounted, so we catch it with a check too.
    const interval = setInterval(async () => {
      try {
        const ok = await isAuthenticated()
        if (ok) navigate('/', { replace: true })
      } catch { /* still waiting */ }
    }, 500)

    // Hard timeout: if still here after 30 s, show an error
    const timeout = setTimeout(() => {
      setError('Sign-in timed out. Please try again.')
    }, 30_000)

    return () => {
      unsubscribe()
      clearInterval(interval)
      clearTimeout(timeout)
    }
  }, [navigate])

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
      <div className="flex flex-col items-center gap-4">
        {error ? (
          <>
            <p className="text-sm font-medium" style={{ color: '#DC2626' }}>{error}</p>
            <button
              onClick={() => navigate('/login', { replace: true })}
              className="btn btn-secondary text-sm"
            >
              Back to login
            </button>
          </>
        ) : (
          <>
            <div className="w-8 h-8 rounded-full border-2 border-[var(--accent)] border-t-transparent"
                 style={{ animation: 'spin 0.8s linear infinite' }} />
            <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Signing you in…</p>
          </>
        )}
      </div>
    </div>
  )
}
