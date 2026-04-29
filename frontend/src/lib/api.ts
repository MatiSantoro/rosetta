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
}

export interface CreateJobResponse {
  jobId:     string
  uploadUrl: string
}

// ── Fetch wrapper ───────────────────────────────────────────────────────────

async function apiFetch<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const token = await getAccessToken()
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      Authorization:  `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
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
  return apiFetch('GET', `/jobs${qs}`)
}

export async function getJob(jobId: string): Promise<Job> {
  return apiFetch('GET', `/jobs/${jobId}`)
}

export async function createJob(payload: {
  sourceLang:    LangKey
  targetLang:    LangKey
  sourceCdkLang?: CdkLang
  targetCdkLang?: CdkLang
}): Promise<CreateJobResponse> {
  return apiFetch('POST', '/jobs', payload)
}

export async function startJob(jobId: string): Promise<{ jobId: string; status: string }> {
  return apiFetch('POST', `/jobs/${jobId}/start`)
}

export async function getDownloadUrl(jobId: string): Promise<{ downloadUrl: string; status: string }> {
  return apiFetch('GET', `/jobs/${jobId}/download`)
}

export async function uploadZip(uploadUrl: string, file: File): Promise<void> {
  const res = await fetch(uploadUrl, {
    method:  'PUT',
    headers: { 'Content-Type': 'application/zip' },
    body:    file,
  })
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
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
