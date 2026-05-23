import { create } from 'zustand'

export type Theme = 'light' | 'dark'

interface UIState {
  theme: Theme
  toggleTheme: () => void
}

/**
 * 全局 UI 状态。Phase 0 仅含主题切换，Phase 1 按
 * 前端实施计划 §1.4 扩展（sidebarCollapsed / activeTab 等）。
 */
export const useUIStore = create<UIState>((set) => ({
  theme: 'light',
  toggleTheme: () => set((state) => ({ theme: state.theme === 'light' ? 'dark' : 'light' })),
}))
