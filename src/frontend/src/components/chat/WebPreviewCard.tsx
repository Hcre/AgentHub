import { useState } from 'react'
import { Maximize2 } from 'lucide-react'
import { Icon } from '../ui'
import { useUIStore } from '../../stores/uiStore'
import { uid } from '../../lib/id'
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
  const host = getHost(url)
  const display = title?.trim() || host
  const favicon = faviconBroken ? null : faviconUrl ?? defaultFavicon(url)
  const addPreviewTab = useUIStore((s) => s.addPreviewTab)
  const setActivePreviewTab = useUIStore((s) => s.setActivePreviewTab)
  const setRightPanelCollapsed = useUIStore((s) => s.setRightPanelCollapsed)

  const handleFullscreen = () => {
    const tabId = uid('web')
    addPreviewTab({ id: tabId, type: 'webpage', label: display, url })
    setActivePreviewTab(tabId)
    setRightPanelCollapsed(false)
  }

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
          {/* 侧栏查看：在右侧边栏打开网页 */}
          <button
            type="button"
            data-testid="fullscreen-btn"
            onClick={handleFullscreen}
            aria-label="侧栏查看"
            title="在右侧边栏预览网页"
            className="flex flex-shrink-0 items-center gap-1 rounded-md border bg-background px-2 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-brand"
          >
            <Icon name="panelRight" className="h-3 w-3" />
            侧栏
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

    </>
  )
}
