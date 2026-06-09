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

  /**
   * t7 拓展：群组置顶/取消置顶。
   *
   * 设计权衡：复用 backing Session.pinned 而非给 Group 实体加列
   * - 收益：0 alembic 迁移 + 0 entity 改动 + 复用 t7 已落地的 Session.pinned 列 + service + 401/403/422 校验
   * - 代价：删 group 时级联删 session → pin 状态丢失；新建 group 自动建 session → 默认 pinned=false
   * - 决策点：等真正出现"删 group 要保留 pin"需求时再迁到 Group.pinned（alembic 0024 + entity）
   *
   * 实现：没 sessionId 时先 findOrCreateSession 拿，再 PATCH `/api/sessions/{id}` body={pinned}
   * 复用 sessionsApi.patch → 401/403/422 链路与单聊一致
   */
  togglePin: async (
    groupId: string,
    sessionId: string | null | undefined,
    nextPinned: boolean,
  ): Promise<void> => {
    let sid = sessionId
    if (!sid) {
      const s = await groupsApi.findOrCreateSession(groupId)
      sid = s.id
    }
    await sessionsApi.patch(sid, { pinned: nextPinned })
  },
}
