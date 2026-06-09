import { useMemo, useState } from 'react'
import ReactDiffViewer from 'react-diff-viewer-continued'
import { Button, Dialog, DialogContent, Icon } from '../ui'
import { parseMultiFileDiff } from './diffParse'

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

/** 单文件 diff 块（内联 + 全屏共用） */
function FileDiffBlock({
  file,
  styles,
  extraLines,
  maxH,
}: {
  file: { filename: string; oldValue: string; newValue: string; hasChanges: boolean }
  styles: typeof DIFF_VIEWER_STYLES
  extraLines: number
  maxH: string
}) {
  return (
    <div className="border-b last:border-b-0">
      {file.filename && (
        <div className="flex items-center gap-1.5 border-b bg-muted/20 px-3 py-1.5 font-mono text-[11px] text-muted-foreground">
          <Icon name="files" className="h-3 w-3 flex-shrink-0" />
          <span className="truncate">{file.filename}</span>
        </div>
      )}
      <div className="overflow-auto" style={{ maxHeight: maxH }}>
        <ReactDiffViewer
          oldValue={file.oldValue}
          newValue={file.newValue}
          splitView={false}
          useDarkTheme={false}
          styles={styles}
          showDiffOnly
          extraLinesSurroundingDiff={extraLines}
          disableWorker
        />
      </div>
    </div>
  )
}

/**
 * DiffView —— 在消息流里把 ```diff``` 围栏渲染成彩色 diff。
 *
 * 设计要点：
 * 1. **多文件拆分**：按 diff --git 头自动切分，每文件独立渲染（带文件名标题）。
 * 2. **单文件回退**：无 diff --git 头时（```diff 围栏）按单文件渲染，不显示文件名框。
 * 3. **统一视图**：splitView=false（上下对比），有行号，无 before/after 标签。
 * 4. **全屏模式**：Dialog 内展示所有文件，max-h 更高。
 */
export function DiffView({ unifiedDiff, language, oldTitle, newTitle }: DiffViewProps) {
  const [fullscreen, setFullscreen] = useState(false)

  const files = useMemo(() => parseMultiFileDiff(unifiedDiff), [unifiedDiff])

  if (files.length === 0) {
    return (
      <div
        role="note"
        className="my-2 rounded-lg border bg-muted/40 px-3 py-2 font-mono text-[12px] text-muted-foreground"
      >
        (empty diff{language ? ` · ${language}` : ''})
      </div>
    )
  }

  const hasAnyChanges = files.some((f) => f.hasChanges)
  const isMultiFile = files.length > 1 || (files.length === 1 && !!files[0].filename)
  const totalFiles = files.filter((f) => f.filename).length || files.length

  const inlineStyles = hasAnyChanges
    ? DIFF_VIEWER_STYLES
    : { ...DIFF_VIEWER_STYLES, contentText: { color: '#94a3b8' } }

  return (
    <div
      data-testid="diff-view"
      data-has-changes={hasAnyChanges ? 'true' : 'false'}
      data-language={language ?? ''}
      className="my-2 overflow-hidden rounded-lg border bg-background"
    >
      {/* 顶部标题栏 */}
      <div className="flex items-center justify-between gap-2 border-b bg-muted/40 px-3 py-1.5 font-mono text-[11.5px] text-muted-foreground">
        <div className="flex items-center gap-1.5 truncate">
          <Icon name="diff" className="h-3.5 w-3.5 flex-shrink-0" />
          <span className="truncate">
            {isMultiFile
              ? `${totalFiles} 个文件`
              : oldTitle && newTitle
                ? `${oldTitle} → ${newTitle}`
                : (oldTitle ?? newTitle ?? 'diff')}
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

      {/* 内联：每文件独立滚动盒子 */}
      <div className="font-mono text-[12.5px]">
        {files.map((file, i) => (
          <FileDiffBlock key={i} file={file} styles={inlineStyles} extraLines={2} maxH="320px" />
        ))}
      </div>

      {/* 全屏 Dialog */}
      <Dialog open={fullscreen} onOpenChange={setFullscreen}>
        <DialogContent className="w-[min(96vw,1100px)]">
          <div className="flex items-center justify-between gap-2 border-b bg-muted/40 px-4 py-2 font-mono text-[12px] text-muted-foreground">
            <div className="flex items-center gap-2 truncate">
              <Icon name="diff" className="h-4 w-4 flex-shrink-0" />
              <span className="truncate">
                {isMultiFile
                  ? `${totalFiles} 个文件`
                  : oldTitle && newTitle
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
            {files.map((file, i) => (
              <FileDiffBlock key={i} file={file} styles={DIFF_VIEWER_STYLES} extraLines={3} maxH="50vh" />
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
