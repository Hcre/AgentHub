import { useEffect, useMemo, useState } from 'react'
import { cn } from '../../lib/cn'
import { fsApi } from '../../api/fs'
import { Button, Icon } from '../ui'
import { FileTree } from './FileTree'
import { useUIStore } from '../../stores/uiStore'

/** 文件树固定宽度（与 AppShell 全局拖拽的右栏宽度解耦） */
const TREE_WIDTH = 140

interface FilePreviewProps {
  /** 工作目录（项目根），为空时不显示 */
  workdir?: string
  /** 初始打开的文件路径（可选） */
  initialPath?: string
}

interface OpenTab {
  path: string
  name: string
  content: string
  size: number
  loading: boolean
  error: string | null
}

export function FilePreview({ workdir, initialPath }: FilePreviewProps) {
  const [tabs, setTabs] = useState<OpenTab[]>([])
  const [activePath, setActivePath] = useState<string | null>(null)
  const fileTreeCollapsed = useUIStore((s) => s.fileTreeCollapsed)

  useEffect(() => {
    if (initialPath) void openFile(initialPath)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPath])

  const openFile = async (path: string) => {
    if (tabs.find((t) => t.path === path)) {
      setActivePath(path)
      return
    }
    const placeholder: OpenTab = {
      path,
      name: basename(path),
      content: '',
      size: 0,
      loading: true,
      error: null,
    }
    setTabs((prev) => [...prev, placeholder])
    setActivePath(path)
    try {
      const data = await fsApi.readFile(path)
      setTabs((prev) =>
        prev.map((t) =>
          t.path === path ? { ...t, content: data.content, size: data.size, loading: false } : t,
        ),
      )
    } catch (e) {
      setTabs((prev) =>
        prev.map((t) =>
          t.path === path
            ? { ...t, loading: false, error: e instanceof Error ? e.message : '读取失败' }
            : t,
        ),
      )
    }
  }

  const closeTab = (path: string, e: React.MouseEvent) => {
    e.stopPropagation()
    setTabs((prev) => prev.filter((t) => t.path !== path))
    if (activePath === path) {
      setActivePath((prev) => {
        if (prev !== path) return prev
        const remaining = tabs.filter((t) => t.path !== path)
        return remaining.length > 0 ? (remaining[remaining.length - 1]?.path ?? null) : null
      })
    }
  }

  const active = useMemo(() => tabs.find((t) => t.path === activePath) ?? null, [tabs, activePath])

  if (!workdir) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center text-sm text-muted-foreground">
        <Icon name="panelRight" className="h-7 w-7 opacity-40" strokeWidth={1.5} />
        <p>暂无工作目录</p>
        <p className="text-[11.5px] text-muted-foreground/70">
          请在私聊或群组里指定工作目录
        </p>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* 顶部：文件 tab */}
      <div className="flex flex-shrink-0 items-center gap-1 border-b border-border/70 bg-muted/30 px-2 py-1.5">
        {tabs.length === 0 && (
          <span className="px-2 font-mono text-[11.5px] text-muted-foreground">
            从右侧文件树选个文件打开
          </span>
        )}
        {tabs.map((t) => {
          const isActive = t.path === activePath
          return (
            <button
              key={t.path}
              type="button"
              onClick={() => setActivePath(t.path)}
              className={cn(
                'group flex max-w-[180px] items-center gap-1.5 rounded-md border px-2.5 py-1 font-mono text-[12px]',
                isActive
                  ? 'border-border bg-card text-foreground shadow-sm'
                  : 'border-transparent text-muted-foreground hover:bg-card/60 hover:text-foreground',
              )}
              title={t.path}
            >
              <span className="truncate">{t.name}</span>
              <span
                role="button"
                tabIndex={-1}
                onClick={(e) => closeTab(t.path, e)}
                className="grid h-4 w-4 flex-shrink-0 cursor-pointer place-items-center rounded text-muted-foreground hover:bg-accent hover:text-foreground"
              >
                <Icon name="x" className="h-2.5 w-2.5" />
              </span>
            </button>
          )
        })}
      </div>

      {/* 面包屑：当前打开文件的相对路径 + 文件树折叠按钮 */}
      {active && <Breadcrumb path={active.path} workdir={workdir} right={<TreeToggleButton />} />}

      {/* 主体：内容（flex-1） + 文件树（固定 140px，折叠时 0） */}
      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-auto bg-background">
            {!active && (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                选个文件开始
              </div>
            )}
            {active?.loading && (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                读取中…
              </div>
            )}
            {active?.error && (
              <div className="flex h-full items-center justify-center text-sm text-destructive">
                {active.error}
              </div>
            )}
            {active && !active.loading && !active.error && (
              <CodeView content={active.content} />
            )}
          </div>
        </div>

        {/* 文件树：固定宽度 140px；折叠时 width:0,内容不渲染（用 hidden 而非 width:0,避免留白 transition 抖动） */}
        {!fileTreeCollapsed && (
          <aside
            style={{ width: TREE_WIDTH }}
            className="flex flex-shrink-0 flex-col border-l border-border/70 bg-muted/10"
          >
            <FileTree root={workdir} selectedPath={activePath ?? undefined} onSelect={openFile} />
          </aside>
        )}
      </div>
    </div>
  )
}

