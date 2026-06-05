import { create } from 'zustand'
import { persist } from 'zustand/middleware'

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
  /** 文件预览面板的全局工作目录兜底：当前会话/群组无 workdir 时用这个 */
  fileWorkdir: string | null
  /** 右栏（预览面板）是否折叠 */
  rightPanelCollapsed: boolean
  /** 右栏（预览面板）宽度（px），拖拽全局分界线时更新；持久化 */
  rightPanelWidth: number
  /** 右栏（预览面板）内的预览 tab 列表（files / diff / deploy / webpage） */
  previewTabs: PreviewTab[]
  /** 右栏内当前激活的预览 tab id */
  activePreviewTabId: string | null

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
  /** 设置/清空 文件预览全局 workdir */
  setFileWorkdir: (w: string | null) => void
  /** 整个右栏（预览面板）折叠/展开 */
  toggleRightPanel: () => void
  setRightPanelCollapsed: (v: boolean) => void
  /** 右栏宽度 */
  setRightPanelWidth: (w: number) => void
  /** 预览 tab 操作 */
  addPreviewTab: (tab: PreviewTab) => void
  removePreviewTab: (id: string) => void
  setActivePreviewTab: (id: string | null) => void
}

/** 预览 tab（RightPanel 内的 PreviewMode tab） */
export interface PreviewTab {
  id: string
  type: 'files' | 'diff' | 'deploy' | 'webpage'
  label: string
  workdir?: string
}

/**
 * 全局 UI 状态（前端实施计划 §1.4）。Phase 1 含三栏折叠、路由段、
 * Tab 与当前会话；业务数据由各 domain store 承载。
 *
 * 持久化：只持久化布局类（rightPanelWidth 等），不持久化运行时临时状态
 * （如 agentDrawerAgentId、当前 section 等）。
 */
export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
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
  fileWorkdir: null,
  rightPanelCollapsed: false,
  rightPanelWidth: 380,
  previewTabs: [],
  activePreviewTabId: null,

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
  setFileWorkdir: (fileWorkdir) => set({ fileWorkdir }),
  toggleRightPanel: () => set((s) => ({ rightPanelCollapsed: !s.rightPanelCollapsed })),
  setRightPanelCollapsed: (v) => set({ rightPanelCollapsed: v }),
  setRightPanelWidth: (rightPanelWidth) => set({ rightPanelWidth }),
  addPreviewTab: (tab) => set((s) => ({ previewTabs: [...s.previewTabs, tab] })),
  removePreviewTab: (id) =>
    set((s) => {
      const next = s.previewTabs.filter((t) => t.id !== id)
      let nextActive = s.activePreviewTabId
      if (s.activePreviewTabId === id) {
        const idx = s.previewTabs.findIndex((t) => t.id === id)
        const fallback = next[Math.max(0, idx - 1)] ?? next[0] ?? null
        nextActive = fallback?.id ?? null
      }
      return { previewTabs: next, activePreviewTabId: nextActive }
    }),
  setActivePreviewTab: (id) => set({ activePreviewTabId: id }),
    }),
    {
      name: 'agenthub-ui',
      partialize: (state) => ({
        // 只持久化布局/UI 偏好 + 预览面板用户态；不持久化路由段、当前选中
        fileWorkdir: state.fileWorkdir,
        rightPanelCollapsed: state.rightPanelCollapsed,
        rightPanelWidth: state.rightPanelWidth,
        previewTabs: state.previewTabs,
        activePreviewTabId: state.activePreviewTabId,
        theme: state.theme,
        accent: state.accent,
        density: state.density,
        headingFont: state.headingFont,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
      // v1 → v2：清掉 fileTreeWidth / fileTreeCollapsed（FilePreview 已不引用）
      version: 2,
      migrate: (persisted) => {
        // 旧版里的死字段直接丢弃
        if (persisted && typeof persisted === 'object') {
          const p = persisted as Record<string, unknown>
          delete p.fileTreeWidth
          delete p.fileTreeCollapsed
        }
        return persisted as UIState
      },
      merge: (persisted, current) => ({ ...current, ...(persisted as object) }),
    },
  ),
)
