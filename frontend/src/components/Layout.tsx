import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { LayoutDashboard, Plus, LogOut, Zap, ArrowRight, Clock } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { signOut } from '../lib/auth'
import { listJobs, type Job } from '../lib/api'
import ThemeToggle from './ThemeToggle'
import HieroglyphRain from './HieroglyphRain'
import Footer from './Footer'

const navItems = [
  { to: '/',         icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/jobs/new', icon: Plus,            label: 'New Translation' },
]

const FORMATS = [
  { label: 'Terraform',      mono: '.tf',   color: '#7B68EE' },
  { label: 'CloudFormation', mono: '.yaml', color: '#F59E0B' },
  { label: 'SAM',            mono: '.yaml', color: '#10B981' },
  { label: 'CDK',            mono: '.ts+',  color: '#06B6D4' },
]

const DAILY_QUOTA = Number(import.meta.env.VITE_DAILY_QUOTA ?? 3)

const LANG_SHORT: Record<string, string> = {
  terraform: 'TF', cloudformation: 'CFN', sam: 'SAM', cdk: 'CDK',
}
const STATUS_DOT: Record<string, string> = {
  COMPLETED: '#22C55E', COMPLETED_WITH_WARNINGS: '#F59E0B',
  RUNNING: '#3B82F6', FAILED: '#EF4444', AWAITING_UPLOAD: '#6B7280',
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins  = Math.floor(diff / 60_000)
  const hours = Math.floor(diff / 3_600_000)
  const days  = Math.floor(diff / 86_400_000)
  if (mins < 1)   return 'just now'
  if (mins < 60)  return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return 'Yesterday'
  if (days < 7)   return `${days}d ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function RecentJobs({ jobs, navigate }: { jobs: Job[]; navigate: (p: string) => void }) {
  const recent = [...jobs]
    .filter(j => j.status !== 'AWAITING_UPLOAD')
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 4)

  if (recent.length === 0) return null

  return (
    <div className="px-3 pt-3">
      <p className="text-[10px] font-semibold uppercase tracking-widest mb-1.5 px-1"
         style={{ color: 'var(--text-faint)' }}>
        Recent
      </p>
      <div className="space-y-0.5">
        {recent.map(job => {
          const dot = STATUS_DOT[job.status] ?? '#6B7280'
          const src = LANG_SHORT[job.sourceLang] ?? job.sourceLang
          const tgt = LANG_SHORT[job.targetLang] ?? job.targetLang
          return (
            <button
              key={job.jobId}
              onClick={() => navigate(`/jobs/${job.jobId}`)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left
                         transition-all duration-150 group"
              style={{ background: 'transparent' }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--bg-subtle)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
            >
              {/* Status dot */}
              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: dot }} />
              {/* Route */}
              <span className="flex items-center gap-1 flex-1 min-w-0">
                <span className="font-mono text-[10px]" style={{ color: 'var(--text-faint)' }}>{src}</span>
                <ArrowRight size={9} style={{ color: 'var(--text-faint)', flexShrink: 0 }} />
                <span className="font-mono text-[10px]" style={{ color: 'var(--text-muted)' }}>{tgt}</span>
              </span>
              {/* Timestamp */}
              <span className="text-[10px] flex-shrink-0" style={{ color: 'var(--text-faint)' }}>
                {relativeTime(job.createdAt)}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function QuotaCard({ jobs, loading }: { jobs: Job[]; loading: boolean }) {
  const today = new Date().toDateString()
  const usedToday = jobs.filter(j =>
    new Date(j.createdAt).toDateString() === today &&
    j.status !== 'AWAITING_UPLOAD'
  ).length
  const remaining = Math.max(0, DAILY_QUOTA - usedToday)
  const pct = ((DAILY_QUOTA - remaining) / DAILY_QUOTA) * 100

  return (
    <div className="rounded-xl p-3" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium flex items-center gap-1.5" style={{ color: 'var(--text-muted)' }}>
          <Zap size={11} style={{ color: 'var(--accent)' }} />
          Daily usage
        </span>
        <span className="font-mono text-xs font-bold" style={{ color: remaining === 0 ? '#DC2626' : 'var(--accent)' }}>
          {loading ? '…' : `${usedToday}/${DAILY_QUOTA}`}
        </span>
      </div>
      {/* Progress bar */}
      <div className="h-1 rounded-full overflow-hidden" style={{ background: 'var(--border)' }}>
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pct}%`,
            background: remaining === 0 ? '#DC2626' : 'var(--accent)',
          }}
        />
      </div>
      <p className="text-[10px] mt-1.5" style={{ color: 'var(--text-faint)' }}>
        {remaining === 0 ? 'Daily limit reached — resets at midnight UTC' : `${remaining} remaining today`}
      </p>
    </div>
  )
}

