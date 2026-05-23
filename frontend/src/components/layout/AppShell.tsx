import { cn } from '../../lib/cn'
import { useUIStore } from '../../stores/uiStore'
import { Icon } from '../ui'
import { CenterPanel } from './CenterPanel'
import { LeftPanel } from './LeftPanel'
import { RightPanel } from './RightPanel'

export function AppShell() {
  const { sidebarCollapsed, rightCollapsed, section, toggleSidebar } = useUIStore()
  const showRight = (section === 'chat' || section === 'group') && !rightCollapsed

  return (
    <div className="flex h-full">
      {/* 左侧栏 */}
      <div
        className={cn(
          'flex-shrink-0 overflow-hidden p-2.5 pr-1.5 transition-all duration-300 ease-out',
          sidebarCollapsed ? 'w-0 p-0' : 'w-[280px]',
        )}
      >
        <LeftPanel />
      </div>

      {/* 折叠后浮动展开按钮 */}
      {sidebarCollapsed && (
        <button
          onClick={toggleSidebar}
          title="展开侧边栏"
          className="animate-[var(--animate-fade-in)] fixed left-3 top-3 z-30 grid h-9 w-9 place-items-center rounded-lg border glass-strong text-muted-foreground shadow-sm transition-colors hover:text-foreground"
        >
          <Icon name="panelLeft" className="h-3.5 w-3.5" />
        </button>
      )}

      {/* 中心区 */}
      <div className="min-w-0 flex-1 py-2.5">
        <CenterPanel />
      </div>

      {/* 右侧栏 */}
      {showRight && (
        <div className="w-[340px] flex-shrink-0 p-2.5 pl-1.5">
          <RightPanel />
        </div>
      )}
    </div>
  )
}
