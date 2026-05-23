import { useEffect } from 'react'
import { MessageSquare, Moon, Sun } from 'lucide-react'
import { useUIStore } from './stores/uiStore'

/**
 * Phase 0 占位页：验证 Tailwind 设计 token、glass-panel、
 * lucide-react 图标与 Zustand store 均可用。Phase 1 起替换为 AppShell 三栏布局。
 */
function App() {
  const theme = useUIStore((s) => s.theme)
  const toggleTheme = useUIStore((s) => s.toggleTheme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="glass-panel flex w-full max-w-md flex-col gap-5 rounded-[var(--radius)] border border-border p-8 text-card-foreground shadow-xl">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand text-brand-foreground">
            <MessageSquare size={22} strokeWidth={2} />
          </span>
          <div>
            <h1 className="text-lg font-semibold">AgentHub</h1>
            <p className="text-sm text-muted-foreground">Phase 0 — 工程基座就绪</p>
          </div>
        </div>

        <p className="text-sm text-muted-foreground">
          Vite + React + TypeScript + Tailwind v4 + Zustand 已配置。设计 token、
          <code className="rounded bg-muted px-1 py-0.5 text-foreground">glass-panel</code>、lucide
          图标与状态管理均可用。
        </p>

        <button
          type="button"
          onClick={toggleTheme}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-foreground transition hover:bg-brand-deep"
        >
          {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          切换到{theme === 'light' ? '暗色' : '浅色'}主题
        </button>
      </div>
    </div>
  )
}

export default App
