import { create } from 'zustand'

export type Theme = 'light' | 'dim' | 'dark'
export type AccentId = 'coral' | 'blue' | 'sage' | 'plum'
export type Density = 'comfort' | 'compact'
export type HeadingFont = 'Geist' | 'Source Serif 4' | 'Instrument Serif' | 'IBM Plex Sans'

/** 中心区路由段：聊天 / 收件箱 / 任务 / 日历 / 群组主页 / 群聊 / 助手详情 / Skill 市场 / 设置 */
export type Section = 'chat' | 'inbox' | 'tasks' | 'calendar' | 'groups' | 'group' | 'agent-detail' | 'skills-market' | 'api-keys'

interface UIState {
  theme: Theme
  accent: AccentId
  density: Density
  headingFont: HeadingFont
  sidebarCollapsed: boolean
  rightCollapsed: boolean
  section: Section
  /** 中心区当前 Tab（chat / tasks / activity / ...） */
  activeTab: string
  activeAgentId: string | null
  activeConversationId: string | null
  activeGroupId: string | null

  toggleTheme: () => void
  setTheme: (theme: Theme) => void
  setAccent: (accent: AccentId) => void
  setDensity: (density: Density) => void
  setHeadingFont: (font: HeadingFont) => void
  toggleSidebar: () => void
  toggleRight: () => void
  setSection: (section: Section) => void
  setActiveTab: (tab: string) => void
  /** 打开某助手的某会话（默认进入聊天） */
  openConversation: (agentId: string, conversationId: string) => void
  /** 进入某频道的群聊 */
  openGroup: (groupId: string) => void
  /** 查看某助手详情 */
  viewAgent: (agentId: string) => void
  /** AI 队友「详细」抽屉：null = 关闭 */
  agentDrawerAgentId: string | null
  openAgentDrawer: (agentId: string) => void
  closeAgentDrawer: () => void
}

/**
 * 全局 UI 状态（前端实施计划 §1.4）。Phase 1 含三栏折叠、路由段、
 * Tab 与当前会话；业务数据由各 domain store 承载。
 */
export const useUIStore = create<UIState>((set) => ({
  theme: 'light',
  accent: 'coral',
  density: 'comfort',
  headingFont: 'Source Serif 4',
  sidebarCollapsed: false,
  rightCollapsed: false,
  section: 'chat',
  activeTab: 'chat',
  activeAgentId: 'editor',
  activeConversationId: 'c2',
  activeGroupId: 'design',

  toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
  setTheme: (theme) => set({ theme }),
  setAccent: (accent) => set({ accent }),
  setDensity: (density) => set({ density }),
  setHeadingFont: (headingFont) => set({ headingFont }),
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
  openGroup: (groupId) => set({ section: 'group', activeGroupId: groupId }),
  viewAgent: (agentId) => set({ section: 'agent-detail', activeAgentId: agentId }),

  agentDrawerAgentId: null,
  openAgentDrawer: (agentId) => set({ agentDrawerAgentId: agentId }),
  closeAgentDrawer: () => set({ agentDrawerAgentId: null }),
}))
