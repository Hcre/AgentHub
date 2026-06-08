import { useDeferredValue, useEffect, useRef, useState } from 'react'
import { cn } from '../../lib/cn'
import { fsApi, type FsItem, type FsSearchResultItem } from '../../api/fs'
import { Icon } from '../ui'

interface FileTreeProps {
  /** 根目录（workdir） */
  root: string
  /** 当前选中的文件路径 */
  selectedPath?: string
  /** 点击文件触发 */
  onSelect: (path: string) => void
}

/** 节点状态 */
interface NodeState {
  items: FsItem[]
  loading: boolean
  error: string | null
}

/** 文件树（懒加载：点开文件夹才拉下一层）+ 顶部搜索框（有查询时走 /api/fs/search 递归） */
export function FileTree({ root, selectedPath, onSelect }: FileTreeProps) {
  const [query, setQuery] = useState('')
  // useDeferredValue：React 18+ 推荐的「低优先级更新」机制；相当于内置防抖，
  // 避免每次按键都触发搜索请求（不依赖手写 setTimeout）
  const debouncedQuery = useDeferredValue(query.trim())

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* 搜索框 */}
      <div className="border-b border-border/60 px-2 py-1.5">
        <div className="relative">
          <Icon
            name="search"
            className="pointer-events-none absolute left-2 top-1/2 h-3 w-3 -translate-y-1/2 text-muted-foreground"
            strokeWidth={2}
          />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="筛选文件…"
            className="w-full rounded-md border border-border/60 bg-background py-1 pl-7 pr-2 font-mono text-[11.5px] text-foreground placeholder:text-muted-foreground/60 focus:border-border focus:outline-none"
          />
        </div>
      </div>

      {/* 主体：搜索中 → 搜索结果；否则 → 懒加载树 */}
      <div className="min-h-0 flex-1">
        {debouncedQuery ? (
          <SearchResults
            root={root}
            query={debouncedQuery}
            selectedPath={selectedPath}
            onSelect={onSelect}
          />
        ) : (
          <LazyTree root={root} selectedPath={selectedPath} onSelect={onSelect} />
        )}
      </div>
    </div>
  )
}

// ── 懒加载树（无搜索时） ─────────────────────────────────────────

function LazyTree({ root, selectedPath, onSelect }: FileTreeProps) {
  const [rootNode, setRootNode] = useState<NodeState>({ items: [], loading: true, error: null })
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [childCache, setChildCache] = useState<Map<string, NodeState>>(new Map())

  useEffect(() => {
    let alive = true
    fsApi
      .browse(root)
      .then((data) => {
        if (!alive) return
        const items = Array.isArray(data) ? data : data.items ?? []
        setRootNode({ items, loading: false, error: null })
      })
      .catch((e) => {
        if (!alive) return
        setRootNode({ items: [], loading: false, error: e?.message ?? '加载失败' })
      })
    return () => {
      alive = false
    }
  }, [root])

  const toggle = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
        if (!childCache.has(path)) {
          loadChildren(path)
        }
      }
      return next
    })
  }

  const loadChildren = (path: string) => {
    setChildCache((prev) => {
      const next = new Map(prev)
      next.set(path, { items: [], loading: true, error: null })
      return next
    })
    fsApi
      .browse(path)
      .then((data) => {
        const items = Array.isArray(data) ? data : data.items ?? []
        setChildCache((prev) => {
          const next = new Map(prev)
          next.set(path, { items, loading: false, error: null })
          return next
        })
      })
      .catch((e) => {
        setChildCache((prev) => {
          const next = new Map(prev)
          next.set(path, { items: [], loading: false, error: e?.message ?? '加载失败' })
          return next
        })
      })
  }

  return (
    <div className="h-full overflow-y-auto px-1 py-1 font-mono text-[12px]">
      {rootNode.loading && <div className="px-2 py-3 text-muted-foreground">加载中…</div>}
      {rootNode.error && (
        <div className="px-2 py-3 text-destructive">错误：{rootNode.error}</div>
      )}
      {!rootNode.loading && !rootNode.error && rootNode.items.length === 0 && (
        <div className="px-2 py-3 text-muted-foreground">此目录为空</div>
      )}
      <ul className="space-y-0.5">
        {rootNode.items.map((item) => (
          <TreeNode
            key={item.path}
            item={item}
            depth={0}
            expanded={expanded}
            childCache={childCache}
            selectedPath={selectedPath}
            onSelect={onSelect}
            onToggle={toggle}
          />
        ))}
      </ul>
    </div>
  )
}

