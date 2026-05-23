import { create } from 'zustand'
import { inbox } from '../data/extra'
import type { InboxItem } from '../types'

// 真实接入：items 来自 GET /api/inbox；resolve 对应批准/驳回 POST，
// 与群聊 requiresApproval 流程对接（见 group/HANDOFF.md）。
interface InboxState {
  items: InboxItem[]
  markRead: (id: string) => void
  resolve: (id: string) => void // 批准或驳回后从列表移除
}

export const useInboxStore = create<InboxState>((set) => ({
  items: inbox,
  markRead: (id) =>
    set((s) => ({ items: s.items.map((i) => (i.id === id ? { ...i, unread: false } : i)) })),
  resolve: (id) => set((s) => ({ items: s.items.filter((i) => i.id !== id) })),
}))
