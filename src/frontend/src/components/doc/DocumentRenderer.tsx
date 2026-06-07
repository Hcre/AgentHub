import { useState } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import rehypeHighlight from 'rehype-highlight'
import { Icon } from '../ui'

/**
 * 文档渲染器（统一 Markdown / PDF / 富文本 入口） —— P1-2
 *
 * 设计目标：
 *   - 从 MessageBubble 抽离 MarkdownBody 复用，避免每条消息重渲染 + 风格不一致
 *   - 三种 kind 走同一个壳：顶角 header（文件名 + 类型标签） + 内容区
 *   - PDF 走 iframe（与 WebPreviewCard 同源，沙箱化但允许脚本）
 *   - 富文本降级为 Markdown 子集（粗体 + 链接），保证前端 demo 范围可控
 *
 * 数据契约：
 *   - markdown/richtext：用 `content` 字段
 *   - pdf：用 `url` 字段（指向 PDF 文件 URL）
 *   - fileName：可选，显示在 header
 */

export type DocumentKind = 'markdown' | 'pdf' | 'richtext'

export interface DocumentRendererProps {
  kind: DocumentKind
  /** markdown / richtext 的文本内容（markdown / richtext 必填） */
  content?: string
  /** PDF 文件 URL（pdf 必填） */
  url?: string
  /** 文件名（显示在 header；缺省按 kind 给个默认名） */
  fileName?: string
  /** Markdown 渲染自定义 className（透传给外层） */
  className?: string
}

/** 截 snippet 用：把超长 markdown text 折叠到 N 字符。 */
const MAX_PREVIEW_CHARS = 4000

/**
 * 共享的 markdown 渲染 components：与 MessageBubble 视觉同步
 * （pre/code 加边框 + 灰底，链接 brand 色）。
 */
const MD_COMPONENTS = {
  pre: ({ children }: { children?: React.ReactNode }) => (
    <pre className="my-2 overflow-x-auto whitespace-pre-wrap rounded-lg border bg-muted/50 p-3 text-[13px] font-mono text-foreground/80">
      {children}
    </pre>
  ),
  code: ({
    className,
    children,
    ...props
  }: {
    className?: string
    children?: React.ReactNode
  } & React.HTMLAttributes<HTMLElement>) => {
    const isInline = !className
    return isInline ? (
      <code
        className="rounded bg-muted/50 px-1 py-0.5 font-mono text-[12px] text-foreground"
        {...props}
      >
        {children}
      </code>
    ) : (
      <code className={className} {...props}>
        {children}
      </code>
    )
  },
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener"
      className="text-brand underline"
    >
      {children}
    </a>
  ),
  h1: ({ children }: { children?: React.ReactNode }) => (
    <h1 className="mb-2 mt-3 text-[18px] font-semibold">{children}</h1>
  ),
  h2: ({ children }: { children?: React.ReactNode }) => (
    <h2 className="mb-2 mt-3 text-[16px] font-semibold">{children}</h2>
  ),
  h3: ({ children }: { children?: React.ReactNode }) => (
    <h3 className="mb-1.5 mt-2 text-[14px] font-semibold">{children}</h3>
  ),
  ul: ({ children }: { children?: React.ReactNode }) => (
    <ul className="my-1.5 list-disc pl-5">{children}</ul>
  ),
  ol: ({ children }: { children?: React.ReactNode }) => (
    <ol className="my-1.5 list-decimal pl-5">{children}</ol>
  ),
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote className="my-2 border-l-2 border-brand/40 pl-3 italic text-muted-foreground">
      {children}
    </blockquote>
  ),
} satisfies Components

/** 富文本走 markdown 子集：仅 bold + 链接，其余当纯文本。 */
function RichTextBody({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={MD_COMPONENTS}
    >
      {content}
    </ReactMarkdown>
  )
}

