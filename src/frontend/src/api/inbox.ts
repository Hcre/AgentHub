// Inbox API client — 封装后端 /api/inbox 端点
// 对齐 `src/backend/app/api/routers/inbox.py` + `app/schemas/inbox.py`

import type { DiffLine, InboxItem, InboxType } from '../types'
import { api } from './client'

interface BackendInboxItem {
  id: string
  type: string
  title: string
  summary: string
  actor: string | null
  actor_name: string | null
  when: string | null
  payload: { diff?: DiffLine[]; impact?: string } & Record<string, unknown>
  status: string
  resolution: string | null
  unread: boolean
  created_at: string
  updated_at: string
}

interface BackendInboxList {
  items: BackendInboxItem[]
  unread_count: number
}

function toUiItem(b: BackendInboxItem): InboxItem {
  return {
    id: b.id,
    type: b.type as InboxType,
    title: b.title,
    summary: b.summary,
    actor: b.actor ?? undefined,
    actorName: b.actor_name ?? undefined,
    when: b.when ?? '',
    diff: b.payload?.diff,
    impact: b.payload?.impact,
    unread: b.unread,
  }
}

export type ResolveAction = 'approve' | 'reject'

export const inboxApi = {
  list: async (): Promise<InboxItem[]> => {
    const res = await api.get<BackendInboxList>('/api/inbox')
    return res.items.map(toUiItem)
  },

  unreadCount: async (): Promise<number> => {
    const res = await api.get<{ unread_count: number }>('/api/inbox/unread-count')
    return res.unread_count
  },

  markRead: (id: string) => api.post<BackendInboxItem>(`/api/inbox/${id}/read`, {}),

  resolve: (id: string, action: ResolveAction) =>
    api.post<BackendInboxItem>(`/api/inbox/${id}/resolve`, { action }),
}
