import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Plus, ArrowRight, Clock, ChevronLeft, ChevronRight, ArrowUpDown } from 'lucide-react'
import { listJobs, type Job, type LangKey } from '../lib/api'
import StatusBadge from '../components/StatusBadge'

// ── Types & constants ──────────────────────────────────────────────────────

const LANG_LABELS: Record<LangKey, string> = {
  terraform:      'Terraform',
  cloudformation: 'CloudFormation',
  sam:            'SAM',
  cdk:            'CDK',
}

type SortKey = 'newest' | 'oldest' | 'status'

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: 'newest', label: 'Newest first' },
  { key: 'oldest', label: 'Oldest first' },
  { key: 'status', label: 'By status'   },
]

const STATUS_ORDER: Record<string, number> = {
  RUNNING:                 0,
  COMPLETED:               1,
  COMPLETED_WITH_WARNINGS: 2,
  AWAITING_UPLOAD:         3,
  FAILED:                  4,
}

// ── Helpers ────────────────────────────────────────────────────────────────

/** Format date in the user's local timezone — no conversion needed. */
function formatDate(iso: string) {
  const d = new Date(iso)
  const today     = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)

  const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })

  if (d.toDateString() === today.toDateString())
    return `Today, ${time}`
  if (d.toDateString() === yesterday.toDateString())
    return `Yesterday, ${time}`

  return d.toLocaleDateString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
  })
}

function formatLang(job: Job, side: 'source' | 'target') {
  const lang = side === 'source' ? job.sourceLang : job.targetLang
  const cdk  = side === 'source' ? job.sourceCdkLang : job.targetCdkLang
  return cdk ? `${LANG_LABELS[lang]} (${cdk})` : LANG_LABELS[lang]
}

function sortJobs(items: Job[], key: SortKey): Job[] {
  const copy = [...items]
  switch (key) {
    case 'newest':
      return copy.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    case 'oldest':
      return copy.sort((a, b) => new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime())
    case 'status':
      return copy.sort((a, b) =>
        (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9) ||
        new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
      )
  }
}

// ── Sub-components ─────────────────────────────────────────────────────────

function JobCard({ job }: { job: Job }) {
  const navigate = useNavigate()
  return (
    <div
      className="card p-4 cursor-pointer hover:border-[var(--accent)] transition-all duration-200 group"
      onClick={() => navigate(`/jobs/${job.jobId}`)}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="font-mono text-xs px-2 py-0.5 rounded"
                  style={{ background: 'var(--bg-subtle)', color: 'var(--text-muted)' }}>
              {formatLang(job, 'source')}
            </span>
            <ArrowRight size={12} style={{ color: 'var(--accent)', flexShrink: 0 }} />
            <span className="font-mono text-xs px-2 py-0.5 rounded"
                  style={{ background: 'var(--accent-subtle)', color: 'var(--accent)' }}>
              {formatLang(job, 'target')}
            </span>
          </div>
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <StatusBadge status={job.status} />
              {(job.tokensIn + job.tokensOut) > 0 && (
                <span className="text-xs font-mono" style={{ color: 'var(--text-faint)' }}>
                  {((job.tokensIn + job.tokensOut) / 1000).toFixed(1)}k tokens
                </span>
              )}
            </div>
            <span className="flex items-center gap-1 text-xs flex-shrink-0" style={{ color: 'var(--text-faint)' }}>
              <Clock size={10} />
              {formatDate(job.createdAt)}
            </span>
          </div>
        </div>
        <ArrowRight
          size={14}
          className="flex-shrink-0 mt-1 opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ color: 'var(--accent)' }}
        />
      </div>
    </div>
  )
}

function EmptyState() {
  const navigate = useNavigate()
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-4"
           style={{ background: 'var(--accent-subtle)', border: '1px solid var(--accent)' }}>
        <Plus size={28} style={{ color: 'var(--accent)' }} />
      </div>
      <h2 className="font-display text-xl font-semibold mb-2" style={{ color: 'var(--text)' }}>
        No translations yet
      </h2>
      <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
        Upload your IaC project and convert it to any supported format.
      </p>
      <button onClick={() => navigate('/jobs/new')} className="btn btn-primary">
        <Plus size={15} />
        Start first translation
      </button>
    </div>
  )
}

function SkeletonCard() {
  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className="h-5 w-24 rounded shimmer" />
        <div className="h-3 w-3 rounded shimmer" />
        <div className="h-5 w-32 rounded shimmer" />
      </div>
      <div className="flex gap-3">
        <div className="h-4 w-20 rounded-full shimmer" />
        <div className="h-4 w-28 rounded shimmer" />
      </div>
    </div>
  )
}

// ── Pagination ─────────────────────────────────────────────────────────────

