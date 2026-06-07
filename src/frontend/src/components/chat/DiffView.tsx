import { useMemo, useState } from 'react'
import ReactDiffViewer from 'react-diff-viewer-continued'
import { Button, Dialog, DialogContent, Icon } from '../ui'
import { parseUnifiedDiff } from './diffParse'

export interface DiffViewProps {
  /**
   * Unified diff 文本（git 风格，行首 `+` / `-` / 空格）。
   * 通常来自 Agent 回复里的 ```diff ... ``` 围栏。
   */
  unifiedDiff: string
  /**
   * 语言提示（用于 ARIA / 文件名占位）。不影响库内 diff 算法（库本身是文本 diff）。
   */
  language?: string
  /**
   * 左侧（旧）标题文本，例如文件名。显示在 split view 顶部。
   */
  oldTitle?: string
  /**
   * 右侧（新）标题文本，例如文件名。显示在 split view 顶部。
   */
  newTitle?: string
}

const DIFF_VIEWER_STYLES = {
  variables: {
    light: {
      addedBackground: 'rgba(16, 185, 129, 0.12)',
      removedBackground: 'rgba(239, 68, 68, 0.12)',
      wordAddedBackground: 'rgba(16, 185, 129, 0.28)',
      wordRemovedBackground: 'rgba(239, 68, 68, 0.28)',
      addedGutterBackground: 'rgba(16, 185, 129, 0.20)',
      removedGutterBackground: 'rgba(239, 68, 68, 0.20)',
      gutterBackground: '#f6f7f9',
      gutterBackgroundDark: '#eef0f3',
      highlightBackground: '#fffbe6',
      highlightGutterBackground: '#fff3a3',
      diffViewerBackground: '#ffffff',
      diffViewerColor: '#0f172a',
    },
  },
  diffContainer: {
    fontFamily:
      'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace',
    fontSize: '12.5px',
  },
  line: {
    fontFamily:
      'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace',
  },
} as const

/**
 * DiffView —— 在消息流里把 ```diff``` 围栏渲染成彩色 diff。
 *
 * 设计要点：
 * 1. **compact 模式（默认内联在 MessageBubble）**：splitView=true（左右双栏），限制 max-h，
 *    用户可点「全屏」按钮在 Dialog 里看完整版。
 * 2. **fullscreen 模式（在 Dialog 内）**：maxHeight=85vh（DialogContent 默认上限），
 *    「关闭」按钮在右上角。
 * 3. **风格对齐项目**：等宽字体（font-mono fallback 链）、圆角 (rounded-lg)、边框 (border)、
 *    用 Tailwind 调色板（emerald/rose 透明度叠加），不污染全局 CSS（库用 emotion inline style）。
 * 4. **空 diff 兜底**：hasChanges=false 时显示「无变更」提示，不强行调库渲染空表。
 */
export function DiffView({ unifiedDiff, language, oldTitle, newTitle }: DiffViewProps) {
  const [fullscreen, setFullscreen] = useState(false)

  const parsed = useMemo(() => parseUnifiedDiff(unifiedDiff), [unifiedDiff])

  if (!parsed.hasChanges && !parsed.oldValue && !parsed.newValue) {
    return (
      <div
        role="note"
        className="my-2 rounded-lg border bg-muted/40 px-3 py-2 font-mono text-[12px] text-muted-foreground"
      >
        (empty diff{language ? ` · ${language}` : ''})
      </div>
    )
  }

  // 内联渲染：max-h + overflow-auto；Dialog 渲染：max-h 更高（库会自适应）
  const inlineStyles = parsed.hasChanges
    ? DIFF_VIEWER_STYLES
    : { ...DIFF_VIEWER_STYLES, contentText: { color: '#94a3b8' } }

  return (
    <div
      data-testid="diff-view"
      data-has-changes={parsed.hasChanges ? 'true' : 'false'}
      data-language={language ?? ''}
      className="my-2 overflow-hidden rounded-lg border bg-background"
    >
      <div className="flex items-center justify-between gap-2 border-b bg-muted/40 px-3 py-1.5 font-mono text-[11.5px] text-muted-foreground">
        <div className="flex items-center gap-1.5 truncate">
          <Icon name="diff" className="h-3.5 w-3.5 flex-shrink-0" />
          <span className="truncate">
            {oldTitle && newTitle ? `${oldTitle} → ${newTitle}` : (oldTitle ?? newTitle ?? 'diff')}
            {language ? ` · ${language}` : ''}
          </span>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setFullscreen(true)}
          className="h-6 gap-1 px-2 text-[11px]"
          aria-label="全屏查看 diff"
        >
          <Icon name="panelRight" className="h-3 w-3" />
          全屏
        </Button>
      </div>
      <div className="max-h-[420px] overflow-auto font-mono text-[12.5px]">
        <ReactDiffViewer
          oldValue={parsed.oldValue}
          newValue={parsed.newValue}
          splitView
          useDarkTheme={false}
          leftTitle={oldTitle ?? 'before'}
          rightTitle={newTitle ?? 'after'}
          styles={inlineStyles}
          hideLineNumbers={false}
          showDiffOnly
          extraLinesSurroundingDiff={2}
          // 关闭 Web Worker —— 库默认会用 worker 计算 diff，但消息流里出现的 diff
          // 都很小（几十行），同步计算反而比 worker 通信更轻；也避免 jsdom 下 worker
          // 加载失败导致挂起。
          disableWorker
        />
      </div>
      <Dialog open={fullscreen} onOpenChange={setFullscreen}>
        <DialogContent className="w-[min(96vw,1100px)]">
          <div className="flex items-center justify-between gap-2 border-b bg-muted/40 px-4 py-2 font-mono text-[12px] text-muted-foreground">
            <div className="flex items-center gap-2 truncate">
              <Icon name="diff" className="h-4 w-4 flex-shrink-0" />
              <span className="truncate">
                {oldTitle && newTitle
                  ? `${oldTitle} → ${newTitle}`
                  : (oldTitle ?? newTitle ?? 'diff')}
                {language ? ` · ${language}` : ''}
              </span>
            </div>
            <Button
              type="button"
              variant="ghost"
              size="iconSm"
              onClick={() => setFullscreen(false)}
              aria-label="关闭全屏"
            >
              <Icon name="x" className="h-4 w-4" />
            </Button>
          </div>
          <div className="overflow-auto bg-background font-mono text-[12.5px]">
            <ReactDiffViewer
              oldValue={parsed.oldValue}
              newValue={parsed.newValue}
              splitView
              useDarkTheme={false}
              leftTitle={oldTitle ?? 'before'}
              rightTitle={newTitle ?? 'after'}
              styles={DIFF_VIEWER_STYLES}
              hideLineNumbers={false}
              showDiffOnly
              extraLinesSurroundingDiff={3}
              disableWorker
            />
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
