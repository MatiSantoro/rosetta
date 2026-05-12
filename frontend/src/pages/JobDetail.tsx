import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Download, AlertCircle, CheckCircle, ArrowRight, Copy, Check, Lock } from 'lucide-react'
import { useState, useEffect, useRef } from 'react'
import { getJob, getDownloadUrl, submitFeedback, type Job, type LangKey } from '../lib/api'
import StatusBadge from '../components/StatusBadge'

// ── Constants ───────────────────────────────────────────────────────────────

const LANG_LABELS: Record<LangKey, string> = {
  terraform:      'Terraform',
  cloudformation: 'CloudFormation',
  sam:            'SAM',
  cdk:            'CDK',
}

const PIPELINE_STEPS = [
  { key: 'PREFLIGHT',    label: 'Preflight',     desc: 'Extracting & classifying files'  },
  { key: 'COMPAT_CHECK', label: 'Compatibility', desc: 'Checking SAM serverless rules'   },
  { key: 'PLAN',         label: 'Analysis',      desc: 'Building translation plan'       },
  { key: 'TRANSLATE',    label: 'Translation',   desc: 'Calling Claude Sonnet'           },
  { key: 'VALIDATE',     label: 'Validation',    desc: 'Linting output files'            },
  { key: 'DONE',         label: 'Done',          desc: 'Packaging results'               },
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
  if (r.includes('language_mismatch') || r.includes('look like') && r.includes('but you selected')) {
    // Extract the detected/declared labels from the raw message if possible
    const match = raw?.match(/look like (.+?), but you selected (.+?)\. Please/)
    if (match)
      return `The uploaded files look like ${match[1]}, but you selected ${match[2]} as the source language. Please start a new translation and choose the correct source format.`
    return 'The source language you selected does not match the files in your zip. Please start a new translation and choose the correct source format.'
  }
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
  const terminal = isTerminal(job.status)
  const failed   = job.status === 'FAILED'
  const allDone  = job.status === 'COMPLETED' || job.status === 'COMPLETED_WITH_WARNINGS'

  // The real step index from the server — our ground truth.
  const serverIdx = allDone
    ? PIPELINE_STEPS.length  // every step complete
    : failed
      ? stepIndex(job.step)
      : stepIndex(job.step)

  // displayIdx: the step we're currently SHOWING in the UI.
  // It only ever moves forward — never backwards.
  // When the server jumps several steps at once (e.g. polling missed
  // COMPAT_CHECK and PLAN), we animate through each missed step at 350ms
  // intervals so the user sees them light up one by one.
  const [displayIdx, setDisplayIdx] = useState(Math.max(serverIdx, -1))
  const animRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    // Clear any running animation before starting a new one
    if (animRef.current) clearInterval(animRef.current)

    if (serverIdx <= displayIdx) return  // never go backwards

    // Animate through each missed step
    let next = displayIdx + 1
    animRef.current = setInterval(() => {
      setDisplayIdx(next)
      next++
      if (next > serverIdx) {
        clearInterval(animRef.current!)
        animRef.current = null
      }
    }, 350)

    return () => {
      if (animRef.current) clearInterval(animRef.current)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverIdx])

  return (
    <div className="space-y-1">
      {PIPELINE_STEPS.map((s, i) => {
        const done    = allDone || i < displayIdx
        const active  = i === displayIdx && !terminal
        const errored = failed && i === displayIdx

        return (
          <div
            key={s.key}
            className="flex items-center gap-3 py-2 px-3 rounded-lg transition-all duration-300"
            style={{ background: active ? 'var(--accent-subtle)' : errored ? '#DC262610' : 'transparent' }}
          >
            {/* Icon */}
            <div
              className="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-500"
              style={{
                background: done    ? 'var(--accent)'  :
                            active  ? 'var(--accent)'  :
                            errored ? '#DC2626'        : 'var(--bg-subtle)',
                boxShadow: active ? '0 0 12px var(--accent-glow)' : 'none',
              }}
            >
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
              <span
                className="text-sm font-medium transition-colors duration-300"
                style={{ color: done || active ? 'var(--text)' : 'var(--text-faint)' }}
              >
                {s.label}
              </span>
              {active && (
                <span className="ml-2 text-xs" style={{ color: 'var(--text-muted)' }}>
                  {s.desc}
                </span>
              )}
            </div>
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

// ── Validation report ───────────────────────────────────────────────────────

function ValidationReport({ report }: { report: NonNullable<Job['validationReport']> }) {
  const [warningsOpen, setWarningsOpen] = useState(false)
  const hasErrors   = report.errors.length > 0
  const hasWarnings = report.warnings.length > 0

  return (
    <div className="card p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold uppercase tracking-widest"
           style={{ color: 'var(--text-faint)' }}>
          Validation Report
        </p>
        <span
          className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
          style={{ background: 'var(--accent-subtle)', color: 'var(--accent)', border: '1px solid var(--accent)' }}
        >
          Pro feature
        </span>
      </div>

      {/* Summary row */}
      <div className="flex items-center gap-4 mb-3">
        {report.ok ? (
          <span className="flex items-center gap-1.5 text-sm font-medium" style={{ color: '#22C55E' }}>
            <Check size={14} />
            Passed
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-sm font-medium" style={{ color: '#DC2626' }}>
            <AlertCircle size={14} />
            {report.errors.length} {report.errors.length === 1 ? 'error' : 'errors'}
          </span>
        )}
        {hasWarnings && (
          <span className="flex items-center gap-1.5 text-sm" style={{ color: '#D97706' }}>
            <AlertCircle size={13} />
            {report.warnings.length} {report.warnings.length === 1 ? 'warning' : 'warnings'}
          </span>
        )}
      </div>

      {/* Errors list */}
      {hasErrors && (
        <div className="rounded-lg overflow-hidden mb-3"
             style={{ background: '#DC262608', border: '1px solid #DC262620' }}>
          <div className="space-y-0">
            {report.errors.map((e, i) => (
              <div key={i} className="px-3 py-2 border-b last:border-b-0 text-xs"
                   style={{ borderColor: '#DC262618' }}>
                <span className="font-mono" style={{ color: '#DC2626' }}>{e.file}</span>
                <span style={{ color: 'var(--text-faint)' }}>: </span>
                <span style={{ color: 'var(--text-muted)' }}>{e.msg}</span>
                {e.rule && (
                  <span className="ml-2 font-mono text-[10px]" style={{ color: 'var(--text-faint)' }}>
                    [{e.rule}]
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warnings collapsible */}
      {hasWarnings && (
        <div>
          <button
            onClick={() => setWarningsOpen(o => !o)}
            className="flex items-center gap-1.5 text-xs mb-2 transition-colors"
            style={{ color: '#D97706' }}
          >
            <AlertCircle size={11} />
            {warningsOpen ? 'Hide' : 'Show'} {report.warnings.length} {report.warnings.length === 1 ? 'warning' : 'warnings'}
          </button>
          {warningsOpen && (
            <div className="rounded-lg overflow-hidden"
                 style={{ background: '#D9770608', border: '1px solid #D9770620' }}>
              {report.warnings.map((w, i) => (
                <div key={i} className="px-3 py-2 border-b last:border-b-0 text-xs"
                     style={{ borderColor: '#D9770618', color: 'var(--text-muted)' }}>
                  {w}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function LockedValidation() {
  const navigate = useNavigate()
  return (
    <div className="card p-4 mb-4 flex items-start gap-3"
         style={{ border: '1px solid var(--border)' }}>
      <Lock size={15} className="flex-shrink-0 mt-0.5" style={{ color: 'var(--text-faint)' }} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium mb-0.5" style={{ color: 'var(--text-muted)' }}>
          Detailed Validation Report
        </p>
        <p className="text-xs mb-2" style={{ color: 'var(--text-faint)' }}>
          See line-by-line cfn-lint and terraform output.
        </p>
        <button
          onClick={() => navigate('/settings')}
          className="text-xs font-medium transition-colors"
          style={{ color: 'var(--accent)' }}
          onMouseEnter={e => (e.currentTarget.style.opacity = '0.75')}
          onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
        >
          Upgrade to Pro →
        </button>
      </div>
    </div>
  )
}

// ── Feedback widget ─────────────────────────────────────────────────────────

function FeedbackWidget({ job }: { job: Job }) {
  const [submitted, setSubmitted] = useState<'up' | 'down' | null>(
    job.feedback ?? null
  )
  const [loading, setLoading] = useState(false)

  async function vote(value: 'up' | 'down') {
    if (submitted || loading) return
    setLoading(true)
    try {
      await submitFeedback(job.jobId, value)
      setSubmitted(value)
    } catch {
      // silently ignore — feedback is non-critical
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
        {submitted === 'up' ? '👍' : '👎'} Thanks for your feedback!
      </p>
    )
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <p className="text-xs" style={{ color: 'var(--text-faint)' }}>
        Was this translation accurate?
      </p>
      <div className="flex items-center gap-2">
        {(['up', 'down'] as const).map(v => (
          <button
            key={v}
            onClick={() => vote(v)}
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all duration-150"
            style={{
              background: 'var(--bg-subtle)',
              border: '1px solid var(--border)',
              color: 'var(--text-muted)',
              opacity: loading ? 0.5 : 1,
            }}
            onMouseEnter={e => { if (!loading) e.currentTarget.style.borderColor = 'var(--accent)' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border)' }}
          >
            {v === 'up' ? '👍' : '👎'}
          </button>
        ))}
      </div>
    </div>
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
      <div className="card p-4 mb-4 flex flex-wrap items-center gap-3">
        <span className="font-mono text-sm font-medium" style={{ color: 'var(--text-muted)' }}>
          {srcLabel}
        </span>
        <ArrowRight size={14} style={{ color: 'var(--accent)', flexShrink: 0 }} />
        <span className="font-mono text-sm font-medium" style={{ color: 'var(--accent)' }}>
          {tgtLabel}
        </span>
        {totalTokens > 0 && (
          <span className="text-xs font-mono" style={{ color: 'var(--text-faint)', marginLeft: 'auto' }}>
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

      {/* Validation report (Pro) */}
      {job.validationReport
        ? <ValidationReport report={job.validationReport} />
        : <LockedValidation />
      }

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
          <FeedbackWidget job={job} />
          <button onClick={() => navigate('/jobs/new')} className="btn btn-ghost text-xs">
            Start another translation
          </button>
        </div>
      )}
    </div>
  )
}
