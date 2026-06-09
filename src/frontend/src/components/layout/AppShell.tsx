import { useEffect, useRef, useState } from 'react'
import { cn } from '../../lib/cn'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import { useUIStore } from '../../stores/uiStore'
import { AgentDetailDrawer } from '../agent/AgentDetailDrawer'
import { TweaksPanel } from '../tweaks/TweaksPanel'
import { Icon } from '../ui'
import { CenterPanel } from './CenterPanel'
import { LeftPanel } from './LeftPanel'
import { NavRail } from './NavRail'
import { RightPanel } from './RightPanel'

/** 右栏宽度边界（px / 比例） */
const RIGHT_PANEL_MIN = 120
const RIGHT_PANEL_DEFAULT = 380
const RIGHT_PANEL_MAX_RATIO = 0.7

/** 移动 H5 断点：< 768px 视为手机。 */
const MOBILE_QUERY = '(max-width: 767px)'

export function AppShell() {
  const isMobile = useMediaQuery(MOBILE_QUERY)
  const { sidebarCollapsed, section, toggleSidebar } = useUIStore()
  const rightPanelCollapsed = useUIStore((s) => s.rightPanelCollapsed)
  const rightPanelWidth = useUIStore((s) => s.rightPanelWidth)
  const setRightPanelWidth = useUIStore((s) => s.setRightPanelWidth)
  const setRightPanelCollapsed = useUIStore((s) => s.setRightPanelCollapsed)
  const shellRef = useRef<HTMLDivElement>(null)

  const inChat = section === 'chat'
  const showRight = (inChat || section === 'group') && !rightPanelCollapsed
  const showLeftExpand = inChat && sidebarCollapsed

  // ⌘B / Ctrl+B：折叠/展开预览侧边栏
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault()
        e.stopPropagation()
        useUIStore.getState().toggleRightPanel()
      }
    }
    window.addEventListener('keydown', onKey, { capture: true })
    return () => window.removeEventListener('keydown', onKey, { capture: true })
  }, [])

  // 移动端：抽屉打开时 Esc 关闭
  const [mobileLeftOpen, setMobileLeftOpen] = useState(false)
  const [mobileRightOpen, setMobileRightOpen] = useState(false)
  useEffect(() => {
    if (!isMobile) return
    const anyOpen = mobileLeftOpen || mobileRightOpen
    if (!anyOpen) return
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') {
        setMobileLeftOpen(false)
        setMobileRightOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [isMobile, mobileLeftOpen, mobileRightOpen])

  if (isMobile) {
    const inDrawerSection =
      section === 'chat' || section === 'group' || section === 'agent-detail'
    return (
      <div
        ref={shellRef}
        data-testid="app-shell-mobile"
        className="relative flex h-full w-full flex-col"
      >
        <header
          data-testid="mobile-header"
          className="flex h-12 flex-shrink-0 items-center gap-2 border-b border-border/70 bg-background/95 px-2 backdrop-blur"
        >
          <button
            type="button"
            onClick={() => setMobileLeftOpen(true)}
            aria-label="打开导航与会话列表"
            aria-expanded={mobileLeftOpen}
            data-testid="mobile-hamburger"
            className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Icon name="menu" className="h-4 w-4" strokeWidth={2} />
          </button>
          <div className="min-w-0 flex-1 truncate text-center text-[14px] font-medium text-foreground">
            {sectionTitle(section)}
          </div>
          {inDrawerSection && (
            <button
              type="button"
              onClick={() => setMobileRightOpen(true)}
              aria-label="打开预览面板"
              aria-expanded={mobileRightOpen}
              data-testid="mobile-right-toggle"
              className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Icon name="panelRight" className="h-4 w-4" />
            </button>
          )}
        </header>

        <main className="min-h-0 flex-1">
          <CenterPanel />
        </main>

        {mobileLeftOpen && (
          <MobileDrawer
            testId="mobile-left-drawer"
            side="left"
            onClose={() => setMobileLeftOpen(false)}
            ariaLabel="导航与会话列表"
          >
            <div className="flex h-full gap-2 p-2">
              <div className="flex-shrink-0">
                <NavRail />
              </div>
              <div className="min-w-0 flex-1">
                <LeftPanel />
              </div>
            </div>
          </MobileDrawer>
        )}

        {mobileRightOpen && (
          <MobileDrawer
            testId="mobile-right-drawer"
            side="right"
            onClose={() => setMobileRightOpen(false)}
            ariaLabel="预览面板"
          >
            <div className="h-full p-2">
              <RightPanel />
            </div>
          </MobileDrawer>
        )}

        <TweaksPanel />
        <AgentDetailDrawer />
      </div>
    )
  }

  return (
    <div
      ref={shellRef}
      data-testid="app-shell-desktop"
      className="relative mx-auto flex h-full w-full max-w-[1920px]"
    >
      <div className="flex-shrink-0 p-2.5 pr-1.5">
        <NavRail />
      </div>

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

      <div className="min-w-0 flex-1 py-2.5 pl-1.5">
        <CenterPanel />
      </div>

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

function MobileDrawer({
  testId,
  side,
  onClose,
  ariaLabel,
  children,
}: {
  testId: string
  side: 'left' | 'right'
  onClose: () => void
  ariaLabel: string
  children: React.ReactNode
}) {
  return (
    <div
      data-testid={testId}
      role="dialog"
      aria-modal="true"
      aria-label={ariaLabel}
      className="fixed inset-0 z-50 flex"
    >
      <button
        type="button"
        aria-label="关闭"
        onClick={onClose}
        data-testid={`${testId}-scrim`}
        className="flex-1 cursor-default bg-black/40"
      />
      <div
        className={cn(
          'h-full w-[min(85vw,360px)] flex-shrink-0 border-border bg-background shadow-xl',
          side === 'left' ? 'border-r' : 'ml-auto border-l',
        )}
      >
        {children}
      </div>
    </div>
  )
}

function sectionTitle(section: string): string {
  switch (section) {
    case 'chat':
      return '会话'
    case 'group':
      return '群聊'
    case 'groups':
      return '群组'
    case 'agent-detail':
      return 'AI 队友'
    case 'skills-market':
      return '技能市场'
    case 'inbox':
      return '收件箱'
    case 'tasks':
      return '任务'
    case 'calendar':
      return '日历'
    case 'settings':
      return '设置'
    default:
      return 'AgentHub'
  }
}

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
