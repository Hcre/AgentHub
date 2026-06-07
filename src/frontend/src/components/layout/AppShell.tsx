import { useEffect, useRef, useState } from 'react'
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
const RIGHT_PANEL_MIN = 120 // 拖到 120px 以下 → 整个右栏隐藏
const RIGHT_PANEL_DEFAULT = 380
const RIGHT_PANEL_MAX_RATIO = 0.7 // 占 viewport 最大 70%

export function AppShell() {
  const { sidebarCollapsed, section, toggleSidebar } = useUIStore()
  const rightPanelCollapsed = useUIStore((s) => s.rightPanelCollapsed)
  const rightPanelWidth = useUIStore((s) => s.rightPanelWidth)
  const setRightPanelWidth = useUIStore((s) => s.setRightPanelWidth)
  const setRightPanelCollapsed = useUIStore((s) => s.setRightPanelCollapsed)
  const shellRef = useRef<HTMLDivElement>(null)

  const inChat = section === 'chat'
  const showRight = (inChat || section === 'group') && !rightPanelCollapsed
  const showLeftExpand = inChat && sidebarCollapsed

  return (
    <div ref={shellRef} className="relative mx-auto flex h-full w-full max-w-[1920px]">
      {/* 最左侧导航栏（clamp(56px, 4.5vw, 88px) 自适应） */}
      <div className="flex-shrink-0 p-2.5 pr-1.5">
        <NavRail />
      </div>

      {/* 左侧栏（会话列表，clamp(240px, 18vw, 320px) 自适应） */}
      {(inChat || section === 'group') && (
        <div
          className={cn(
            'flex-shrink-0 overflow-hidden py-2.5 pl-1.5 pr-1.5 transition-all duration-300 ease-out',
            sidebarCollapsed ? 'w-0 p-0' : 'w-[clamp(240px,18vw,320px)]',
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

      {/* 中心区 ↔ 右栏之间的可拖拽分界线（仅未折叠时） */}
      {showRight && (
        <RightPanelResizeHandle
          containerRef={shellRef}
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

      {/* 右侧栏（折叠时不渲染；宽度由 uiStore.rightPanelWidth 决定，拖拽 math 钳到视口 × 0.7） */}
      {showRight && (
        <div
          style={{ width: rightPanelWidth }}
          className="ah-right-panel flex-shrink-0 p-2.5 pl-1.5 transition-all duration-200"
        >
          <RightPanel />
        </div>
      )}

      <TweaksPanel />
      <AgentDetailDrawer />
    </div>
  )
}

// ── 全局三栏分界线（CenterPanel ↔ RightPanel） ─────────────────────

function RightPanelResizeHandle({
  containerRef,
  currentWidth,
  onResize,
  onReset,
}: {
  containerRef: React.RefObject<HTMLDivElement | null>
  currentWidth: number
  onResize: (w: number) => void
  onReset: () => void
}) {
  const [dragging, setDragging] = useState(false)
  const startXRef = useRef(0)
  const startWRef = useRef(currentWidth)
  const onResizeRef = useRef(onResize)
  const onResetRef = useRef(onReset)
  useEffect(() => {
    onResizeRef.current = onResize
    onResetRef.current = onReset
  }, [onResize, onReset])

  const handlePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    const target = e.currentTarget
    target.setPointerCapture(e.pointerId)
    startXRef.current = e.clientX
    startWRef.current = currentWidth
    setDragging(true)
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
  }

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return
    const container = containerRef.current
    if (!container) return
    const rect = container.getBoundingClientRect()
    // 右栏在最右：向左拖 → 右栏变宽。所以 newWidth = startW + (startX - e.clientX)
    const delta = startXRef.current - e.clientX
    const raw = startWRef.current + delta
    const maxW = rect.width * RIGHT_PANEL_MAX_RATIO
    const next = Math.max(0, Math.min(raw, maxW))
    onResizeRef.current(next)
  }

  const handlePointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return
    e.currentTarget.releasePointerCapture(e.pointerId)
    setDragging(false)
    document.body.style.cursor = ''
    document.body.style.userSelect = ''
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerUp}
      onDoubleClick={() => onResetRef.current()}
      title="拖拽调整宽度 · 双击重置默认"
      data-dragging={dragging ? 'true' : 'false'}
      // 8px 命中区（之前 4px 太窄，大窗口更难点中）：默认有极淡灰背景让用户能看见，
      // hover/drag 时变紫
      style={{
        flex: '0 0 8px',
        width: 8,
        minWidth: 8,
        maxWidth: 8,
        height: '100%',
        cursor: 'col-resize',
        position: 'relative',
        background: dragging
          ? 'rgba(124,58,237,0.15)'
          : 'rgba(113,113,130,0.08)',
        transition: 'background 120ms',
        touchAction: 'none',
        userSelect: 'none',
      }}
      onMouseEnter={(e) => {
        ;(e.currentTarget as HTMLDivElement).style.background = 'rgba(124,58,237,0.10)'
      }}
      onMouseLeave={(e) => {
        if (!dragging) (e.currentTarget as HTMLDivElement).style.background = 'rgba(113,113,130,0.08)'
      }}
    />
  )
}
