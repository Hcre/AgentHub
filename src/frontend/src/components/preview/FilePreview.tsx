import { useEffect, useMemo, useRef, useState } from 'react'
import hljs from 'highlight.js'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { cn } from '../../lib/cn'
import { fsApi, type PptxSlide } from '../../api/fs'
import { Button, Icon } from '../ui'
import { FileTree } from './FileTree'
import { SlideView } from './SlideView'
import { buildEditPrompt, computeLineRange, relativePath } from '../../lib/selectionEdit'
import { useUIStore } from '../../stores/uiStore'

/** 文件树固定宽度（与 AppShell 全局拖拽的右栏宽度解耦） */
const TREE_WIDTH = 200

// ── 文件类型检测 ─────────────────────────────────────────────────
const IMAGE_EXTS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'])
const MARKDOWN_EXTS = new Set(['.md', '.markdown'])
const PPTX_EXTS = new Set(['.pptx'])

function fileExt(name: string): string {
  const i = name.lastIndexOf('.')
  return i >= 0 ? name.slice(i).toLowerCase() : ''
}

interface FilePreviewProps {
  /** 工作目录（项目根），为空时不显示 */
  workdir?: string
  /** 初始打开的文件路径（从顶层 tab 传入） */
  initialPath?: string
  /** 文件树点击回调：通知父组件在顶层 tab 栏打开文件 */
  onOpenFile?: (path: string) => void
}

interface FileState {
  path: string
  name: string
  content: string
  size: number
  loading: boolean
  error: string | null
  /** .pptx 文件：后端抽取的每页文本（其余文件类型为 undefined） */
  slides?: PptxSlide[]
}

