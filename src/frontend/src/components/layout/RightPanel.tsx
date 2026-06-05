import { forwardRef, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../lib/cn'
import { uid } from '../../lib/id'
import { Icon } from '../ui'
import { PREVIEW_MODES, type PreviewMode } from '../preview/previewModes'
import { FilePreview } from '../preview/FilePreview'
import { useCurrentWorkdir } from './previewContext'
import { useUIStore } from '../../stores/uiStore'

const TAB_LABEL: Record<PreviewMode, string> = {
  files: '文件',
  diff: 'Diff',
  deploy: '部署',
  webpage: '网页',
}

const TAB_ICON: Record<PreviewMode, 'files' | 'diff' | 'rocket' | 'globe'> = {
  files: 'files',
  diff: 'diff',
  deploy: 'rocket',
  webpage: 'globe',
}

/**
 * 右栏 = 内嵌浏览器式 tab 栏
 *   - tab 栏始终显示（无 tab 时也显示 +）
 *   - 点 + 弹下拉菜单（Portal 到 body，不被 overflow 裁剪）
 *   - 选下拉项：新建 tab（或激活已存在的同类型 tab）
 *   - tab × 关闭：保留至少 1 个 tab
 *   - tab 内 workdir 快照：创建时捕获私聊/群组的 workdir
 *   - 状态（tabs / activeId）持久化到 uiStore，刷新后恢复
 */
export function RightPanel() {
  const currentWorkdir = useCurrentWorkdir()
  const tabs = useUIStore((s) => s.previewTabs)
  const activeTabId = useUIStore((s) => s.activePreviewTabId)
  const addPreviewTab = useUIStore((s) => s.addPreviewTab)
  const removePreviewTab = useUIStore((s) => s.removePreviewTab)
  const setActivePreviewTab = useUIStore((s) => s.setActivePreviewTab)
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [dropdownPos, setDropdownPos] = useState<{ top: number; left: number } | null>(null)
  const plusRef = useRef<HTMLButtonElement>(null)
  const menuRef = useRef<HTMLDivElement>(null)

  const activeTab = tabs.find((t) => t.id === activeTabId) ?? null

  // 点击外部关 dropdown（dropdown 在 Portal 里，要同时检查 + 按钮和 dropdown 自身）
  useEffect(() => {
    if (!dropdownOpen) return
    const onMouseDown = (e: MouseEvent) => {
      const t = e.target as Node
      if (plusRef.current?.contains(t)) return
      if (menuRef.current?.contains(t)) return
      setDropdownOpen(false)
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [dropdownOpen])

  const openTab = (mode: PreviewMode) => {
    const existing = tabs.find((t) => t.type === mode)
    if (existing) {
      setActivePreviewTab(existing.id)
      setDropdownOpen(false)
      return
    }
    const newTab = {
      id: uid('tab'),
      type: mode,
      label: TAB_LABEL[mode],
      workdir: currentWorkdir,
    }
    addPreviewTab(newTab)
    setActivePreviewTab(newTab.id)
    setDropdownOpen(false)
  }

  const closeTab = (id: string) => {
    removePreviewTab(id)
  }

  const togglePlus = () => {
    if (dropdownOpen) {
      setDropdownOpen(false)
      return
    }
    if (plusRef.current) {
      const r = plusRef.current.getBoundingClientRect()
      setDropdownPos({
        top: r.bottom + 4, // 4px 间隙
        left: r.left, // 左对齐 + 按钮
      })
    }
    setDropdownOpen(true)
  }

  return (
    <aside className="flex h-full w-full flex-col overflow-hidden rounded-2xl border glass-panel shadow-sm">
      <TabBar
        tabs={tabs}
        activeId={activeTabId}
        onTabClick={(id) => setActiveTabId(id)}
        onTabClose={closeTab}
        plusRef={plusRef}
        dropdownOpen={dropdownOpen}
        onPlusClick={togglePlus}
      />

      <div className="min-h-0 flex-1">
        {activeTab ? (
          <ActiveTabContent tab={activeTab} />
        ) : (
          <EmptyState onPickFirst={togglePlus} />
        )}
      </div>

      {dropdownOpen &&
        dropdownPos &&
        createPortal(
          <PreviewMenu ref={menuRef} pos={dropdownPos} onSelect={openTab} />,
          document.body,
        )}
    </aside>
  )
}

// ── 子组件 ──────────────────────────────────────────────────────────────

function TabBar({
  tabs,
  activeId,
  onTabClick,
  onTabClose,
  plusRef,
  dropdownOpen,
  onPlusClick,
}: {
  tabs: PreviewTab[]
  activeId: string | null
  onTabClick: (id: string) => void
  onTabClose: (id: string) => void
  plusRef: React.RefObject<HTMLButtonElement | null>
  dropdownOpen: boolean
  onPlusClick: () => void
}) {
  return (
    <div
      role="tablist"
      className="flex items-center gap-1 overflow-x-auto border-b border-border/70 bg-muted/30 px-2 py-1.5"
    >
      {tabs.map((tab) => (
        <TabButton
          key={tab.id}
          tab={tab}
          active={tab.id === activeId}
          onClick={() => onTabClick(tab.id)}
          onClose={() => onTabClose(tab.id)}
        />
      ))}

      <button
        ref={plusRef}
        type="button"
        onClick={onPlusClick}
        aria-label="新建预览"
        aria-expanded={dropdownOpen}
        className={cn(
          'grid h-7 w-7 flex-shrink-0 place-items-center rounded-md border text-muted-foreground transition-colors',
          dropdownOpen
            ? 'border-border bg-card text-foreground'
            : 'border-transparent hover:border-border hover:bg-card/60 hover:text-foreground',
        )}
      >
        <Icon name="plus" className="h-3.5 w-3.5" strokeWidth={2} />
      </button>
    </div>
  )
}

const PreviewMenu = forwardRef<
  HTMLDivElement,
  { pos: { top: number; left: number }; onSelect: (mode: PreviewMode) => void }
>(function PreviewMenu({ pos, onSelect }, ref) {
  return (
    <div
      ref={ref}
      role="menu"
      style={{ position: 'fixed', top: pos.top, left: pos.left }}
      className="z-50 w-48 overflow-hidden rounded-lg border border-border bg-card py-1 shadow-lg"
    >
      {PREVIEW_MODES.map((m) => (
        <button
          key={m.mode}
          type="button"
          role="menuitem"
          onClick={() => m.enabled && onSelect(m.mode)}
          disabled={!m.enabled}
          className={cn(
            'flex w-full items-center gap-2.5 px-3 py-2 text-left text-[13px] transition-colors',
            m.enabled
              ? 'text-foreground hover:bg-muted'
              : 'cursor-not-allowed text-muted-foreground/60',
          )}
        >
          <Icon name={m.icon} className="h-4 w-4" strokeWidth={1.75} />
          <span className="flex-1">{m.title}</span>
          {!m.enabled && (
            <span className="text-[10px] text-muted-foreground/60">{m.hint}</span>
          )}
        </button>
      ))}
    </div>
  )
})

function TabButton({
  tab,
  active,
  onClick,
  onClose,
}: {
  tab: PreviewTab
  active: boolean
  onClick: () => void
  onClose: () => void
}) {
  return (
    // div + role=tab：避免 button-in-button 非法 HTML；点 × 时自然 stopPropagation
    <div
      role="tab"
      aria-selected={active}
      onClick={onClick}
      data-active={active ? 'true' : 'false'}
      className={cn(
        'group flex h-7 flex-shrink-0 cursor-pointer items-center gap-1.5 rounded-md border px-2 font-mono text-[12px]',
        active
          ? 'border-border bg-card text-foreground shadow-sm'
          : 'border-transparent text-muted-foreground hover:bg-card/60 hover:text-foreground',
      )}
      title={tab.workdir ?? tab.label}
    >
      <Icon name={TAB_ICON[tab.type]} className="h-3 w-3" strokeWidth={2} />
      <span>{tab.label}</span>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          onClose()
        }}
        aria-label="关闭标签"
        title="关闭标签"
        className="ml-0.5 grid h-4 w-4 flex-shrink-0 cursor-pointer place-items-center rounded text-muted-foreground/60 transition-colors hover:bg-destructive/15 hover:text-destructive"
      >
        <Icon name="x" className="h-2.5 w-2.5" strokeWidth={2.5} />
      </button>
    </div>
  )
}

function ActiveTabContent({ tab }: { tab: PreviewTab }) {
  if (tab.type === 'files') return <FilePreview workdir={tab.workdir} />
  return (
    <div className="flex h-full items-center justify-center p-8 text-center text-sm text-muted-foreground">
      <div>
        <Icon name="sparkle" className="mx-auto mb-3 h-6 w-6 opacity-50" />
        <p>「{tab.label}」预览即将到来</p>
        <p className="mt-1 text-[11.5px]">快照工作目录：{tab.workdir ?? '未设置'}</p>
      </div>
    </div>
  )
}

function EmptyState({ onPickFirst }: { onPickFirst: () => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center text-sm text-muted-foreground">
      <Icon name="panelRight" className="h-8 w-8 opacity-40" strokeWidth={1.5} />
      <p>
        点击右上角 <span className="font-mono">+</span> 选择预览模式
      </p>
      <button
        type="button"
        onClick={onPickFirst}
        className="mt-1 rounded-md border border-border/70 bg-card px-3 py-1.5 text-[12px] text-foreground hover:bg-muted"
      >
        新建预览
      </button>
    </div>
  )
}