// ── 文件树折叠按钮(放在 Breadcrumb 行右侧) ─────────────────────────

function TreeToggleButton() {
  const collapsed = useUIStore((s) => s.fileTreeCollapsed)
  const toggle = useUIStore((s) => s.toggleFileTree)
  return (
    <Button
      variant="ghost"
      size="iconSm"
      onClick={toggle}
      title={collapsed ? '展开文件树' : '收起文件树'}
      aria-label={collapsed ? '展开文件树' : '收起文件树'}
    >
      <Icon
        name={collapsed ? 'chevronLeft' : 'chevronRight'}
        className="h-3.5 w-3.5"
        strokeWidth={2}
      />
    </Button>
  )
}

// ── 面包屑 ────────────────────────────────────────────────────────

function Breadcrumb({
  path,
  workdir,
  right,
}: {
  path: string
  workdir: string
  right?: React.ReactNode
}) {
  const norm = (s: string) => s.replace(/\\/g, '/').replace(/\/+$/, '')
  const root = norm(workdir)
  const full = norm(path)
  const rel = full.startsWith(root) ? full.slice(root.length).replace(/^\/+/, '') : full
  const segs = rel.split('/').filter(Boolean)
  return (
    <div
      className="flex flex-shrink-0 items-center gap-1 border-b border-border/60 bg-muted/10 px-3 py-1 font-mono text-[11.5px] text-muted-foreground"
      title={path}
    >
      <span className="min-w-0 flex-1 truncate">
        <span className="text-foreground/80">{root.split(/[/\\]/).pop() || root}</span>
        {segs.map((s, i) => (
          <span key={i}>
            <span className="px-1 text-muted-foreground/60">/</span>
            <span className={cn(i === segs.length - 1 && 'text-foreground/90')}>{s}</span>
          </span>
        ))}
      </span>
      {right}
    </div>
  )
}

// ── 代码视图 ──────────────────────────────────────────────────────

function CodeView({ content }: { content: string }) {
  const lines = content.split('\n')
  return (
    <div className="flex min-h-full font-mono text-[12.5px] leading-relaxed">
      <div className="sticky left-0 select-none border-r border-border/40 bg-muted/20 px-3 py-3 text-right text-muted-foreground/60">
        {lines.map((_, i) => (
          <div key={i}>{i + 1}</div>
        ))}
      </div>
      <pre className="flex-1 overflow-x-auto px-4 py-3 text-foreground/90">
        <code>{content}</code>
      </pre>
    </div>
  )
}

function basename(p: string): string {
  const parts = p.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] ?? p
}