function FormatsCard() {
  return (
    <div className="rounded-xl p-3" style={{ background: 'var(--bg-subtle)', border: '1px solid var(--border)' }}>
      <p className="text-[10px] font-semibold uppercase tracking-widest mb-2.5" style={{ color: 'var(--text-faint)' }}>
        Supported formats
      </p>
      <div className="space-y-1.5">
        {FORMATS.map(f => (
          <div key={f.label} className="flex items-center justify-between">
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>{f.label}</span>
            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded" style={{ color: f.color, background: `${f.color}14` }}>
              {f.mono}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Layout() {
  const navigate = useNavigate()

  // Keep jobs fresh in the sidebar so the quota card always reflects reality.
  // Shares the same query key as Dashboard — no duplicate network calls when both are mounted.
  const { data: jobsData, isLoading: jobsLoading } = useQuery({
    queryKey:       ['jobs'],
    queryFn:        () => listJobs(),
    staleTime:      30_000,   // reuse cached data for 30 s
    refetchInterval: 60_000,  // then refresh every minute
  })
  const jobs = jobsData?.items ?? []

  async function handleSignOut() {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen flex" style={{ background: "transparent" }}>
      <HieroglyphRain />

      {/* Sidebar — fixed height, no scroll */}
      <aside
        className="hidden md:flex flex-col w-56 flex-shrink-0 border-r overflow-hidden"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)', height: '100vh', position: 'sticky', top: 0 }}
      >
        {/* Brand */}
        <div className="px-4 py-4 border-b flex-shrink-0 flex items-center gap-3" style={{ borderColor: 'var(--border)' }}>
          <img src="/rosetta-logo.png" alt="Rosetta" className="w-9 h-9 flex-shrink-0"  />
          <div>
            <span className="font-display text-base font-bold tracking-tight block" style={{ color: 'var(--accent)' }}>
              ROSETTA
            </span>
            <p className="text-[10px] font-mono leading-none mt-0.5" style={{ color: 'var(--text-faint)' }}>
              IaC Translator
            </p>
          </div>
        </div>

        {/* Nav — natural height, no flex-1 */}
        <nav className="p-3 space-y-0.5 flex-shrink-0">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'text-[var(--accent)] bg-[var(--accent-subtle)]'
                    : 'text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--bg-subtle)]'
                }`
              }
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Recent jobs — just below nav, natural height */}
        <RecentJobs jobs={jobs} navigate={navigate} />

        {/* Middle — fills remaining space, cards pushed to bottom */}
        <div className="flex-1 p-3 flex flex-col justify-end gap-2.5">
          <QuotaCard jobs={jobs} loading={jobsLoading} />
          <FormatsCard />
        </div>

        {/* Footer — always at the very bottom */}
        <div className="p-3 border-t flex-shrink-0" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center justify-between">
            <button
              onClick={handleSignOut}
              className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-sm
                         text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--bg-subtle)]
                         transition-all duration-150"
            >
              <LogOut size={14} />
              Sign out
            </button>
            <ThemeToggle />
          </div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 flex items-center justify-between px-4 h-14 border-b"
           style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <img src="/rosetta-logo.png" alt="Rosetta" className="w-7 h-7"  />
          <span className="font-display font-bold text-lg" style={{ color: 'var(--accent)' }}>
            ROSETTA
          </span>
        </div>
        <div className="flex items-center gap-1">
          <ThemeToggle />
          <NavLink to="/jobs/new"
            className="btn btn-primary px-3 py-1.5 text-xs">
            + New
          </NavLink>
        </div>
      </div>

      {/* Main content */}
      <main className="flex-1 min-w-0 md:pt-0 pt-14">
        <div className="max-w-4xl mx-auto px-4 md:px-8 py-8 animate-fade-in">
          <Outlet />
        <Footer minimal />
        </div>
      </main>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 border-t flex"
           style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center gap-1 py-3 text-xs font-medium transition-colors ${
                isActive ? 'text-[var(--accent)]' : 'text-[var(--text-muted)]'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
