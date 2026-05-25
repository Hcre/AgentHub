import { api } from './client'
import type { ApiGroup } from '../types'

export interface CreateGroupInput {
  name: string
  description?: string
  /** 初始成员 Agent id 列表；协调者由后端自动加入，不在此列。 */
  member_ids?: string[]
}

export interface NameCheckResult {
  available: boolean
  reason?: string
}

export const groupsApi = {
  list: () => api.get<ApiGroup[]>('/api/groups'),
  create: (input: CreateGroupInput) => api.post<ApiGroup>('/api/groups', input),
  rename: (id: string, name: string) => api.patch<ApiGroup>(`/api/groups/${id}`, { name }),
  remove: (id: string) => api.del<void>(`/api/groups/${id}`),
  checkName: (name: string) =>
    api.get<NameCheckResult>(`/api/groups/check-name?name=${encodeURIComponent(name)}`),
}
