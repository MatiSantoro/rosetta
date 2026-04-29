import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download, AlertCircle, CheckCircle, ArrowRight, Copy, Check } from 'lucide-react'
import { useState } from 'react'
import { getJob, getDownloadUrl, type Job, type LangKey } from '../lib/api'
import StatusBadge from '../components/StatusBadge'

// ── Constants ───────────────────────────────────────────────────────────────

const LANG_LABELS: Record<LangKey, string> = {
  terraform:      'Terraform',
  cloudformation: 'CloudFormation',
  sam:            'SAM',
  cdk:            'CDK',
}

const PIPELINE_STEPS = [
  { key: 'PREFLIGHT',   label: 'Preflight',    desc: 'Extracting & classifying files' },
  { key: 'COMPAT_CHECK',label: 'Compatibility', desc: 'Checking SAM serverless rules' },
  { key: 'DEP_MAP',     label: 'Analysis',     desc: 'Building dependency graph' },
  { key: 'TRANSLATE',   label: 'Translation',  desc: 'Calling Claude Sonnet' },
  { key: 'VALIDATE',    label: 'Validation',   desc: 'Linting output files' },
  { key: 'DONE',        label: 'Done',         desc: 'Packaging results' },
]

// ── Helper ──────────────────────────────────────────────────────────────────

function stepIndex(step?: string): number {
  if (!step) return -1
  return PIPELINE_STEPS.findIndex(s => s.key === step)
}

/** Map internal/AWS error messages to user-friendly copy. */
function friendlyError(raw?: string): string {
  if (!raw) return 'An unexpected error occurred. Please try again.'

  const r = raw.toLowerCase()
  if (r.includes('no valid iac files'))
    return 'No supported IaC files were found in your zip. Make sure it contains .tf, .yaml, .json, .ts, .py, .java, .cs, or .go files.'
  if (r.includes('quota') || r.includes('429') || r.includes('limit'))
    return "You've reached your daily translation limit. Try again tomorrow."
  if (r.includes('too large') || r.includes('size'))
    return 'Your zip file exceeds the 50 MB limit. Try removing large binary files before zipping.'
  if (r.includes('serverless') || r.includes('compatible'))
    return 'Some resources in your template are not serverless-compatible. SAM requires all resources to use serverless AWS services.'
  if (r.includes('timeout') || r.includes('timed out'))
    return 'The translation took too long and was stopped. Try with a smaller project or fewer files.'
  if (r.includes('upload not found') || r.includes('no such key'))
    return 'Your file upload could not be found. Please start a new translation and upload again.'

  // Generic fallback — never expose raw AWS/internal messages
  return 'Something went wrong during translation. Please try again. If the problem persists, contact support.'
}

function isTerminal(status: Job['status']) {
  return ['COMPLETED', 'COMPLETED_WITH_WARNINGS', 'FAILED'].includes(status)
}

// ── Pipeline visualization ──────────────────────────────────────────────────

