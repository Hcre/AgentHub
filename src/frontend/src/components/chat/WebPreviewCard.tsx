import { useEffect, useState } from 'react'
import { Maximize2, X } from 'lucide-react'
import { Dialog, DialogContent, Icon } from '../ui'
import { getHost } from './webPreviewUrl'

export interface WebPreviewCardProps {
  url: string
  title?: string
  /** 可选覆盖默认 favicon（默认从 `/api/favicon?url=...` 推导） */
  faviconUrl?: string
}

/**
 * 从 url 推导默认 favicon：Google s2 favicon 服务（公开 CDN，离线时回退到透明 1×1）。
 * 注意：favicon 加载失败不影响卡片本身渲染 —— 浏览器天然 fallback 到 alt 文本。
 */
function defaultFavicon(url: string): string {
  const host = getHost(url)
  return `https://www.google.com/s2/favicons?domain=${host}&sz=32`
}

/**
 * 网页预览卡片：在 Agent 消息流里内联展示一个可点击的链接，
 * 折叠态只显示标题 + URL + favicon + 「展开」按钮；
 * 用户点「展开」后才挂载 <iframe>，避免无谓加载第三方资源。
 * 用户点「全屏预览」则打开 Dialog 全屏 modal（90vh 高），
 * 适合右侧 panel 收折后跟随收折的场景。
 *
 * 设计参考：src/frontend/src/components/chat/MessageBubble.tsx:94-106 attachment 模式
 * （统一圆角 + 边框 + 小字号 + muted 配色）。
 */
export function WebPreviewCard({ url, title, faviconUrl }: WebPreviewCardProps) {
  const [expanded, setExpanded] = useState(false)
  const [faviconBroken, setFaviconBroken] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)
  const host = getHost(url)
  const display = title?.trim() || host
  const favicon = faviconBroken ? null : faviconUrl ?? defaultFavicon(url)

  // P1-3：ESC 键关全屏 Dialog（Dialog 自身没绑 ESC，这里手动监听）。
  // 仅在 fullscreen 为 true 时挂监听，避免无谓占用 keydown。
  useEffect(() => {
    if (!fullscreen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setFullscreen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [fullscreen])

  return (
    <>
      <div className="my-2 overflow-hidden rounded-lg border bg-card/50 text-[12.5px]">
        <div className="flex items-center gap-2.5 px-3 py-2">
          {favicon ? (
            <img
              src={favicon}
              alt=""
              width={16}
              height={16}
              loading="lazy"
              className="h-4 w-4 flex-shrink-0 rounded-sm"
              onError={() => setFaviconBroken(true)}
            />
          ) : (
            <span className="grid h-4 w-4 flex-shrink-0 place-items-center rounded-sm bg-muted text-[10px] text-muted-foreground">
              🔗
            </span>
          )}
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium text-foreground">{display}</div>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="block truncate font-mono text-[11px] text-muted-foreground hover:text-brand hover:underline"
            >
              {url}
            </a>
          </div>
          {/* P1-3 全屏预览：与「展开」并列，触发 Dialog 全屏 modal。
              视觉上更突出（icon + 蓝色提示），方便右侧 panel 收折后用户仍能访问。 */}
          <button
            type="button"
            data-testid="fullscreen-btn"
            onClick={() => setFullscreen(true)}
            aria-label="全屏预览"
            title="全屏预览（适合右侧面板收折后）"
            className="flex flex-shrink-0 items-center gap-1 rounded-md border bg-background px-2 py-1 text-[11px] font-medium text-blue-700 transition-colors hover:bg-accent hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-200"
          >
            <Maximize2 className="h-3 w-3" strokeWidth={1.75} />
            全屏
          </button>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="flex flex-shrink-0 items-center gap-1 rounded-md border bg-background px-2 py-1 text-[11px] font-medium text-foreground/80 transition-colors hover:bg-accent hover:text-foreground"
          >
            <Icon name={expanded ? 'chevronUp' : 'chevronDown'} className="h-3 w-3" />
            {expanded ? '收起' : '展开'}
          </button>
        </div>
        {expanded && (
          <div className="border-t bg-background">
            <iframe
              src={url}
              title={display}
              sandbox="allow-scripts allow-same-origin"
              referrerPolicy="no-referrer"
              loading="lazy"
              className="h-[480px] w-full"
            />
          </div>
        )}
      </div>

      {/* P1-3 全屏 Dialog：90vh 高，宽 90vw，留 5vw 边距。
          关闭：右上 X 按钮、backdrop 点击、ESC 键（useEffect 监听）。 */}
      <Dialog
        open={fullscreen}
        onOpenChange={(o) => setFullscreen(o)}
        data-testid="webpreview-fullscreen-dialog"
      >
        <DialogContent
          className="h-[90vh] w-[90vw] max-w-[calc(100vw-2rem)]"
          data-testid="webpreview-fullscreen-content"
        >
          <header className="flex items-center gap-2.5 border-b px-3 py-2">
            {favicon && !faviconBroken ? (
              <img
                src={favicon}
                alt=""
                width={16}
                height={16}
                className="h-4 w-4 flex-shrink-0 rounded-sm"
                onError={() => setFaviconBroken(true)}
              />
            ) : (
              <span className="grid h-4 w-4 flex-shrink-0 place-items-center rounded-sm bg-muted text-[10px] text-muted-foreground">
                🔗
              </span>
            )}
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-semibold text-foreground">
                {display}
              </div>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="block truncate font-mono text-[11px] text-muted-foreground hover:text-brand hover:underline"
              >
                {url}
              </a>
            </div>
            <button
              type="button"
              data-testid="fullscreen-close-btn"
              onClick={() => setFullscreen(false)}
              aria-label="关闭全屏预览"
              className="grid h-7 w-7 flex-shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          </header>
          <div className="min-h-0 flex-1">
            <iframe
              src={url}
              title={display}
              sandbox="allow-scripts allow-same-origin"
              referrerPolicy="no-referrer"
              className="h-full w-full"
            />
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