export function FilePreview({ workdir, initialPath, onOpenFile }: FilePreviewProps) {
  const [file, setFile] = useState<FileState | null>(null)
  const [flashKey, setFlashKey] = useState(0)
  const fileTreeCollapsed = useUIStore((s) => s.fileTreeCollapsed)
  const fileRef = useRef<FileState | null>(null)
  fileRef.current = file

  /** AI 工具操作文件后刷新当前打开的文件 */
  useEffect(() => {
    const onFileChanged = () => {
      const f = fileRef.current
      if (!f) return
      fsApi.readFile(f.path).then((data) => {
        if (f.content !== data.content) {
          setFlashKey((k) => k + 1)
          setFile((prev) => prev?.path === f.path
            ? { ...prev, content: data.content, size: data.size, error: null }
            : prev)
        }
      }).catch(() => {})
    }
    window.addEventListener('file-changed', onFileChanged)
    return () => window.removeEventListener('file-changed', onFileChanged)
  }, [])

  useEffect(() => {
    if (initialPath) void loadFile(initialPath)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialPath])

  /** 文件树点击 → 通知父组件打开顶层 tab */
  const handleTreeSelect = (path: string) => {
    if (onOpenFile) {
      onOpenFile(path)
    } else {
      void loadFile(path)
    }
  }

  const loadFile = async (path: string) => {
    if (file?.path === path) return
    const name = basename(path)
    const ext = fileExt(name)

    // 图片：跳过 API（后端 /read 返回 415），用 /raw 端点直接渲染
    if (IMAGE_EXTS.has(ext)) {
      setFile({ path, name, content: '', size: 0, loading: false, error: null })
      return
    }

    // PPT：走专用端点抽每页文本（后端 /read 对二进制返 415）
    if (PPTX_EXTS.has(ext)) {
      setFile({ path, name, content: '', size: 0, loading: true, error: null })
      try {
        const data = await fsApi.pptxSlides(path)
        setFile({ path, name, content: '', size: 0, loading: false, error: null, slides: data.slides })
      } catch (e) {
        setFile((prev) => prev?.path === path
          ? { ...prev, loading: false, error: e instanceof Error ? e.message : '解析 PPT 失败' }
          : prev)
      }
      return
    }

    setFile({ path, name, content: '', size: 0, loading: true, error: null })
    try {
      const data = await fsApi.readFile(path)
      setFile({ path, name, content: data.content, size: data.size, loading: false, error: null })
    } catch (e) {
      setFile((prev) => prev?.path === path
        ? { ...prev, loading: false, error: e instanceof Error ? e.message : '读取失败' }
        : prev)
    }
  }

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
      {/* 面包屑：当前文件路径 + 文件树折叠按钮 */}
      {file && !file.loading && <Breadcrumb path={file.path} workdir={workdir} right={<TreeToggleButton />} />}

      {/* 主体：内容（flex-1） + 文件树（固定 140px，折叠时 0） */}
      <div className="flex min-h-0 flex-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1 overflow-auto bg-background">
            {!file && (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                从右侧文件树选个文件打开
              </div>
            )}
            {file?.loading && (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                读取中…
              </div>
            )}
            {file?.error && file.error.includes('415') && (
              <BinaryPlaceholder name={file.name} ext={fileExt(file.name)} />
            )}
            {file?.error && !file.error.includes('415') && (
              <div className="flex h-full items-center justify-center text-sm text-destructive">
                {file.error}
              </div>
            )}
            {file && !file.loading && !file.error && (
              <FileContentView path={file.path} name={file.name} content={file.content} slides={file.slides} workdir={workdir} flashKey={flashKey} />
            )}
          </div>
        </div>

        {/* 文件树：固定宽度 140px；折叠时 width:0,内容不渲染（用 hidden 而非 width:0,避免留白 transition 抖动） */}
        {!fileTreeCollapsed && (
          <aside
            style={{ width: TREE_WIDTH }}
            className="flex flex-shrink-0 flex-col border-l border-border/70 bg-muted/10"
          >
            <FileTree root={workdir} selectedPath={file?.path} onSelect={handleTreeSelect} />
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
      className="flex flex-shrink-0 items-center gap-1 border-b border-border/60 bg-white px-3 py-1 font-mono text-[11.5px] text-muted-foreground dark:bg-black"
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

function CodeView({ content, path, workdir }: { content: string; path?: string; workdir?: string }) {
  const [flash, setFlash] = useState(true)
  const [wrap, setWrap] = useState(false)
  const preRef = useRef<HTMLPreElement | null>(null)
  const [sel, setSel] = useState<
    { text: string; startLine: number; endLine: number; x: number; y: number } | null
  >(null)
  const lines = content.split('\n')

  // 挂载时触发闪动，短暂延迟后移除
  useEffect(() => {
    const t = setTimeout(() => setFlash(false), 800)
    return () => clearTimeout(t)
  }, [])

  // 选区 → 浮层："✨ 修改选中"（对话式局部修改入口）
  const onMouseUp = () => {
    const selection = window.getSelection()
    const text = selection?.toString() ?? ''
    if (!text.trim() || !preRef.current || selection!.rangeCount === 0) {
      setSel(null)
      return
    }
    const range = selection!.getRangeAt(0)
    if (!preRef.current.contains(range.commonAncestorContainer)) {
      setSel(null)
      return
    }
    const lr = computeLineRange(content, text)
    if (!lr) {
      setSel(null)
      return
    }
    const rect = range.getBoundingClientRect()
    const host = preRef.current.getBoundingClientRect()
    setSel({
      text,
      startLine: lr.startLine,
      endLine: lr.endLine,
      x: rect.left - host.left + preRef.current.scrollLeft,
      y: rect.bottom - host.top + preRef.current.scrollTop,
    })
  }

  // highlight.js 高亮（memo 避免大文件重复计算）
  const highlighted = useMemo(() => {
    if (!content) return ''
    const lang = path ? getLanguage(path) : undefined
    try {
      if (lang) {
        const result = hljs.highlight(content, { language: lang })
        if (result.value) return result.value
      }
      // 回退：自动检测
      const auto = hljs.highlightAuto(content)
      return auto.value
    } catch {
      // 极端情况回退：HTML 转义
      return content.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    }
  }, [content, path])

  return (
    <div
      className={cn(
        'flex min-h-full flex-col font-mono text-[12.5px] leading-relaxed transition-colors duration-500',
        flash && 'bg-primary/5',
      )}
    >
      {/* 工具栏：自动换行切换 */}
      <div className="flex flex-shrink-0 items-center justify-end border-b border-border/40 bg-white px-2 py-0.5 dark:bg-black">
        <Button
          variant="ghost"
          size="iconSm"
          onClick={() => setWrap((w) => !w)}
          title={wrap ? '关闭自动换行' : '开启自动换行'}
          aria-label={wrap ? '关闭自动换行' : '开启自动换行'}
        >
          <Icon
            name="wrapText"
            className={cn('h-3.5 w-3.5 transition-colors', wrap && 'text-primary')}
            strokeWidth={2}
          />
        </Button>
      </div>

      {/* 代码主体 */}
      <div className="relative flex min-h-0 flex-1">
        {/* 行号 */}
        <div className="sticky left-0 select-none border-r border-border/40 bg-white px-3 py-3 text-right text-muted-foreground/60 dark:bg-black">
          {lines.map((_, i) => (
            <div key={i}>{i + 1}</div>
          ))}
        </div>
        {/* 高亮代码 */}
        <pre
          ref={preRef}
          onMouseUp={onMouseUp}
          className={cn(
            'relative min-w-0 flex-1 overflow-x-auto px-4 py-3 bg-white dark:bg-black',
            wrap ? 'whitespace-pre-wrap break-all' : 'whitespace-pre',
          )}
        >
          <code dangerouslySetInnerHTML={{ __html: highlighted }} />
          {sel && (
            <SelectionEditPopover
              x={sel.x}
              y={sel.y}
              startLine={sel.startLine}
              endLine={sel.endLine}
              onClose={() => setSel(null)}
              onSubmit={(request) => {
                const prompt = buildEditPrompt({
                  relPath: relativePath(path ?? '', workdir),
                  startLine: sel.startLine,
                  endLine: sel.endLine,
                  selectedText: sel.text,
                  request,
                })
                // 经现有会话 WS 通道发给当前 Agent（ChatView 监听并走 onSend 链路）
                window.dispatchEvent(new CustomEvent('agent-edit-request', { detail: { text: prompt } }))
                setSel(null)
              }}
            />
          )}
        </pre>
      </div>
    </div>
  )
}

/** 选区编辑浮层：输入修改需求 → 提交后组装 prompt 经会话发给 Agent。 */
function SelectionEditPopover({
  x, y, startLine, endLine, onSubmit, onClose,
}: {
  x: number
  y: number
  startLine: number
  endLine: number
  onSubmit: (request: string) => void
  onClose: () => void
}) {
  const [val, setVal] = useState('')
  const range = startLine === endLine ? `第 ${startLine} 行` : `第 ${startLine}–${endLine} 行`
  return (
    <div
      data-testid="selection-edit-popover"
      style={{ left: Math.max(4, x), top: y + 6 }}
      className="absolute z-20 w-72 rounded-lg border bg-popover p-2 shadow-lg"
      onMouseUp={(e) => e.stopPropagation()}
    >
      <div className="mb-1.5 flex items-center justify-between text-[11.5px] text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="text-brand">✨</span> 修改选中（{range}）
        </span>
        <button type="button" onClick={onClose} aria-label="关闭" className="hover:text-foreground">
          ✕
        </button>
      </div>
      <textarea
        autoFocus
        rows={2}
        value={val}
        onChange={(e) => setVal(e.target.value)}
        placeholder="描述要怎么改，例如：把循环换成 map…"
        className="w-full resize-none rounded border bg-background px-2 py-1 font-sans text-[12.5px] outline-none focus:border-brand/40"
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && val.trim()) onSubmit(val.trim())
          if (e.key === 'Escape') onClose()
        }}
      />
      <div className="mt-1.5 flex items-center justify-end gap-2">
        <span className="mr-auto text-[10.5px] text-muted-foreground/60">⌘/Ctrl+↵ 发送</span>
        <button
          type="button"
          data-testid="selection-edit-send"
          disabled={!val.trim()}
          onClick={() => val.trim() && onSubmit(val.trim())}
          className="rounded bg-brand px-2.5 py-1 text-[12px] font-medium text-brand-foreground disabled:opacity-50"
        >
          发送给 Agent
        </button>
      </div>
    </div>
  )
}

