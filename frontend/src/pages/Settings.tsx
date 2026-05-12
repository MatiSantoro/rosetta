import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Check, Copy, ExternalLink, AlertTriangle, LogOut } from 'lucide-react'
import { getUserProfile, createCheckoutSession, createPortalSession } from '../lib/api'
import { signOut } from '../lib/auth'

// ── Subscription section ────────────────────────────────────────────────────

function SubscriptionSection() {
  const { data: profile, isLoading } = useQuery({
    queryKey: ['user-profile'],
    queryFn: getUserProfile,
    refetchOnWindowFocus: false,
  })
  const [actionLoading, setActionLoading] = useState(false)

  async function handleUpgrade() {
    setActionLoading(true)
    try {
      const { url } = await createCheckoutSession()
      window.location.href = url
    } finally {
      setActionLoading(false)
    }
  }

  async function handleManage() {
    setActionLoading(true)
    try {
      const { url } = await createPortalSession()
      window.location.href = url
    } finally {
      setActionLoading(false)
    }
  }

  if (isLoading) {
    return (
      <div className="card p-5 space-y-3">
        <div className="h-5 w-36 rounded shimmer" />
        <div className="h-4 w-56 rounded shimmer" />
        <div className="h-9 w-48 rounded shimmer" />
      </div>
    )
  }

  const tier = profile?.tier ?? 'free'
  const status = profile?.subscriptionStatus

  return (
    <div className="card p-5">
      <h2 className="text-sm font-semibold uppercase tracking-widest mb-4"
          style={{ color: 'var(--text-faint)' }}>
        Subscription
      </h2>

      {/* Past-due warning */}
      {status === 'past_due' && (
        <div className="flex items-start gap-3 p-3 rounded-xl mb-4"
             style={{ background: '#DC262610', border: '1px solid #DC262630' }}>
          <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" style={{ color: '#DC2626' }} />
          <div>
            <p className="text-sm font-medium" style={{ color: '#DC2626' }}>
              Payment failed — update your payment method
            </p>
            <p className="text-xs mt-0.5" style={{ color: '#DC2626', opacity: 0.75 }}>
              Your Pro access may be suspended soon.
            </p>
          </div>
        </div>
      )}

      {tier === 'free' ? (
        <>
          <div className="flex items-center gap-3 mb-4">
            <div>
              <p className="text-base font-semibold" style={{ color: 'var(--text)' }}>
                Free plan
              </p>
              <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
                5 translations / month
              </p>
            </div>
          </div>

          <div className="p-4 rounded-xl mb-4" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
            <p className="text-xs font-semibold uppercase tracking-widest mb-2"
               style={{ color: 'var(--text-faint)' }}>
              Pro plan includes
            </p>
            <ul className="space-y-1.5">
              {[
                '100 translations per month',
                'Full translation history',
                'API key for CLI & GitHub Actions',
                'Detailed validation reports (cfn-lint, terraform)',
                'Priority support',
              ].map(item => (
                <li key={item} className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
                  <span style={{ color: 'var(--accent)' }}>✓</span>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <button
            onClick={handleUpgrade}
            disabled={actionLoading}
            className="btn btn-primary px-6 py-2.5"
            style={{ boxShadow: '0 4px 16px var(--accent-glow)' }}
          >
            {actionLoading ? (
              <div className="w-4 h-4 rounded-full border-2 border-current border-t-transparent"
                   style={{ animation: 'spin 0.7s linear infinite' }} />
            ) : null}
            Upgrade to Pro — $18/month
          </button>
        </>
      ) : (
        <>
          <div className="flex items-center gap-3 mb-4">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                 style={{ background: 'var(--accent-subtle)', border: '1px solid var(--accent)' }}>
              <span className="text-sm font-bold" style={{ color: 'var(--accent)' }}>✦</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <p className="text-base font-semibold" style={{ color: 'var(--text)' }}>
                  Pro plan
                </p>
                <span
                  className="text-[10px] font-bold px-1.5 py-0.5 rounded-full"
                  style={{ background: 'var(--accent)', color: 'var(--bg)' }}
                >
                  {status === 'past_due' ? 'PAST DUE' : 'ACTIVE'}
                </span>
              </div>
              <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
                100 translations / month
              </p>
            </div>
          </div>

          <ul className="space-y-1.5 mb-4">
            {[
              '100 translations per month',
              'Full translation history',
              'API key for CLI & GitHub Actions',
              'Detailed validation reports',
              'Priority support',
            ].map(item => (
              <li key={item} className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
                <Check size={13} style={{ color: 'var(--accent)', flexShrink: 0 }} />
                {item}
              </li>
            ))}
          </ul>

          <button
            onClick={handleManage}
            disabled={actionLoading}
            className="btn btn-secondary px-5 py-2"
          >
            {actionLoading ? (
              <div className="w-3.5 h-3.5 rounded-full border-2 border-current border-t-transparent"
                   style={{ animation: 'spin 0.7s linear infinite' }} />
            ) : null}
            Manage subscription
          </button>
        </>
      )}
    </div>
  )
}

// ── API Key section ─────────────────────────────────────────────────────────

function ApiKeySection() {
  const { data: profile, isLoading } = useQuery({
    queryKey: ['user-profile'],
    queryFn: getUserProfile,
    refetchOnWindowFocus: false,
  })
  const [copied, setCopied] = useState(false)

  if (isLoading) {
    return (
      <div className="card p-5 space-y-3">
        <div className="h-5 w-24 rounded shimmer" />
        <div className="h-9 w-full rounded shimmer" />
      </div>
    )
  }

  // Only shown for Pro users
  if (profile?.tier !== 'pro') return null

  const apiKey = profile?.apiKey

  function copyKey() {
    if (!apiKey) return
    navigator.clipboard.writeText(apiKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="card p-5">
      <h2 className="text-sm font-semibold uppercase tracking-widest mb-4"
          style={{ color: 'var(--text-faint)' }}>
        API Access
      </h2>

      <p className="text-xs font-medium mb-2" style={{ color: 'var(--text-muted)' }}>
        API Key
      </p>

      {apiKey ? (
        <>
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <input
              readOnly
              value={apiKey}
              className="flex-1 font-mono text-xs px-3 py-2 rounded-lg"
              style={{
                background: 'var(--bg-subtle)',
                border: '1px solid var(--border)',
                color: 'var(--text)',
                outline: 'none',
              }}
            />
            <button
              onClick={copyKey}
              className="btn btn-secondary px-3 py-2 text-xs gap-1.5 flex-shrink-0"
              title="Copy to clipboard"
            >
              {copied ? (
                <>
                  <Check size={12} />
                  Copied!
                </>
              ) : (
                <>
                  <Copy size={12} />
                  Copy
                </>
              )}
            </button>
          </div>
          <p className="text-xs mb-3" style={{ color: 'var(--text-faint)' }}>
            Use this key to authenticate CLI and GitHub Action requests.
          </p>
          <a
            href="#"
            className="inline-flex items-center gap-1 text-xs"
            style={{ color: 'var(--accent)' }}
          >
            View GitHub Action docs
            <ExternalLink size={11} />
          </a>
        </>
      ) : (
        <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--text-muted)' }}>
          <div className="w-3.5 h-3.5 rounded-full border-2 border-current border-t-transparent"
               style={{ animation: 'spin 0.7s linear infinite', flexShrink: 0 }} />
          Generating your API key…
        </div>
      )}
    </div>
  )
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function Settings() {
  const navigate  = useNavigate()
  const [loading, setLoading] = useState(false)

  async function handleSignOut() {
    setLoading(true)
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="animate-fade-in">
      <h1 className="text-2xl font-bold mb-6" style={{ color: 'var(--text)' }}>
        Settings
      </h1>

      <div className="space-y-4">
        <SubscriptionSection />
        <ApiKeySection />

        {/* Sign out — always visible, especially useful on mobile where the sidebar is hidden */}
        <div className="card p-5">
          <h2 className="text-sm font-semibold uppercase tracking-widest mb-4"
              style={{ color: 'var(--text-faint)' }}>
            Account
          </h2>
          <button
            onClick={handleSignOut}
            disabled={loading}
            className="flex items-center gap-2 text-sm transition-colors"
            style={{ color: 'var(--text-muted)' }}
            onMouseEnter={e => (e.currentTarget.style.color = '#DC2626')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
          >
            {loading
              ? <div className="w-4 h-4 rounded-full border-2 border-current border-t-transparent"
                     style={{ animation: 'spin 0.7s linear infinite' }} />
              : <LogOut size={14} />
            }
            Sign out
          </button>
        </div>
      </div>
    </div>
  )
}
