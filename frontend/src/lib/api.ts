import { getAccessToken } from './auth'

const BASE = import.meta.env.VITE_API_ENDPOINT?.replace(/\/$/, '') ?? ''

// ── Types ───────────────────────────────────────────────────────────────────

export type LangKey = 'terraform' | 'cloudformation' | 'sam' | 'cdk'
export type CdkLang  = 'typescript' | 'python' | 'java' | 'csharp' | 'go'

export type JobStatus =
  | 'AWAITING_UPLOAD'
  | 'RUNNING'
  | 'COMPLETED'
  | 'COMPLETED_WITH_WARNINGS'
  | 'FAILED'

export interface Job {
  userId:       string
  jobId:        string
  status:       JobStatus
  step?:        string
  sourceLang:   LangKey
  sourceCdkLang?: CdkLang
  targetLang:   LangKey
  targetCdkLang?: CdkLang
  inputS3Key?:  string
  outputS3Key?: string
  createdAt:    string
  updatedAt:    string
  retryCount:   number
  tokensIn:     number
  tokensOut:    number
  errorMsg?:    string
  skippedFiles?: { path: string; reason: string }[]
  validationReport?: {
    ok: boolean
    errors: Array<{ file: string; msg: string; rule?: string }>
    warnings: string[]
  }
}

export interface CreateJobResponse {
  jobId:     string
  uploadUrl: string
}

export interface UserProfile {
  userId: string
  tier: 'free' | 'pro'
  quotaLimit: number
  subscriptionStatus: string | null
  apiKey: string | null
}

// ── Fetch wrapper ───────────────────────────────────────────────────────────

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = await getAccessToken()
  const res = await fetch(`${BASE}${path}`, {
    method: 'GET',
    ...init,
    headers: {
      Authorization:  `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }))
    throw Object.assign(new Error(err.error ?? 'API error'), { status: res.status, data: err })
  }
  return res.json()
}

// ── API methods ─────────────────────────────────────────────────────────────

export async function listJobs(nextToken?: string): Promise<{ items: Job[]; nextToken?: string }> {
  const qs = nextToken ? `?nextToken=${encodeURIComponent(nextToken)}` : ''
  return apiFetch(`/jobs${qs}`)
}

export async function getJob(jobId: string): Promise<Job> {
  return apiFetch(`/jobs/${jobId}`)
}

export async function createJob(payload: {
  sourceLang:    LangKey
  targetLang:    LangKey
  sourceCdkLang?: CdkLang
  targetCdkLang?: CdkLang
}): Promise<CreateJobResponse> {
  return apiFetch('/jobs', { method: 'POST', body: JSON.stringify(payload) })
}

export async function startJob(jobId: string): Promise<{ jobId: string; status: string }> {
  return apiFetch(`/jobs/${jobId}/start`, { method: 'POST' })
}

export async function getDownloadUrl(jobId: string): Promise<{ downloadUrl: string; status: string }> {
  return apiFetch(`/jobs/${jobId}/download`)
}

export async function uploadZip(uploadUrl: string, file: File): Promise<void> {
  const res = await fetch(uploadUrl, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/zip' },
    body:    file,
  })
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
}

// ── User & billing ──────────────────────────────────────────────────────────

export async function getUserProfile(): Promise<UserProfile> {
  return apiFetch('/user/profile')
}

export async function createCheckoutSession(): Promise<{ url: string }> {
  return apiFetch('/billing/checkout', { method: 'POST' })
}

export async function createPortalSession(): Promise<{ url: string }> {
  return apiFetch('/billing/portal', { method: 'POST' })
}

// ── Full job submission flow ────────────────────────────────────────────────

export async function submitJob(
  file: File,
  sourceLang: LangKey,
  targetLang: LangKey,
  sourceCdkLang?: CdkLang,
  targetCdkLang?: CdkLang,
): Promise<string> {
  const { jobId, uploadUrl } = await createJob({
    sourceLang, targetLang, sourceCdkLang, targetCdkLang,
  })
  await uploadZip(uploadUrl, file)
  await startJob(jobId)
  return jobId
}