// ── 文件内容分发 ──────────────────────────────────────────────────

function FileContentView({ path, name, content, slides, workdir, flashKey }: {
  path: string
  name: string
  content: string
  slides?: PptxSlide[]
  workdir?: string
  flashKey: number
}) {
  const ext = fileExt(name)
  if (IMAGE_EXTS.has(ext)) return <ImageView path={path} name={name} />
  if (PPTX_EXTS.has(ext)) return <SlideView slides={slides ?? []} />
  if (MARKDOWN_EXTS.has(ext)) return <MarkdownView content={content} />
  return <CodeView content={content} path={path} workdir={workdir} key={flashKey} />
}

// ── 图片预览 ──────────────────────────────────────────────────────

function ImageView({ path, name }: { path: string; name: string }) {
  const [error, setError] = useState(false)
  const src = `/api/fs/raw?path=${encodeURIComponent(path)}`
  if (error) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-destructive">
        图片加载失败
      </div>
    )
  }
  return (
    <div className="flex h-full items-start justify-center overflow-auto p-4">
      <img
        src={src}
        alt={name}
        className="max-w-full object-contain"
        onError={() => setError(true)}
      />
    </div>
  )
}

// ── Markdown 预览 ─────────────────────────────────────────────────

function MarkdownView({ content }: { content: string }) {
  return (
    <div className="min-h-full overflow-auto bg-white px-6 py-4 dark:bg-black">
      <div className="prose prose-sm max-w-none text-[14px] leading-[1.6] text-foreground">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    </div>
  )
}

