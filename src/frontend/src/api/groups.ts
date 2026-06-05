import { api } from './client'
import { sessionsApi } from './sessions'
import type { ApiGroup, Session } from '../types'

export interface CreateGroupInput {
  name: string
  description?: string
  /** 初始成员 Agent id 列表；协调者由后端自动加入，不在此列。 */
  member_ids?: string[]
  /** 群组工作目录（必填）。 */
  workdir: string
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

  /**
   * 找回已有群聊 Session 或创建新的。
   * 当前后端 GET /api/sessions 不支持 ?group_id= 过滤，先 list(type=group) 再筛选。
   * 后端加上 group_id query 后可简化为单次 GET。
   */
  findOrCreateSession: async (groupId: string): Promise<Session> => {
    const all = await sessionsApi.list({ type: 'group' })
    const hit = all.find((s) => s.group_id === groupId && s.type === 'group')
    if (hit) return hit
    return sessionsApi.createGroup(groupId)
  },
}
