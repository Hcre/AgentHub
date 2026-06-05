import { useEffect, useRef } from 'react'
import { cn } from '../../lib/cn'
import { useUIStore } from '../../stores/uiStore'
import { AgentDetailDrawer } from '../agent/AgentDetailDrawer'
import { TweaksPanel } from '../tweaks/TweaksPanel'
import { Icon } from '../ui'
import { CenterPanel } from './CenterPanel'
import { LeftPanel } from './LeftPanel'
import { NavRail } from './NavRail'
import { RightPanel } from './RightPanel'

/** 右栏宽度边界（px / 比例） */
const RIGHT_PANEL_MIN = 240
const RIGHT_PANEL_DEFAULT = 380
const RIGHT_PANEL_MAX_RATIO = 0.7

export function AppShell() {
  const { sidebarCollapsed, rightCollapsed, section, toggleSidebar } = useUIStore()
  const rightPanelCollapsed = useUIStore((s) => s.rightPanelCollapsed)
  const rightPanelWidth = useUIStore((s) => s.rightPanelWidth)
  const setRightPanelWidth = useUIStore((s) => s.setRightPanelWidth)
  const setRightPanelCollapsed = useUIStore((s) => s.setRightPanelCollapsed)

  const inChat = section === 'chat'
  const showRight = (inChat || section === 'group') && !rightCollapsed
  const showLeftExpand = inChat && sidebarCollapsed

  return (
    <div className="flex h-full">
      {/* 最左侧导航栏（60px） */}
      <div className="flex-shrink-0 p-2.5 pr-1.5">
        <NavRail />
      </div>

      {/* 左侧栏（会话列表） */}
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

      {showLeftExpand && (
        <button
          onClick={toggleSidebar}
          title="展开侧边栏"
          className="animate-[var(--animate-fade-in)] fixed left-3 top-3 z-30 grid h-9 w-9 place-items-center rounded-lg border glass-strong text-muted-foreground shadow-sm transition-colors hover:text-foreground"
        >
          <Icon name="panelLeft" className="h-3.5 w-3.5" />
        </button>
      )}

      {/* 中心区（flex-1，吃掉所有剩余空间） */}
      <div className="min-w-0 flex-1 py-2.5 pl-1.5">
        <CenterPanel />
      </div>

      {/* 中心区 ↔ 右栏 之间的拖拽 handle —— flex 兄弟，不在右栏内 */}
      {showRight && !rightPanelCollapsed && (
        <ResizeHandle
          currentWidth={rightPanelWidth}
          onResize={(w) => {
            if (w < RIGHT_PANEL_MIN) {
              setRightPanelCollapsed(true)
            } else {
              setRightPanelWidth(w)
            }
          }}
          onReset={() => setRightPanelWidth(RIGHT_PANEL_DEFAULT)}
        />
      )}

      {/* 右侧栏（预览面板）—— 不挤压内容，不加 outline，不加 marginLeft hack */}
      {showRight && (
        <div
          style={{ width: rightPanelCollapsed ? 'auto' : rightPanelWidth }}
          className={cn(
            'flex-shrink-0 p-2.5 pl-1.5 transition-all duration-200',
            rightPanelCollapsed && 'w-auto',
          )}
        >
          <RightPanel />
        </div>
      )}

      <TweaksPanel />
      <AgentDetailDrawer />
    </div>
  )
}

/**
 * 全局三栏分界线（CenterPanel ↔ RightPanel 之间的 flex 兄弟）
 * - 不嵌在右栏内部，所以不挤压右栏内容
 * - 内联 style width:16 + flex 三件套保底，Tailwind 失效也不影响
 * - 视觉强行用红底+黄边，30 天后变淡
 */
function ResizeHandle({
  currentWidth,
  onResize,
  onReset,
}: {
  currentWidth: number
  onResize: (w: number) => void
  onReset: () => void
}) {
  const startXRef = useRef(0)
  const startWRef = useRef(currentWidth)
  const draggingRef = useRef(false)
  const onResizeRef = useRef(onResize)
  const onResetRef = useRef(onReset)
  useEffect(() => {
    onResizeRef.current = onResize
    onResetRef.current = onReset
  }, [onResize, onReset])
  useEffect(() => {
    startWRef.current = currentWidth
  }, [currentWidth])

  // 挂载诊断
  useEffect(() => {
    console.log('[resize-handle] MOUNTED, currentWidth =', currentWidth, 'px')
    return () => console.log('[resize-handle] UNMOUNTED')
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    const target = e.currentTarget
    target.setPointerCapture(e.pointerId)
    startXRef.current = e.clientX
    startWRef.current = currentWidth
    draggingRef.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    console.log('[resize-handle] pointerdown', e.clientX)
  }

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return
    const shellEl = e.currentTarget.parentElement
    if (!shellEl) return
    const rect = shellEl.getBoundingClientRect()
    const delta = startXRef.current - e.clientX
    const raw = startWRef.current + delta
    const maxW = rect.width * RIGHT_PANEL_MAX_RATIO
    const next = Math.max(0, Math.min(raw, maxW))
    onResizeRef.current(next)
  }

  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!draggingRef.current) return
    try {
      e.currentTarget.releasePointerCapture(e.pointerId)
    } catch {
      // ignore
    }
    draggingRef.current = false
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
    console.log('[resize-handle] pointerup')
  }

  return (
    <div
      data-testid="resize-handle"
      role="separator"
      aria-orientation="vertical"
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onDoubleClick={() => {
        console.log('[resize-handle] doubleclick — RESET to 380px')
        onResetRef.current()
      }}
      onClick={() => console.log('[resize-handle] click')}
      title="⬌ 拖拽调整宽度 · 双击重置"
      // 内联 style 三件套保底：width + minWidth + maxWidth + flex 0 0 16px
      // 即便 Tailwind v4 的 w-3 / flex-shrink-0 出问题，元素也绝对是 16px 宽
      style={{
        flex: '0 0 16px',
        width: 16,
        minWidth: 16,
        maxWidth: 16,
        alignSelf: 'stretch',
        cursor: 'col-resize',
        background: '#dc2626',
        border: '2px solid #fbbf24',
        boxSizing: 'border-box',
        color: '#fff',
        fontSize: 11,
        fontWeight: 700,
        lineHeight: '12px',
        textAlign: 'center',
        userSelect: 'none',
        touchAction: 'none',
        zIndex: 50,
      }}
    >
      <span
        style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          pointerEvents: 'none',
        }}
      >
        ⬌
      </span>
    </div>
  )
}