// ── 二进制文件占位 ────────────────────────────────────────────────

function BinaryPlaceholder({ name, ext }: { name: string; ext: string }) {
  const typeLabel = ext ? ext.slice(1).toUpperCase() : '未知'
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center text-sm text-muted-foreground">
        <div className="mb-1 font-medium text-foreground/80">{name}</div>
        <div>{typeLabel} 文件 · 无法预览</div>
      </div>
    </div>
  )
}

/** 根据文件扩展名推断 highlight.js 语言标识 */
function getLanguage(path: string): string | undefined {
  const ext = path.split('.').pop()?.toLowerCase()
  switch (ext) {
    case 'ts':
    case 'tsx':
      return 'typescript'
    case 'js':
    case 'jsx':
      return 'javascript'
    case 'py':
      return 'python'
    case 'json':
      return 'json'
    case 'css':
    case 'scss':
    case 'less':
      return 'css'
    case 'html':
    case 'htm':
    case 'xml':
    case 'svg':
      return 'xml'
    case 'yaml':
    case 'yml':
      return 'yaml'
    case 'sql':
      return 'sql'
    case 'md':
    case 'markdown':
      return 'markdown'
    case 'sh':
    case 'bash':
      return 'bash'
    case 'rs':
      return 'rust'
    case 'go':
      return 'go'
    case 'java':
      return 'java'
    case 'c':
    case 'h':
      return 'c'
    case 'cpp':
    case 'hpp':
    case 'cc':
    case 'cxx':
      return 'cpp'
    case 'toml':
      return 'ini'
    case 'dockerfile':
      return 'dockerfile'
    default:
      return undefined
  }
}

function basename(p: string): string {
  const parts = p.replace(/\\/g, '/').split('/').filter(Boolean)
  return parts[parts.length - 1] ?? p
}
