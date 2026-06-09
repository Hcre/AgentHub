// Deploy API client — 封装后端 /api/deployments 端点
// 对齐 `src/backend/app/api/routers/deploy.py` + `app/schemas/deploy.py`
//
// 端点:
//   POST   /api/deployments         提交部署
//   GET    /api/deployments         列表（按 session_id 过滤）
//   GET    /api/deployments/{id}    详情
//   DELETE /api/deployments/{id}    软删

import { api } from './client'

export type DeployStatus = 'queued' | 'building' | 'ready' | 'failed'

export type DeployTarget = 'static_site' | 'container' | 'package'

export interface Deployment {
  id: string
  session_id: string
  owner_id: string | null
  target: DeployTarget
  entry_file: string | null
  framework: string | null
  status: DeployStatus
  stage: string | null
  progress: number
  preview_url: string | null
  download_url: string | null
  build_logs: string[]
  error_code: string | null
  error_message: string | null
  ttl: number
  created_at: string
  updated_at: string
}

export interface StartDeploymentInput {
  session_id: string
  target: DeployTarget
  entry_file?: string
  framework?: string
  files?: Record<string, string>
}

function qs(params: Record<string, string | number | undefined>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export const deployApi = {
  list: (params: { session_id: string }) =>
    api.get<Deployment[]>(`/api/deployments${qs({ session_id: params.session_id })}`),

  get: (id: string) => api.get<Deployment>(`/api/deployments/${id}`),

  start: (input: StartDeploymentInput) => api.post<Deployment>('/api/deployments', input),

  remove: (id: string) => api.del<void>(`/api/deployments/${id}`),
}
