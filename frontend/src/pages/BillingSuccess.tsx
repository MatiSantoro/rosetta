import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { CheckCircle } from 'lucide-react'

export default function BillingSuccess() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  // Invalidate the user profile so the sidebar updates immediately
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['user-profile'] })
  }, [queryClient])

  return (
    <div className="min-h-screen flex items-center justify-center px-4"
         style={{ background: 'var(--bg)' }}>
      <div className="max-w-md w-full text-center animate-fade-in">
        {/* Check icon */}
        <div className="flex items-center justify-center mb-6">
          <div
            className="w-20 h-20 rounded-full flex items-center justify-center"
            style={{ background: '#22C55E18', border: '1px solid #22C55E40' }}
          >
            <CheckCircle size={40} style={{ color: '#22C55E' }} />
          </div>
        </div>

        <h1 className="font-display text-3xl font-bold mb-3" style={{ color: 'var(--text)' }}>
          You're now on Pro!
        </h1>
        <p className="text-base mb-8" style={{ color: 'var(--text-muted)' }}>
          Your subscription is active. Enjoy 100 translations/month,
          full history, and API access.
        </p>

        <button
          onClick={() => navigate('/', { replace: true })}
          className="btn btn-primary px-8 py-3"
          style={{ boxShadow: '0 4px 20px var(--accent-glow)' }}
        >
          Go to Dashboard
        </button>
      </div>
    </div>
  )
}
