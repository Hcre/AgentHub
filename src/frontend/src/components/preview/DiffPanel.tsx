import { useCallback, useEffect, useState } from 'react'
import { Loader2, RefreshCw, GitCompareArrows, AlertTriangle } from 'lucide-react'
import { fsApi, type FsGitDiffOut } from '../../api/fs'
import { DiffView } from '../chat/DiffView'
import { cn } from '../../lib/cn'

/**
 * DiffPanel — 审查 diff tab 内容
 * - 接 workdir prop → 调 fsApi.gitDiff(workdir) 拉 unified diff
 * - 用 DiffView (react-diff-viewer-continued) 渲染 split 视图（emerald/rose 配色）
 * - staged toggle + 手动 refresh + 工作目录面包屑
 * - 失败/未设置/无 diff → 友好空态
 */

export function DiffPanel({ workdir }: { workdir?: string }) {
  const [staged, setStaged] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<FsGitDiffOut | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!workdir) {
      setResult(null)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const data = await fsApi.gitDiff(workdir, staged)
      setResult(data)
    } catch (e) {
      // 网络/解析错误：API 失败抛异常
      setError(e instanceof Error ? e.message : '加载 diff 失败')
      setResult(null)
    } finally {
      setLoading(false)
    }
  }, [workdir, staged])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load()
  }, [load])

  if (!workdir) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-sm text-muted-foreground">
        <div>
          <GitCompareArrows className="mx-auto mb-3 h-6 w-6 opacity-50" />
          <p>未设置工作目录</p>
          <p className="mt-1 text-[11.5px]">在聊天中选择带 workdir 的会话</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border/70 px-3 py-2">
        <div className="flex min-w-0 items-center gap-2 text-[12px] text-muted-foreground">
          <GitCompareArrows className="h-3.5 w-3.5 flex-shrink-0" />
          <span className="truncate font-mono text-[11px]" title={workdir}>
            {workdir}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <label className="flex cursor-pointer items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground">
            <input
              type="checkbox"
              checked={staged}
              onChange={(e) => setStaged(e.target.checked)}
              className="h-3 w-3 cursor-pointer rounded border-border"
              data-testid="diff-staged-toggle"
            />
            <span>staged</span>
          </label>
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading}
            aria-label="刷新 diff"
            title="刷新"
            className="grid h-6 w-6 place-items-center rounded text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3 w-3', loading && 'animate-spin')} />
          </button>
        </div>
      </div>
      {error && (
        <div className="mx-3 mt-2 rounded border border-rose-300 bg-rose-50/60 px-2 py-1 text-[11.5px] text-rose-700 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-300">
          {error}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && !result ? (
          <div className="flex h-full items-center justify-center text-[12px] text-muted-foreground">
            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
            加载 diff…
          </div>
        ) : result && !result.ok ? (
          <div className="flex h-full items-center justify-center p-8 text-center text-sm text-muted-foreground">
            <div>
              <AlertTriangle className="mx-auto mb-3 h-6 w-6 text-amber-500" />
              <p>无法显示 diff</p>
              <p className="mt-1 text-[11.5px] text-rose-600 dark:text-rose-400">{result.reason}</p>
              <p className="mt-2 text-[11px]">需 workdir 为 git 仓库且 git 可用</p>
            </div>
          </div>
        ) : result && result.diff === '' ? (
          <div className="flex h-full items-center justify-center text-center text-[12px] text-muted-foreground">
            <div>
              <GitCompareArrows className="mx-auto mb-2 h-5 w-5 opacity-40" />
              <p>{staged ? '暂存区无变更' : '工作区无未提交变更'}</p>
              <p className="mt-1 text-[11px]">
                {staged ? '切换到 unstaged 查看工作目录改动' : '所有改动已提交或工作目录干净'}
              </p>
            </div>
          </div>
        ) : result ? (
          <div className="flex h-full flex-col">
            {result.truncated && (
              <div className="border-b border-amber-300 bg-amber-50/60 px-3 py-1.5 text-[11.5px] text-amber-800 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                输出超过 2MB，已截断显示
              </div>
            )}
            <div className="min-h-0 flex-1 overflow-auto">
              <DiffView
                unifiedDiff={result.diff}
                oldTitle="before"
                newTitle="after"
                language="diff"
              />
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
