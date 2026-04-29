import type { JobStatus } from '../lib/api'

const CONFIG: Record<JobStatus, { label: string; color: string; dot: string }> = {
  AWAITING_UPLOAD:         { label: 'Awaiting upload',  color: '#6B7280', dot: '#9CA3AF' },
  RUNNING:                 { label: 'Translating',      color: '#2563EB', dot: '#3B82F6' },
  COMPLETED:               { label: 'Completed',        color: '#16A34A', dot: '#22C55E' },
  COMPLETED_WITH_WARNINGS: { label: 'Completed ⚠',     color: '#D97706', dot: '#F59E0B' },
  FAILED:                  { label: 'Failed',           color: '#DC2626', dot: '#EF4444' },
}

export default function StatusBadge({ status }: { status: JobStatus }) {
  const { label, color, dot } = CONFIG[status] ?? CONFIG.RUNNING

  return (
    <span
      className="badge"
      style={{
        color,
        background: `${color}14`,
        border:     `1px solid ${color}30`,
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
        style={{
          background: dot,
          ...(status === 'RUNNING' && {
            animation: 'glowPulse 1.4s ease-in-out infinite',
            boxShadow: `0 0 6px ${dot}`,
          }),
        }}
      />
      {label}
    </span>
  )
}