function Pagination({
  page, hasNext, onPrev, onNext, loading,
}: {
  page: number; hasNext: boolean
  onPrev: () => void; onNext: () => void
  loading: boolean
}) {
  return (
    <div className="flex items-center justify-between pt-2">
      <button
        onClick={onPrev}
        disabled={page === 1 || loading}
        className="btn btn-secondary px-3 py-1.5 text-xs gap-1 disabled:opacity-40"
      >
        <ChevronLeft size={13} />
        Previous
      </button>
      <span className="text-xs" style={{ color: 'var(--text-faint)' }}>
        Page {page}
      </span>
      <button
        onClick={onNext}
        disabled={!hasNext || loading}
        className="btn btn-secondary px-3 py-1.5 text-xs gap-1 disabled:opacity-40"
      >
        Next
        <ChevronRight size={13} />
      </button>
    </div>
  )
}

// ── Main ───────────────────────────────────────────────────────────────────

export default function Dashboard() {
  const navigate = useNavigate()

  // Pagination state — keep a stack of tokens for back-navigation
  const [page, setPage]         = useState(1)
  const [tokenStack, setStack]  = useState<(string | undefined)[]>([undefined]) // index 0 = page 1
  const currentToken            = tokenStack[page - 1]

  // Sort state
  const [sort, setSort]         = useState<SortKey>('newest')
  const [sortOpen, setSortOpen] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey:        ['jobs', currentToken],
    queryFn:         () => listJobs(currentToken),
    refetchInterval: 8_000,
    staleTime:       30_000,
  })

  const sorted = useMemo(
    () => sortJobs(data?.items ?? [], sort),
    [data?.items, sort]
  )

  function goNext() {
    const next = data?.nextToken
    if (!next) return
    setStack(s => {
      const copy = [...s]
      copy[page] = next
      return copy
    })
    setPage(p => p + 1)
  }

  function goPrev() {
    if (page <= 1) return
    setPage(p => p - 1)
  }

  const hasNext = !!data?.nextToken

  return (
    <div className="animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="font-display text-2xl font-bold" style={{ color: 'var(--text)' }}>
            Translations
          </h1>
          {data && (
            <p className="text-sm mt-0.5" style={{ color: 'var(--text-muted)' }}>
              {sorted.length} on this page
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Sort dropdown */}
          <div className="relative">
            <button
              onClick={() => setSortOpen(o => !o)}
              className="btn btn-secondary px-3 py-1.5 text-xs gap-1.5"
            >
              <ArrowUpDown size={12} />
              {SORT_OPTIONS.find(o => o.key === sort)?.label}
            </button>
            {sortOpen && (
              <div
                className="absolute right-0 top-full mt-1 rounded-xl overflow-hidden z-10 min-w-[140px]"
                style={{ background: 'var(--surface)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-md)' }}
              >
                {SORT_OPTIONS.map(o => (
                  <button
                    key={o.key}
                    onClick={() => { setSort(o.key); setSortOpen(false) }}
                    className="w-full text-left px-4 py-2.5 text-xs transition-colors"
                    style={{
                      color:      sort === o.key ? 'var(--accent)' : 'var(--text-muted)',
                      background: sort === o.key ? 'var(--accent-subtle)' : 'transparent',
                    }}
                    onMouseEnter={e => { if (sort !== o.key) e.currentTarget.style.background = 'var(--bg-subtle)' }}
                    onMouseLeave={e => { if (sort !== o.key) e.currentTarget.style.background = 'transparent' }}
                  >
                    {o.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          <button onClick={() => navigate('/jobs/new')} className="btn btn-primary text-xs px-3 py-1.5">
            <Plus size={13} />
            New
          </button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="space-y-3">
          {[0, 1, 2, 3].map(i => <SkeletonCard key={i} />)}
        </div>
      ) : error ? (
        <div className="card p-6 text-center" style={{ borderColor: '#DC262630' }}>
          <p className="text-sm" style={{ color: '#DC2626' }}>Failed to load jobs. Check your connection.</p>
        </div>
      ) : sorted.length === 0 ? (
        <EmptyState />
      ) : (
        <>
          <div className="space-y-3">
            {sorted.map((job, i) => (
              <div key={job.jobId} className="animate-slide-up" style={{ animationDelay: `${i * 0.04}s` }}>
                <JobCard job={job} />
              </div>
            ))}
          </div>

          {(page > 1 || hasNext) && (
            <div className="mt-6">
              <Pagination
                page={page}
                hasNext={hasNext}
                onPrev={goPrev}
                onNext={goNext}
                loading={isLoading}
              />
            </div>
          )}
        </>
      )}

      {/* Close sort dropdown on outside click */}
      {sortOpen && (
        <div className="fixed inset-0 z-0" onClick={() => setSortOpen(false)} />
      )}
    </div>
  )
}
