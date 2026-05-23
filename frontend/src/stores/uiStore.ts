import { create } from 'zustand'

export type Theme = 'light' | 'dark'

/** 中心区路由段：聊天 / 收件箱 / 任务 / 日历 / 群组 / 助手详情 */
export type Section = 'chat' | 'inbox' | 'tasks' | 'calendar' | 'group' | 'agent-detail'

interface UIState {
  theme: Theme
  sidebarCollapsed: boolean
  rightCollapsed: boolean
  section: Section
  /** 中心区当前 Tab（chat / tasks / activity / ...） */
  activeTab: string
  activeAgentId: string | null
  activeConversationId: string | null

  toggleTheme: () => void
  toggleSidebar: () => void
  toggleRight: () => void
  setSection: (section: Section) => void
  setActiveTab: (tab: string) => void
  /** 打开某助手的某会话（默认进入聊天） */
  openConversation: (agentId: string, conversationId: string) => void
}

/**
 * 全局 UI 状态（前端实施计划 §1.4）。Phase 1 含三栏折叠、路由段、
 * Tab 与当前会话；业务数据由各 domain store 承载。
 */
export const useUIStore = create<UIState>((set) => ({
  theme: 'light',
  sidebarCollapsed: false,
  rightCollapsed: false,
  section: 'chat',
  activeTab: 'chat',
  activeAgentId: 'editor',
  activeConversationId: 'c2',

  toggleTheme: () => set((s) => ({ theme: s.theme === 'light' ? 'dark' : 'light' })),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  toggleRight: () => set((s) => ({ rightCollapsed: !s.rightCollapsed })),
  setSection: (section) => set({ section }),
  setActiveTab: (activeTab) => set({ activeTab }),
  openConversation: (agentId, conversationId) =>
    set({
      section: 'chat',
      activeTab: 'chat',
      activeAgentId: agentId,
      activeConversationId: conversationId,
    }),
}))
