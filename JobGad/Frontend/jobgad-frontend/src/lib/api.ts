const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

function getToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('access_token')
}

function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('refresh_token')
}

export function saveTokens(access: string, refresh?: string) {
  localStorage.setItem('access_token', access)
  if (refresh) localStorage.setItem('refresh_token', refresh)
}

export function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
}

async function request<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  if (!(options.body instanceof FormData)) {
    headers['Content-Type'] = headers['Content-Type'] || 'application/json'
  }
  const res = await fetch(`${BASE}/api/v1${path}`, { ...options, headers })
  if (res.status === 401 && retry) {
    const refreshed = await tryRefresh()
    if (refreshed) return request<T>(path, options, false)
    clearTokens()
    if (typeof window !== 'undefined') window.location.href = '/login'
    throw new Error('Session expired')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: 'Request failed' }))
    throw new Error(err.detail || err.message || `Error ${res.status}`)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken()
  if (!refresh) return false
  try {
    const res = await fetch(`${BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!res.ok) return false
    const data = await res.json()
    saveTokens(data.access_token)
    return true
  } catch { return false }
}

export async function downloadFile(path: string, filename: string) {
  const token = getToken()
  const res = await fetch(`${BASE}/api/v1${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  if (!res.ok) throw new Error('Download failed')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export const auth = {
  register: (data: { email: string; password: string; full_name: string; role: string }) =>
    request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
  login: async (email: string, password: string) => {
    const form = new URLSearchParams()
    form.append('username', email)
    form.append('password', password)
    const res = await fetch(`${BASE}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Invalid credentials')
    }
    return res.json() as Promise<{ access_token: string; refresh_token: string; token_type: string }>
  },
  me: () => request<User>('/auth/me'),
  logout: () => { clearTokens(); window.location.href = '/login' },
}

export const profile = {
  get: () => request<Profile>('/profile/me'),
  create: (data: Partial<Profile>) => request('/profile/me', { method: 'POST', body: JSON.stringify(data) }),
  update: (data: Partial<Profile>) => request('/profile/me', { method: 'PUT', body: JSON.stringify(data) }),
  delete: () => request('/profile/me', { method: 'DELETE' }),
  completeness: () => request<{ profile_completeness: number; message: string }>('/profile/me/completeness'),
  getSkills: () => request<Skill[]>('/profile/me/skills'),
  addSkill: (data: { name: string; category: string; proficiency: string }) =>
    request('/profile/me/skills', { method: 'POST', body: JSON.stringify(data) }),
  deleteSkill: (id: string) => request(`/profile/me/skills/${id}`, { method: 'DELETE' }),
  skillGap: (jobId?: string) => request<SkillGap>(`/profile/me/skill-gap${jobId ? `?job_id=${jobId}` : ''}`),
  learningRoadmap: () => request('/profile/me/learning-roadmap'),
  cvReview: () => request('/profile/me/cv-review'),
  analyzeSocials: () => request('/profile/me/analyze-socials', { method: 'POST' }),
  getDocuments: () => request<Document[]>('/profile/documents'),
  uploadDocument: (file: File, docType: string) => {
    const form = new FormData()
    form.append('file', file)
    form.append('doc_type', docType)
    return request('/profile/documents', { method: 'POST', body: form })
  },
  deleteDocument: (id: string) => request(`/profile/documents/${id}`, { method: 'DELETE' }),
  extractSkills: (id: string) => request(`/profile/documents/${id}/extract-skills`, { method: 'POST' }),
}

export const jobs = {
  list: (params?: { page?: number; page_size?: number; search?: string; employment_type?: string; location?: string }) => {
    const q = new URLSearchParams()
    if (params?.page)            q.set('page', String(params.page))
    if (params?.page_size)       q.set('page_size', String(params.page_size))
    if (params?.search)          q.set('search', params.search)
    if (params?.employment_type) q.set('employment_type', params.employment_type)
    if (params?.location)        q.set('location', params.location)
    return request<{ jobs: Job[]; total: number; page: number; page_size: number }>(`/jobs/listings?${q}`)
  },
  get: (id: string) => request<Job>(`/jobs/listings/${id}`),
  runMatches: (topK = 10, employmentType?: string) => {
    const q = new URLSearchParams({ top_k: String(topK) })
    if (employmentType) q.set('employment_type', employmentType)
    return request<JobMatch[]>(`/jobs/matches/run?${q}`, { method: 'POST' })
  },
  getMatches: (status?: string) => request<JobMatch[]>(`/jobs/matches${status ? `?match_status=${status}` : ''}`),
  updateMatchStatus: (matchId: string, status: string) =>
    request(`/jobs/matches/${matchId}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
  explainMatch: (jobId: string) => request<MatchExplanation>(`/jobs/matches/${jobId}/explain`),
}

export const search = {
  jobs: (params: { q?: string; location?: string; employment_type?: string; company?: string; posted_within?: number; sort_by?: string; page?: number; page_size?: number }) => {
    const q = new URLSearchParams()
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) q.set(k, String(v)) })
    return request<SearchResult>(`/search/jobs?${q}`)
  },
  suggestions: (q: string) => request<string[]>(`/search/jobs/suggestions?q=${encodeURIComponent(q)}`),
}

export const applications = {
  apply: (jobId: string, coverLetter?: string) =>
    request('/applications/', { method: 'POST', body: JSON.stringify({ job_id: jobId, cover_letter: coverLetter }) }),
  list: (statusFilter?: string) => request<Application[]>(`/applications/${statusFilter ? `?status_filter=${statusFilter}` : ''}`),
  stats: () => request<ApplicationStats>('/applications/stats'),
  get: (id: string) => request<Application>(`/applications/${id}`),
  withdraw: (id: string) => request(`/applications/${id}`, { method: 'DELETE' }),
}

export const coaching = {
  createSession: (jobId: string, sessionType: 'behavioral' | 'technical' | 'mixed') =>
    request<CoachingSession>('/coaching/sessions', { method: 'POST', body: JSON.stringify({ job_id: jobId, session_type: sessionType }) }),
  submitAnswer: (sessionId: string, data: { question_number: number; answer: string; time_taken_seconds: number }) =>
    request(`/coaching/sessions/${sessionId}/answer`, { method: 'POST', body: JSON.stringify(data) }),
  endSession: (sessionId: string) => request(`/coaching/sessions/${sessionId}/end`, { method: 'POST' }),
  getSessions: () => request<CoachingSession[]>('/coaching/sessions'),
  getSession: (id: string) => request<CoachingSession>(`/coaching/sessions/${id}`),
  getIRI: () => request<IRIData>('/coaching/iri'),
  getProgress: () => request('/coaching/progress'),
  getLearningPlan: () => request('/coaching/learning-plan'),
}

export const cv = {
  generate: (jobId: string, fileFormat: 'pdf' | 'docx' = 'pdf') =>
    request('/cv/generate', { method: 'POST', body: JSON.stringify({ job_id: jobId, file_format: fileFormat }) }),
  generateWithAnswers: (data: object) =>
    request('/cv/generate-with-answers', { method: 'POST', body: JSON.stringify(data) }),
  list: () => request<GeneratedCV[]>('/cv/'),
  download: (cvId: string, filename: string) => downloadFile(`/cv/${cvId}/download`, filename),
}

export const notifications = {
  list: () => request<NotificationsResponse>('/notifications/'),
  markRead: (id: string) => request(`/notifications/${id}/read`, { method: 'PATCH' }),
  markAllRead: () => request('/notifications/read-all', { method: 'PATCH' }),
}

export const dashboard = {
  me: () => request<GraduateDashboard | HRDashboard>('/dashboard/me'),
  graduate: () => request<GraduateDashboard>('/dashboard/graduate'),
  hr: () => request<HRDashboard>('/dashboard/hr'),
}

export const hr = {
  postJob: (data: object) => request('/hr/jobs', { method: 'POST', body: JSON.stringify(data) }),
  getJobs: (includeInactive = false) => request<Job[]>(`/hr/jobs?include_closed=${includeInactive}`),
  updateJob: (id: string, data: object) => request(`/hr/jobs/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  closeJob: (id: string) => request(`/hr/jobs/${id}/close`, { method: 'PATCH' }),
  getApplications: (status?: string) => request<Application[]>(`/hr/applications${status ? `?status_filter=${status}` : ''}`),
  getJobApplications: (jobId: string) => request<Application[]>(`/hr/jobs/${jobId}/applications`),
  updateApplicationStatus: (appId: string, status: string, notes?: string) =>
    request(`/hr/applications/${appId}/status`, { method: 'PATCH', body: JSON.stringify({ status, hr_notes: notes }) }),
}

export const admin = {
  dashboard: () => request('/admin/dashboard'),
  getCompanies: (status?: string) => request(`/admin/companies${status ? `?status_filter=${status}` : ''}`),
  approveCompany: (id: string) => request(`/admin/companies/${id}/approve`, { method: 'PATCH' }),
  rejectCompany: (id: string, reason: string) => request(`/admin/companies/${id}/reject`, { method: 'PATCH', body: JSON.stringify({ reason }) }),
  getHRProfiles: (status?: string) => request(`/admin/hr-profiles${status ? `?status_filter=${status}` : ''}`),
  approveHR: (id: string) => request(`/admin/hr-profiles/${id}/approve`, { method: 'PATCH' }),
  rejectHR: (id: string, reason: string) => request(`/admin/hr-profiles/${id}/reject`, { method: 'PATCH', body: JSON.stringify({ reason }) }),
  registerCompany: (data: object) => request('/admin/companies', { method: 'POST', body: JSON.stringify(data) }),
  registerHRProfile: (data: object) => request('/admin/hr-profiles', { method: 'POST', body: JSON.stringify(data) }),
}

export interface User { id: string; email: string; full_name: string; role: string; is_active: boolean; is_verified: boolean; created_at: string }
export interface Profile { id?: string; headline?: string; bio?: string; github_url?: string; linkedin_url?: string; portfolio_url?: string; education_level?: string; field_of_study?: string; institution?: string; graduation_year?: number; target_role?: string; skills?: Skill[] }
export interface Skill { id: string; name: string; category: string; proficiency: string }
export interface SkillGap { target_role: string; total_skills: number; matching_skills: string[]; missing_skills: string[]; recommendations: string[]; readiness_score: number }
export interface Document { id: string; doc_type: string; file_name: string; storage_url?: string; processing_status: string; created_at: string; extracted_text?: string }
export interface Job { id: string; title: string; company: string; location: string; description: string; requirements: string; salary_range?: string; employment_type: string; source_url?: string; is_active: boolean; created_at: string; application_deadline?: string }
export interface JobMatch { id: string; job: Job; similarity_score: number; match_reason: string; status: string; created_at: string }
export interface MatchExplanation { job: Job; similarity_score: number; tier: string; match_reason: string; skill_overlap: { matched: string[]; missing: string[] } }
export interface SearchResult { results: (Job & { combined_score: number; match_reason: string })[]; total: number; page: number; page_size: number; total_pages: number }
export interface Application { id: string; job: Job; status: string; cover_letter?: string; hr_notes?: string; created_at: string; updated_at: string }
export interface ApplicationStats { total_applications: number; pending: number; reviewed: number; shortlisted: number; rejected: number; accepted: number }
export interface CoachingSession { session_id: string; job_title?: string; company?: string; session_type: string; personality: string; current_iri: number; total_questions: number; greeting?: string; questions?: Question[]; status: string; iri_score?: IRIScore }
export interface Question { question_number: number; question: string; type: string; difficulty?: string; time_limit_seconds: number; hints: string[]; what_we_look_for?: string }
export interface IRIScore { overall_score: number; communication: number; technical_accuracy: number; confidence: number; structure: number; readiness_level: string; next_step: string }
export interface IRIData { current_iri: number; readiness_level: string; breakdown: { communication: number; technical_accuracy: number; confidence: number; structure: number }; history: { score: number; date: string }[]; total_sessions: number }
export interface GeneratedCV { cv_id: string; file_name: string; file_format: string; storage_url?: string; generated_at: string }
export interface Notification { id: string; type: string; title: string; message: string; is_read: boolean; related_job_id?: string; related_application_id?: string; created_at: string }
export interface NotificationsResponse { notifications: Notification[]; total: number; unread: number }
export interface GraduateDashboard { user: User; profile: { exists: boolean; completeness: number; headline: string; target_role: string; skills_count: number; iri_score: number }; job_matches: { total: number; new_this_week: number; top_match_score: number; top_match_title: string }; applications: ApplicationStats & { recent_applications: Application[] }; recent_applications: Application[]; coaching: { total_sessions: number; current_iri: number; communication: number; technical_accuracy: number; confidence: number; structure: number; iri_history: { score: number; date: string }[]; readiness_level: string }; generated_cvs: number; unread_notifications: number; next_steps: { priority: number; action: string; description: string; link: string; icon: string }[] }
export interface HRDashboard { user: User; company: { name: string; status: string }; jobs: { total: number; active: number; closed: number }; applications: { total: number; pending: number; shortlisted: number } }