function PipelineSteps({ job }: { job: Job }) {
  const current = stepIndex(job.step)
  const failed  = job.status === 'FAILED'

  return (
    <div className="space-y-1">
      {PIPELINE_STEPS.map((s, i) => {
        const done    = i < current || job.status === 'COMPLETED' || job.status === 'COMPLETED_WITH_WARNINGS'
        const active  = i === current && !isTerminal(job.status)
        const errored = failed && i === current

        return (
          <div key={s.key} className="flex items-center gap-3 py-2 px-3 rounded-lg transition-all duration-300"
               style={{ background: active ? 'var(--accent-subtle)' : errored ? '#DC262610' : 'transparent' }}>

            {/* Icon */}
            <div className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-500"
                 style={{
                   background: done    ? 'var(--accent)' :
                               active  ? 'var(--accent)' :
                               errored ? '#DC2626'       : 'var(--bg-subtle)',
                   boxShadow: active ? '0 0 12px var(--accent-glow)' : 'none',
                 }}>
              {done ? (
                <Check size={11} color="var(--accent-fg)" />
              ) : errored ? (
                <span className="text-[9px] font-bold text-white">✗</span>
              ) : active ? (
                <div className="w-2 h-2 rounded-full bg-white"
                     style={{ animation: 'glowPulse 1s ease-in-out infinite' }} />
              ) : (
                <div className="w-2 h-2 rounded-full" style={{ background: 'var(--text-faint)' }} />
              )}
            </div>

            {/* Text */}
            <div className="flex-1 min-w-0">
              <span className="text-sm font-medium"
                    style={{ color: done || active ? 'var(--text)' : 'var(--text-faint)' }}>
                {s.label}
              </span>
              {active && (
                <span className="ml-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                  {s.desc}
                </span>
              )}
            </div>

            {/* Connector line */}
            {i < PIPELINE_STEPS.length - 1 && (
              <div className="absolute" /> // visual handled by spacing
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Download button ─────────────────────────────────────────────────────────

function DownloadButton({ jobId }: { jobId: string }) {
  const [loading, setLoading] = useState(false)

  async function download() {
    setLoading(true)
    try {
      const { downloadUrl } = await getDownloadUrl(jobId)
      const a = document.createElement('a')
      a.href = downloadUrl
      a.download = `rosetta-${jobId.slice(0, 8)}.zip`
      a.click()
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={download}
      disabled={loading}
      className="btn btn-primary px-6 py-3"
      style={{ boxShadow: '0 4px 20px var(--accent-glow)' }}
    >
      {loading ? (
        <div className="w-4 h-4 rounded-full border-2 border-current border-t-transparent"
             style={{ animation: 'spin 0.7s linear infinite' }} />
      ) : (
        <Download size={16} />
      )}
      Download result
    </button>
  )
}

// ── Job ID copy ─────────────────────────────────────────────────────────────

function CopyId({ id }: { id: string }) {
  const [copied, setCopied] = useState(false)
  function copy() {
    navigator.clipboard.writeText(id)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button onClick={copy} className="flex items-center gap-1.5 group">
      <span className="font-mono text-xs" style={{ color: 'var(--text-faint)' }}>
        {id.slice(0, 8)}…
      </span>
      {copied
        ? <Check size={10} style={{ color: 'var(--accent)' }} />
        : <Copy size={10} className="opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ color: 'var(--text-faint)' }} />}
    </button>
  )
}

// ── Main component ──────────────────────────────────────────────────────────

export default function JobDetail() {
  const { id }    = useParams<{ id: string }>()
  const navigate  = useNavigate()

  const { data: job, isLoading } = useQuery({
    queryKey:       ['job', id],
    queryFn:        () => getJob(id!),
    refetchInterval: (q) =>
      q.state.data && isTerminal(q.state.data.status) ? false : 3000,
    enabled: !!id,
  })

  if (isLoading) return (
    <div className="animate-fade-in space-y-4">
      <div className="h-8 w-32 rounded shimmer" />
      <div className="card p-5 space-y-3">
        {[0,1,2,3].map(i => (
          <div key={i} className="flex items-center gap-3">
            <div className="w-6 h-6 rounded-full shimmer" />
            <div className="h-4 w-24 rounded shimmer" />
          </div>
        ))}
      </div>
    </div>
  )

  if (!job) return (
    <div className="text-center py-24">
      <p style={{ color: 'var(--text-muted)' }}>Job not found.</p>
    </div>
  )

  const srcLabel = LANG_LABELS[job.sourceLang] + (job.sourceCdkLang ? ` (${job.sourceCdkLang})` : '')
  const tgtLabel = LANG_LABELS[job.targetLang] + (job.targetCdkLang ? ` (${job.targetCdkLang})` : '')
  const totalTokens = job.tokensIn + job.tokensOut
  const done = job.status === 'COMPLETED' || job.status === 'COMPLETED_WITH_WARNINGS'

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      {/* Back */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/')} className="btn btn-ghost w-8 h-8 p-0 rounded-lg">
          <ArrowLeft size={15} />
        </button>
        <div className="flex items-center gap-2">
          <h1 className="font-display text-2xl font-bold" style={{ color: 'var(--text)' }}>
            Translation
          </h1>
          <CopyId id={job.jobId} />
        </div>
        <div className="ml-auto">
          <StatusBadge status={job.status} />
        </div>
      </div>

      {/* Route summary */}
      <div className="card p-4 flex items-center gap-3 mb-4">
        <span className="font-mono text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          {srcLabel}
        </span>
        <ArrowRight size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
        <span className="font-mono text-sm font-medium" style={{ color: 'var(--accent)' }}>
          {tgtLabel}
        </span>
        {totalTokens > 0 && (
          <span className="ml-auto text-xs font-mono" style={{ color: 'var(--text-faint)' }}>
            {(totalTokens / 1000).toFixed(1)}k tokens
          </span>
        )}
      </div>

      {/* Pipeline */}
      <div className="card p-4 mb-4">
        <p className="text-xs font-semibold uppercase tracking-widest mb-3"
           style={{ color: 'var(--text-faint)' }}>
          Pipeline
        </p>
        <PipelineSteps job={job} />
      </div>

      {/* Error */}
      {job.status === 'FAILED' && (
        <div className="flex items-start gap-3 p-4 rounded-xl mb-4"
             style={{ background: '#DC262610', border: '1px solid #DC262630' }}>
          <AlertCircle size={15} className="mt-0.5 flex-shrink-0" style={{ color: '#DC2626' }} />
          <div>
            <p className="text-sm font-medium mb-1" style={{ color: '#DC2626' }}>Translation failed</p>
            <p className="text-xs" style={{ color: '#DC2626', opacity: 0.75 }}>
              {friendlyError(job.errorMsg)}
            </p>
          </div>
        </div>
      )}

      {/* Warnings */}
      {job.status === 'COMPLETED_WITH_WARNINGS' && (
        <div className="flex items-start gap-3 p-4 rounded-xl mb-4"
             style={{ background: '#D9770610', border: '1px solid #D9770630' }}>
          <AlertCircle size={15} className="mt-0.5 flex-shrink-0" style={{ color: '#D97706' }} />
          <p className="text-sm" style={{ color: '#D97706' }}>
            Translation completed with warnings. Some files may need manual review.
          </p>
        </div>
      )}

      {/* Skipped files */}
      {job.skippedFiles && job.skippedFiles.length > 0 && (
        <div className="card p-4 mb-4">
          <p className="text-xs font-semibold uppercase tracking-widest mb-2"
             style={{ color: 'var(--text-faint)' }}>
            Skipped files ({job.skippedFiles.length})
          </p>
          <div className="space-y-1">
            {job.skippedFiles.slice(0, 5).map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-xs">
                <span className="font-mono" style={{ color: 'var(--text-muted)' }}>{f.path}</span>
                <span className="ml-auto" style={{ color: 'var(--text-faint)' }}>{f.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Success action */}
      {done && (
        <div className="flex flex-col items-center gap-3 py-6 animate-slide-up">
          <div className="w-12 h-12 rounded-full flex items-center justify-center"
               style={{ background: 'var(--accent-subtle)', border: '1px solid var(--accent)' }}>
            <CheckCircle size={22} style={{ color: 'var(--accent)' }} />
          </div>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>
            Your translated IaC is ready.
          </p>
          <DownloadButton jobId={job.jobId} />
          <button onClick={() => navigate('/jobs/new')} className="btn btn-ghost text-xs">
            Start another translation
          </button>
        </div>
      )}
    </div>
  )
}