function TreeNode({
  item,
  depth,
  expanded,
  childCache,
  selectedPath,
  onSelect,
  onToggle,
}: {
  item: FsItem
  depth: number
  expanded: Set<string>
  childCache: Map<string, NodeState>
  selectedPath?: string
  onSelect: (path: string) => void
  onToggle: (path: string) => void
}) {
  const isDir = item.type === 'dir'
  const isOpen = expanded.has(item.path)
  const childNode = childCache.get(item.path)
  const isSelected = !isDir && selectedPath === item.path

  return (
    <li>
      <button
        type="button"
        onClick={() => (isDir ? onToggle(item.path) : onSelect(item.path))}
        className={cn(
          'flex w-full items-center gap-1 rounded px-1.5 py-0.5 text-left hover:bg-accent/60',
          isSelected && 'bg-brand/15 text-foreground',
        )}
        style={{ paddingLeft: 6 + depth * 12 }}
      >
        {isDir ? (
          <Icon
            name={isOpen ? 'chevronDown' : 'chevronRight'}
            className={cn('h-3 w-3 flex-shrink-0 text-muted-foreground', !isOpen && '-rotate-90')}
          />
        ) : (
          <span className="h-3 w-3 flex-shrink-0" />
        )}
        {!isDir && <span className="flex-shrink-0 text-[11px]">📄</span>}
        <span className="truncate text-[12px]">{item.name}</span>
      </button>
      {isDir && isOpen && (
        <ul className="space-y-0.5">
          {childNode?.loading && (
            <li
              className="px-2 py-1 text-[11px] text-muted-foreground"
              style={{ paddingLeft: 18 + depth * 12 }}
            >
              加载中…
            </li>
          )}
          {childNode?.error && (
            <li
              className="px-2 py-1 text-[11px] text-destructive"
              style={{ paddingLeft: 18 + depth * 12 }}
            >
              错误
            </li>
          )}
          {childNode?.items.map((sub) => (
            <TreeNode
              key={sub.path}
              item={sub}
              depth={depth + 1}
              expanded={expanded}
              childCache={childCache}
              selectedPath={selectedPath}
              onSelect={onSelect}
              onToggle={onToggle}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

// ── 搜索结果视图 ──────────────────────────────────────────────────

function SearchResults({
  root,
  query,
  selectedPath,
  onSelect,
}: {
  root: string
  query: string
  selectedPath?: string
  onSelect: (path: string) => void
}) {
  // 用 reqIdRef 跟踪最新请求：旧请求回来时丢弃，避免竞态
  // 不用 effect 内 setState「重置 loading」的模式：loading 仅在首次展示，
  // 后续请求用「展示旧结果直到新结果回来」的方式（搜索 UI 常见体验）
  const [data, setData] = useState<{
    results: FsSearchResultItem[]
    truncated: boolean
    error: string | null
  }>({ results: [], truncated: false, error: null })
  const [hasLoaded, setHasLoaded] = useState(false)
  const reqIdRef = useRef(0)

  useEffect(() => {
    const myReqId = ++reqIdRef.current
    fsApi
      .search(root, query)
      .then((d) => {
        if (myReqId !== reqIdRef.current) return
        const results = Array.isArray(d?.items) ? d.items : Array.isArray(d?.results) ? d.results : []
        const error = d?.error || (!results.length && d?.detail ? String(d.detail) : null) || null
        setData({ results, truncated: d?.truncated ?? false, error })
        setHasLoaded(true)
      })
      .catch((e) => {
        if (myReqId !== reqIdRef.current) return
        setData({ results: [], truncated: false, error: e instanceof Error ? e.message : '搜索失败' })
        setHasLoaded(true)
      })
  }, [root, query])

  return (
    <div className="h-full overflow-y-auto px-1 py-1 font-mono text-[11.5px]">
      {!hasLoaded && <div className="px-2 py-3 text-muted-foreground">搜索中…</div>}
      {hasLoaded && data.error && (
        <div className="px-2 py-3 text-destructive">错误：{data.error}</div>
      )}
      {hasLoaded && !data.error && data.results.length === 0 && (
        <div className="px-2 py-3 text-muted-foreground">无匹配：{query}</div>
      )}
      {hasLoaded && !data.error && data.results.length > 0 && (
        <>
          <div className="px-2 py-1 text-[10.5px] text-muted-foreground/70">
            {data.results.length} 个结果{data.truncated ? '（已截断）' : ''}
          </div>
          <ul className="space-y-0.5">
            {data.results.map((r) => {
              const isSelected = r.type === 'file' && selectedPath === r.path
              const rel = r.path.startsWith(root) ? r.path.slice(root.length).replace(/^[\\/]/, '') : r.path
              return (
                <li key={r.path}>
                  <button
                    type="button"
                    onClick={() => r.type === 'file' && onSelect(r.path)}
                    disabled={r.type === 'dir'}
                    className={cn(
                      'flex w-full items-center gap-1 rounded px-1.5 py-0.5 text-left hover:bg-accent/60 disabled:cursor-not-allowed',
                      isSelected && 'bg-brand/15 text-foreground',
                    )}
                    title={r.path}
                  >
                    {r.type !== 'dir' && (
                      <span className="flex-shrink-0 text-[11px]">📄</span>
                    )}
                    <span className="flex-shrink-0 text-foreground">{r.name}</span>
                    <span className="flex-1 truncate text-muted-foreground/70">{rel}</span>
                  </button>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </div>
  )
}
