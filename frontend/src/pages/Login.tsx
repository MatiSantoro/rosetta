import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { isAuthenticated, signInWithGoogle, onAuthEvent } from '../lib/auth'
import ThemeToggle from '../components/ThemeToggle'
import HieroglyphRain from '../components/HieroglyphRain'
import Footer from '../components/Footer'

const EXAMPLES = [
  { from: 'Terraform',      to: 'CloudFormation'   },
  { from: 'CloudFormation', to: 'CDK (TypeScript)'  },
  { from: 'SAM',            to: 'Terraform'         },
  { from: 'CDK (Python)',   to: 'CloudFormation'    },
]

export default function Login() {
  const navigate = useNavigate()
  const [loading, setLoading]   = useState(false)
  const [currIdx, setCurrIdx]   = useState(0)
  const [prevIdx, setPrevIdx]   = useState<number | null>(null)

  useEffect(() => {
    isAuthenticated().then(ok => { if (ok) navigate('/', { replace: true }) })
  }, [navigate])

  useEffect(() => {
    return onAuthEvent(
      () => navigate('/', { replace: true }),
      () => {},
    )
  }, [navigate])

  // True crossfade: old slides out while new slides in simultaneously
  useEffect(() => {
    const t = setInterval(() => {
      setCurrIdx(i => {
        const next = (i + 1) % EXAMPLES.length
        setPrevIdx(i)                          // keep old visible so it can animate out
        setTimeout(() => setPrevIdx(null), 500) // remove after exit animation finishes
        return next
      })
    }, 3500)
    return () => clearInterval(t)
  }, [])

  async function handleSignIn() {
    setLoading(true)
    try { await signInWithGoogle() }
    catch { setLoading(false) }
  }


  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'transparent' }}>
      <HieroglyphRain />
      {/* Top bar — theme toggle only */}
      <div className="flex items-center justify-end px-6 py-4">
        <ThemeToggle />
      </div>

      {/* Hero */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 pb-16">

        {/* Logo mark */}
        <img
          src="/rosetta-logo.png"
          alt="Rosetta"
          className="w-28 h-28 animate-slide-up"
          style={{ filter: 'drop-shadow(0 0 18px var(--accent-glow))' }}
        />

        {/* Brand name — directly below logo */}
        <span
          className="font-display font-black text-2xl tracking-widest mb-8 mt-3 animate-slide-up stagger-1"
          style={{ color: 'var(--accent)', letterSpacing: '0.2em' }}
        >
          ROSETTA
        </span>

        {/* Heading */}
        <h1
          className="font-display text-3xl md:text-4xl font-extrabold text-center leading-[1.08] mb-4 animate-slide-up max-w-[18ch] mx-auto"
          style={{ color: 'var(--text)' }}
        >
          Translate your<br />
          <span style={{ color: 'var(--accent)' }}>infrastructure.</span>
        </h1>

        <p
          className="text-center max-w-sm text-base mb-6 animate-slide-up stagger-1"
          style={{ color: 'var(--text-muted)' }}
        >
          Convert between Terraform, CDK, CloudFormation, and SAM —
          instantly, with Claude AI.
        </p>

        {/* Rotating example pill — old exits while new enters simultaneously */}
        <div
          className="relative overflow-hidden rounded-full mb-8 animate-slide-up stagger-2"
          style={{
            background: 'var(--surface)',
            border: '1px solid var(--border)',
            minWidth: '300px',
            height: '40px',
          }}
        >
          {/* Outgoing — animates out upward */}
          {prevIdx !== null && (
            <span
              key={`out-${prevIdx}`}
              className="absolute inset-0 flex items-center justify-center gap-2 whitespace-nowrap"
              style={{ animation: 'exampleOut 0.45s ease forwards' }}
            >
              <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{EXAMPLES[prevIdx].from}</span>
              <span style={{ color: 'var(--accent)' }}>→</span>
              <span className="font-mono text-xs font-medium" style={{ color: 'var(--accent)' }}>{EXAMPLES[prevIdx].to}</span>
            </span>
          )}

          {/* Incoming — animates in from below */}
          <span
            key={`in-${currIdx}`}
            className="absolute inset-0 flex items-center justify-center gap-2 whitespace-nowrap"
            style={{ animation: 'exampleIn 0.45s ease forwards' }}
          >
            <span className="font-mono text-xs" style={{ color: 'var(--text-muted)' }}>{EXAMPLES[currIdx].from}</span>
            <span style={{ color: 'var(--accent)' }}>→</span>
            <span className="font-mono text-xs font-medium" style={{ color: 'var(--accent)' }}>{EXAMPLES[currIdx].to}</span>
          </span>
        </div>

        {/* CTA */}
        <button
          onClick={handleSignIn}
          disabled={loading}
          className="animate-slide-up stagger-3 flex items-center gap-3 px-6 py-3.5 rounded-xl
                     font-semibold text-sm transition-all duration-200 active:scale-95"
          style={{
            background: loading ? 'var(--accent-subtle)' : 'var(--accent)',
            color: loading ? 'var(--accent)' : 'var(--accent-fg)',
            border: '1px solid var(--accent)',
            boxShadow: loading ? 'none' : '0 4px 16px var(--accent-glow)',
          }}
        >
          {loading ? (
            <>
              <div className="w-4 h-4 rounded-full border-2 border-current border-t-transparent"
                   style={{ animation: 'spin 0.7s linear infinite' }} />
              Redirecting…
            </>
          ) : (
            <>
              {/* Google icon */}
              <svg width="16" height="16" viewBox="0 0 24 24">
                <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              Continue with Google
            </>
          )}
        </button>

        {/* Footer note */}
        <p
          className="mt-6 text-xs text-center animate-slide-up stagger-4"
          style={{ color: 'var(--text-faint)' }}
        >
          3 free translations per day · No credit card required
        </p>
      </div>

      <Footer />
    </div>
  )
}
