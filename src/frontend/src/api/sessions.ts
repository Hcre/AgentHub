import { api } from './client'
import type { Session } from '../types'

export interface MessageOut {
  id: string
  role: string
  content: string
  content_type: string
  sender_agent_id?: string | null
  mentions?: string[]
  created_at?: string
}

export const sessionsApi = {
  list: (params?: { type?: string }) => {
    const qs = params?.type ? `?type=${encodeURIComponent(params.type)}` : ''
    return api.get<Session[]>(`/api/sessions${qs}`)
  },
  createPrivate: (agentId: string, title = '', workspacePath = '') =>
    api.post<Session>('/api/sessions', {
      type: 'private',
      agent_id: agentId,
      title,
      workspace_path: workspacePath,
    }),
  createGroup: (groupId: string, title = '', workspacePath = '') =>
    api.post<Session>('/api/sessions', {
      type: 'group',
      group_id: groupId,
      title,
      workspace_path: workspacePath,
    }),
  messages: (sessionId: string) => api.get<MessageOut[]>(`/api/sessions/${sessionId}/messages`),
  // t7 B-4-P2-CL01：PATCH 接受 pinned 字段翻转置顶状态
  // M1#2 新增 archived 字段翻转归档状态
  patch: (
    sessionId: string,
    body: { title?: string; workspace_path?: string; pinned?: boolean; archived?: boolean },
  ) => api.patch<Session>(`/api/sessions/${sessionId}`, body),
  // 删除单条消息（后端 DELETE /api/messages/{id}，204 无内容，无需 session_id）
  deleteMessage: (messageId: string) => api.del<void>(`/api/messages/${messageId}`),
}
