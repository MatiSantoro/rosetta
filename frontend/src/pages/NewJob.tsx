import { useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { Upload, ArrowRight, ArrowLeft, CheckCircle, AlertCircle, FileArchive } from 'lucide-react'
import { submitJob, type LangKey, type CdkLang } from '../lib/api'

// ── Types & constants ──────────────────────────────────────────────────────

interface Format {
  key:     LangKey
  label:   string
  mono:    string
  color:   string
}

const FORMATS: Format[] = [
  { key: 'terraform',      label: 'Terraform',       mono: '.tf',   color: '#7B68EE' },
  { key: 'cloudformation', label: 'CloudFormation',  mono: '.yaml', color: '#F59E0B' },
  { key: 'sam',            label: 'SAM',             mono: '.yaml', color: '#10B981' },
  { key: 'cdk',            label: 'CDK',             mono: '.ts',   color: '#06B6D4' },
]

const CDK_LANGS: { key: CdkLang; label: string }[] = [
  { key: 'typescript', label: 'TypeScript' },
  { key: 'python',     label: 'Python'     },
  { key: 'java',       label: 'Java'       },
  { key: 'csharp',     label: 'C#'         },
  { key: 'go',         label: 'Go'         },
]

// ── FormatCard ─────────────────────────────────────────────────────────────

function FormatCard({
  format, selected, onClick,
}: { format: Format; selected: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left px-4 py-3 rounded-xl border transition-all duration-150 active:scale-95"
      style={{
        background:   selected ? `${format.color}14` : 'var(--surface)',
        borderColor:  selected ? format.color : 'var(--border)',
        boxShadow:    selected ? `0 0 0 1px ${format.color}` : 'none',
      }}
    >
      <div className="flex items-center justify-between">
        <span className="font-medium text-sm" style={{ color: selected ? format.color : 'var(--text)' }}>
          {format.label}
        </span>
        <span className="font-mono text-xs" style={{ color: selected ? format.color : 'var(--text-faint)' }}>
          {format.mono}
        </span>
      </div>
    </button>
  )
}

// ── Step indicator ──────────────────────────────────────────────────────────

function Steps({ current }: { current: number }) {
  const steps = ['Upload', 'Format', 'Confirm']
  return (
    <div className="flex items-center gap-2 mb-8">
      {steps.map((s, i) => (
        <div key={s} className="flex items-center gap-2">
          <div className="flex items-center gap-1.5">
            <div
              className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold transition-all duration-300"
              style={{
                background: i < current ? 'var(--accent)' : i === current ? 'var(--accent)' : 'var(--bg-subtle)',
                color:      i <= current ? 'var(--accent-fg)' : 'var(--text-faint)',
              }}
            >
              {i < current ? '✓' : i + 1}
            </div>
            <span
              className="text-xs font-medium hidden sm:block"
              style={{ color: i === current ? 'var(--text)' : 'var(--text-faint)' }}
            >
              {s}
            </span>
          </div>
          {i < steps.length - 1 && (
            <div className="w-8 h-px" style={{ background: i < current ? 'var(--accent)' : 'var(--border)' }} />
          )}
        </div>
      ))}
    </div>
  )
}

// ── Main component ──────────────────────────────────────────────────────────

export default function NewJob() {
  const navigate = useNavigate()
  const [step, setStep]             = useState(0)
  const [file, setFile]             = useState<File | null>(null)
  const [dragging, setDragging]     = useState(false)
  const [sourceLang, setSourceLang] = useState<LangKey | null>(null)
  const [targetLang, setTargetLang] = useState<LangKey | null>(null)
  const [sourceCdk, setSourceCdk]   = useState<CdkLang>('typescript')
  const [targetCdk, setTargetCdk]   = useState<CdkLang>('typescript')
  const fileRef = useRef<HTMLInputElement>(null)

  const mutation = useMutation({
    mutationFn: () => submitJob(
      file!,
      sourceLang!,
      targetLang!,
      sourceLang === 'cdk' ? sourceCdk : undefined,
      targetLang === 'cdk' ? targetCdk : undefined,
    ),
    onSuccess: (jobId) => navigate(`/jobs/${jobId}`),
  })

  // Drop zone handlers
  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f?.type === 'application/zip' || f?.name.endsWith('.zip')) {
      setFile(f)
      setStep(1)
    }
  }, [])

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f) { setFile(f); setStep(1) }
  }

  const canGoNext =
    step === 0 ? !!file :
    step === 1 ? !!sourceLang && !!targetLang && sourceLang !== targetLang :
    true

  // ── Step 0: Upload ────────────────────────────────────────────────────────

  function renderUpload() {
    return (
      <div className="animate-slide-up">
        <h2 className="font-display text-xl font-bold mb-1" style={{ color: 'var(--text)' }}>
          Upload your project
        </h2>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
          Zip your IaC files and folders — up to 50 MB, 200 files.
        </p>

        {/* Drop zone */}
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          className="relative flex flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed
                     cursor-pointer transition-all duration-200 h-52"
          style={{
            borderColor: dragging ? 'var(--accent)' : 'var(--border)',
            background:  dragging ? 'var(--accent-subtle)' : 'var(--surface)',
          }}
        >
          {file ? (
            <>
              <div className="w-12 h-12 rounded-xl flex items-center justify-center"
                   style={{ background: 'var(--accent-subtle)' }}>
                <FileArchive size={22} style={{ color: 'var(--accent)' }} />
              </div>
              <div className="text-center">
                <p className="font-mono text-sm font-medium" style={{ color: 'var(--text)' }}>{file.name}</p>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                  {(file.size / 1024).toFixed(1)} KB · Click to change
                </p>
              </div>
            </>
          ) : (
            <>
              <div className="w-12 h-12 rounded-xl flex items-center justify-center"
                   style={{ background: 'var(--bg-subtle)' }}>
                <Upload size={22} style={{ color: 'var(--text-muted)' }} />
              </div>
              <div className="text-center">
                <p className="font-medium text-sm" style={{ color: 'var(--text)' }}>
                  Drop your .zip here
                </p>
                <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                  or click to browse
                </p>
              </div>
            </>
          )}
          <input ref={fileRef} type="file" accept=".zip" className="hidden" onChange={onFileChange} />
        </div>
      </div>
    )
  }

  // ── Step 1: Format selection ──────────────────────────────────────────────

  function renderFormat() {
    return (
      <div className="animate-slide-up">
        <h2 className="font-display text-xl font-bold mb-1" style={{ color: 'var(--text)' }}>
          Choose formats
        </h2>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
          Select the source format and the target you want to convert to.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-[1fr_32px_1fr] gap-4 items-start">
          {/* Source */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest mb-3"
               style={{ color: 'var(--text-faint)' }}>
              From
            </p>
            <div className="space-y-2">
              {FORMATS.map(f => (
                <FormatCard key={f.key} format={f} selected={sourceLang === f.key}
                            onClick={() => setSourceLang(f.key)} />
              ))}
            </div>
            {sourceLang === 'cdk' && (
              <div className="mt-3 p-3 rounded-lg" style={{ background: 'var(--bg-subtle)' }}>
                <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>CDK language</p>
                <div className="flex flex-wrap gap-1.5">
                  {CDK_LANGS.map(l => (
                    <button key={l.key} onClick={() => setSourceCdk(l.key)}
                      className="px-2.5 py-1 rounded-lg text-xs font-mono transition-all"
                      style={{
                        background: sourceCdk === l.key ? 'var(--accent)' : 'var(--surface)',
                        color:      sourceCdk === l.key ? 'var(--accent-fg)' : 'var(--text-muted)',
                        border:     `1px solid ${sourceCdk === l.key ? 'var(--accent)' : 'var(--border)'}`,
                      }}>
                      {l.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Arrow */}
          <div className="hidden md:flex items-center justify-center pt-10">
            <ArrowRight size={18} style={{ color: 'var(--accent)' }} />
          </div>

          {/* Target */}
          <div>
            <p className="text-xs font-semibold uppercase tracking-widest mb-3"
               style={{ color: 'var(--text-faint)' }}>
              To
            </p>
            <div className="space-y-2">
              {FORMATS.map(f => (
                <FormatCard key={f.key} format={f}
                            selected={targetLang === f.key}
                            onClick={() => setTargetLang(f.key)} />
              ))}
            </div>
            {targetLang === 'cdk' && (
              <div className="mt-3 p-3 rounded-lg" style={{ background: 'var(--bg-subtle)' }}>
                <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>CDK language</p>
                <div className="flex flex-wrap gap-1.5">
                  {CDK_LANGS.map(l => (
                    <button key={l.key} onClick={() => setTargetCdk(l.key)}
                      className="px-2.5 py-1 rounded-lg text-xs font-mono transition-all"
                      style={{
                        background: targetCdk === l.key ? 'var(--accent)' : 'var(--surface)',
                        color:      targetCdk === l.key ? 'var(--accent-fg)' : 'var(--text-muted)',
                        border:     `1px solid ${targetCdk === l.key ? 'var(--accent)' : 'var(--border)'}`,
                      }}>
                      {l.label}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {sourceLang && targetLang && sourceLang === targetLang && (
          <div className="flex items-center gap-2 mt-4 p-3 rounded-lg"
               style={{ background: '#DC262610', border: '1px solid #DC262630' }}>
            <AlertCircle size={14} style={{ color: '#DC2626' }} />
            <span className="text-xs" style={{ color: '#DC2626' }}>Source and target must be different formats.</span>
          </div>
        )}
      </div>
    )
  }

  // ── Step 2: Confirm ───────────────────────────────────────────────────────

  function renderConfirm() {
    const src = FORMATS.find(f => f.key === sourceLang)!
    const tgt = FORMATS.find(f => f.key === targetLang)!

    return (
      <div className="animate-slide-up">
        <h2 className="font-display text-xl font-bold mb-1" style={{ color: 'var(--text)' }}>
          Ready to translate
        </h2>
        <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
          Review the details and start the translation.
        </p>

        <div className="card p-5 space-y-4 mb-6">
          <div className="flex items-center gap-3 text-sm">
            <FileArchive size={16} style={{ color: 'var(--text-muted)' }} />
            <span style={{ color: 'var(--text-muted)' }}>File</span>
            <span className="font-mono font-medium" style={{ color: 'var(--text)' }}>{file?.name}</span>
            <span className="ml-auto text-xs" style={{ color: 'var(--text-faint)' }}>
              {((file?.size ?? 0) / 1024).toFixed(1)} KB
            </span>
          </div>

          <div className="h-px" style={{ background: 'var(--border)' }} />

          <div className="flex items-center gap-3">
            <span className="font-mono text-xs px-3 py-1.5 rounded-lg font-medium"
                  style={{ background: `${src.color}14`, color: src.color, border: `1px solid ${src.color}30` }}>
              {src.label}{sourceLang === 'cdk' ? ` (${sourceCdk})` : ''}
            </span>
            <ArrowRight size={16} style={{ color: 'var(--accent)' }} />
            <span className="font-mono text-xs px-3 py-1.5 rounded-lg font-medium"
                  style={{ background: `${tgt.color}14`, color: tgt.color, border: `1px solid ${tgt.color}30` }}>
              {tgt.label}{targetLang === 'cdk' ? ` (${targetCdk})` : ''}
            </span>
          </div>
        </div>

        {mutation.isError && (
          <div className="flex items-start gap-2 p-3 rounded-lg mb-4"
               style={{ background: '#DC262610', border: '1px solid #DC262630' }}>
            <AlertCircle size={14} className="mt-0.5 flex-shrink-0" style={{ color: '#DC2626' }} />
            <span className="text-xs" style={{ color: '#DC2626' }}>
              {(mutation.error as { message?: string })?.message ?? 'Something went wrong. Please try again.'}
            </span>
          </div>
        )}

        <button
          onClick={() => mutation.mutate()}
          disabled={mutation.isPending}
          className="btn btn-primary w-full py-3 text-sm"
          style={{ boxShadow: '0 4px 16px var(--accent-glow)' }}
        >
          {mutation.isPending ? (
            <>
              <div className="w-4 h-4 rounded-full border-2 border-current border-t-transparent"
                   style={{ animation: 'spin 0.7s linear infinite' }} />
              Uploading & starting…
            </>
          ) : (
            <>
              <CheckCircle size={15} />
              Start translation
            </>
          )}
        </button>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      {/* Header */}
      <div className="mb-6">
        <h1 className="font-display text-2xl font-bold" style={{ color: 'var(--text)' }}>
          New translation
        </h1>
      </div>

      <Steps current={step} />

      {/* Step content */}
      {step === 0 && renderUpload()}
      {step === 1 && renderFormat()}
      {step === 2 && renderConfirm()}

      {/* Navigation — Back and Continue always visible together */}
      {step < 2 && (
        <div className="mt-6 flex items-center justify-between">
          <button
            onClick={() => step > 0 ? setStep(s => s - 1) : navigate('/')}
            className="btn btn-ghost px-4 flex items-center gap-2 text-sm"
            style={{ color: 'var(--text-muted)' }}
          >
            <ArrowLeft size={14} />
            {step === 0 ? 'Cancel' : 'Back'}
          </button>

          <button
            onClick={() => setStep(s => s + 1)}
            disabled={!canGoNext}
            className="btn btn-primary px-6"
            style={{ opacity: canGoNext ? 1 : 0.4 }}
          >
            Continue
            <ArrowRight size={14} />
          </button>
        </div>
      )}

      {/* Back button on confirm step */}
      {step === 2 && !mutation.isPending && (
        <div className="mt-3 flex justify-center">
          <button
            onClick={() => setStep(1)}
            className="text-xs flex items-center gap-1.5 transition-colors"
            style={{ color: 'var(--text-faint)' }}
            onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-muted)')}
            onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-faint)')}
          >
            <ArrowLeft size={11} />
            Change formats
          </button>
        </div>
      )}
    </div>
  )
}