/** Markdown 正文（截前 4000 字符避免超长阻塞渲染）。 */
function MarkdownContent({ content }: { content: string }) {
  const truncated =
    content.length > MAX_PREVIEW_CHARS
      ? content.slice(0, MAX_PREVIEW_CHARS) + '\n\n…(内容已截断)'
      : content
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={MD_COMPONENTS}
    >
      {truncated}
    </ReactMarkdown>
  )
}

/** PDF：iframe 直接挂载；带 sandbox + lazy load。 */
function PdfContent({ url, title }: { url: string; title: string }) {
  return (
    <iframe
      src={url}
      title={title}
      sandbox="allow-scripts allow-same-origin"
      referrerPolicy="no-referrer"
      loading="lazy"
      className="h-full min-h-[480px] w-full"
    />
  )
}

/**
 * 顶角 header：文件名 + 类型标签。
 * 标签色按 kind 区分：markdown=brand / pdf=blue / richtext=sage。
 */
function DocHeader({ fileName, kind }: { fileName: string; kind: DocumentKind }) {
  const tagClass =
    kind === 'markdown'
      ? 'bg-brand/10 text-brand'
      : kind === 'pdf'
        ? 'bg-blue-500/10 text-blue-700 dark:text-blue-300'
        : 'bg-emerald-500/10 text-emerald-700 dark:text-emerald-300'
  return (
    <header
      data-testid="doc-header"
      className="flex items-center gap-2 border-b bg-muted/30 px-3 py-1.5 text-[12px]"
    >
      <Icon
        name="doc"
        className="h-3.5 w-3.5 text-muted-foreground"
      />
      <span className="truncate font-medium text-foreground/80">{fileName}</span>
      <span
        data-testid="doc-kind-label"
        className={`ml-auto rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider ${tagClass}`}
      >
        {kind}
      </span>
    </header>
  )
}

/**
 * DocumentRenderer：统一的「文档预览」组件。
 * - markdown：用 react-markdown + remarkGfm + rehypeHighlight 渲染
 * - pdf：用 iframe 挂载 PDF URL
 * - richtext：复用 markdown 引擎，渲染粗体 + 链接
 *
 * 与 MessageBubble 的关系：
 *   - MessageBubble 中的 MarkdownBody 已经被本组件的 MarkdownContent 替代（行为一致）
 *   - 本组件额外支持 PDF / richtext，是文档「预览面板」通用入口
 */
export function DocumentRenderer({
  kind,
  content,
  url,
  fileName,
  className,
}: DocumentRendererProps) {
  // 错误态：pdf 必须有 url，markdown/richtext 必须有 content
  const [err] = useState<string | null>(() => {
    if (kind === 'pdf') {
      if (!url) return 'PDF 文档缺少 url 字段'
      return null
    }
    if (kind === 'markdown' || kind === 'richtext') {
      if (content === undefined || content === null) {
        return `${kind} 文档缺少 content 字段`
      }
      return null
    }
    return null
  })

  const displayName =
    fileName?.trim() ||
    (kind === 'pdf' ? 'document.pdf' : kind === 'richtext' ? 'note.rt' : 'document.md')

  if (err) {
    return (
      <div
        data-testid="doc-renderer"
        data-doc-error={err}
        className="rounded-lg border bg-card/40 p-3 text-[12.5px] text-muted-foreground"
      >
        <DocHeader fileName={displayName} kind={kind} />
        <div className="px-3 py-2 font-mono text-[11px] text-destructive">{err}</div>
      </div>
    )
  }

  return (
    <div
      data-testid="doc-renderer"
      data-doc-kind={kind}
      className={`flex h-full flex-col overflow-hidden rounded-lg border bg-card/40 text-[13.5px] ${className ?? ''}`}
    >
      <DocHeader fileName={displayName} kind={kind} />
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-2">
        {kind === 'markdown' && content !== undefined && (
          <MarkdownContent content={content} />
        )}
        {kind === 'richtext' && content !== undefined && (
          <RichTextBody content={content} />
        )}
        {kind === 'pdf' && url && <PdfContent url={url} title={displayName} />}
      </div>
    </div>
  )
}
