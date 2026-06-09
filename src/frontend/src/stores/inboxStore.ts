import { create } from 'zustand'
import { inboxApi, type ResolveAction } from '../api/inbox'
import type { InboxItem } from '../types'

// 真实接入：items 来自 GET /api/inbox；resolve 走 POST /api/inbox/{id}/resolve
// （批准/驳回），与群聊 requiresApproval 流程对接。
interface InboxState {
  items: InboxItem[]
  loaded: boolean
  loading: boolean

  load: () => Promise<void>
  markRead: (id: string) => void
  resolve: (id: string, action: ResolveAction) => void // 批准/驳回后从列表移除
}

export const useInboxStore = create<InboxState>((set, get) => ({
  items: [],
  loaded: false,
  loading: false,

  load: async () => {
    if (get().loading) return
    set({ loading: true })
    try {
      const items = await inboxApi.list()
      set({ items, loaded: true })
    } catch (err) {
      console.error('加载收件箱失败', err)
    } finally {
      set({ loading: false })
    }
  },

  markRead: (id) => {
    const prev = get().items
    set({ items: prev.map((i) => (i.id === id ? { ...i, unread: false } : i)) })
    inboxApi.markRead(id).catch((err) => {
      console.error('标记已读失败', err)
      set({ items: prev })
    })
  },

  resolve: (id, action) => {
    const prev = get().items
    set({ items: prev.filter((i) => i.id !== id) })
    inboxApi.resolve(id, action).catch((err) => {
      console.error('处理审批失败', err)
      set({ items: prev })
    })
  },
}))
