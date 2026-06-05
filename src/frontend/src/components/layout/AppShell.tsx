import { cn } from '../../lib/cn'
import { useUIStore } from '../../stores/uiStore'
import { AgentDetailDrawer } from '../agent/AgentDetailDrawer'
import { TweaksPanel } from '../tweaks/TweaksPanel'
import { Icon } from '../ui'
import { CenterPanel } from './CenterPanel'
import { LeftPanel } from './LeftPanel'
import { NavRail } from './NavRail'
import { RightPanel } from './RightPanel'

export function AppShell() {
  const { sidebarCollapsed, rightCollapsed, section, toggleSidebar } = useUIStore()
  // 会话列表仅在「会话」视图出现；其他视图（AI 队友 / 群组 / Skill / 设置）下隐藏
  const inChat = section === 'chat'
  // 右侧「阶段/产出」面板：私聊 + 群聊都展示（group 的 panelRight 按钮可折叠它）
  const showRight = (inChat || section === 'group') && !rightCollapsed
  // 折叠按钮：仅在会话视图下且已折叠时出现（其他视图无意义）
  const showLeftExpand = inChat && sidebarCollapsed

  return (
    <div className="flex h-full">
      {/* 最左侧导航栏（60px，固定显示） */}
      <div className="flex-shrink-0 p-2.5 pr-1.5">
        <NavRail />
      </div>

      {/* 左侧栏（会话列表）：inChat（私聊）或 group（群聊）时渲染，
          且 sidebarCollapsed 时不渲染 aside（避免 border/glass-panel 在 0 宽处残留 1px 线） */}
      {(inChat || section === 'group') && (
        <div
          className={cn(
            'flex-shrink-0 overflow-hidden py-2.5 pl-1.5 pr-1.5 transition-all duration-300 ease-out',
            sidebarCollapsed ? 'w-0 p-0' : 'w-[280px]',
          )}
        >
          {!sidebarCollapsed && <LeftPanel />}
        </div>
      )}

      {/* 折叠后浮动展开按钮（仅会话视图且已折叠时） */}
      {showLeftExpand && (
        <button
          onClick={toggleSidebar}
          title="展开侧边栏"
          className="animate-[var(--animate-fade-in)] fixed left-3 top-3 z-30 grid h-9 w-9 place-items-center rounded-lg border glass-strong text-muted-foreground shadow-sm transition-colors hover:text-foreground"
        >
          <Icon name="panelLeft" className="h-3.5 w-3.5" />
        </button>
      )}

      {/* 中心区 */}
      <div className="min-w-0 flex-1 py-2.5 pl-1.5">
        <CenterPanel />
      </div>

      {/* 右侧栏 */}
      {showRight && (
        <div className="w-[340px] flex-shrink-0 p-2.5 pl-1.5">
          <RightPanel />
        </div>
      )}

      <TweaksPanel />
      <AgentDetailDrawer />
    </div>
  )
}
