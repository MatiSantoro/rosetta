import { useNavigate } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'

export default function NotFound() {
  const navigate = useNavigate()

  return (
    <div
      className="min-h-screen flex flex-col items-center justify-center text-center px-6"
      style={{ background: 'var(--bg)' }}
    >
      {/* 404 number */}
      <div
        className="font-display font-bold mb-4 select-none"
        style={{ fontSize: 'clamp(80px, 20vw, 140px)', lineHeight: 1, color: 'var(--accent)', opacity: 0.9 }}
      >
        404
      </div>

      {/* Brand label */}
      <div className="flex items-center gap-2 mb-8">
        <img src="/rosetta-logo.png" alt="Rosetta" style={{ width: 24, height: 24, opacity: 0.6 }} />
        <span className="font-display text-sm font-bold tracking-widest" style={{ color: 'var(--text-faint)' }}>
          ROSETTA
        </span>
      </div>

      <h1 className="font-display text-2xl font-bold mb-2" style={{ color: 'var(--text)' }}>
        Page not found
      </h1>
      <p className="text-sm mb-8 max-w-xs leading-relaxed" style={{ color: 'var(--text-muted)' }}>
        The page you're looking for doesn't exist.
      </p>

      <button
        onClick={() => navigate('/', { replace: true })}
        className="btn btn-primary px-6 py-2.5 flex items-center gap-2"
      >
        <ArrowLeft size={15} />
        Back to Dashboard
      </button>
    </div>
  )
}
