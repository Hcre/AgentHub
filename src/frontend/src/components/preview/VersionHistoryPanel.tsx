import { useCallback, useState } from 'react'
import { History, RotateCcw, AlertTriangle } from 'lucide-react'
import { fsApi, type FileCommit } from '../../api/fs'
import { DiffView } from '../chat/DiffView'
import { FileTree } from './FileTree'
import { cn } from '../../lib/cn'

/**
 * 版本历史：左侧文件树选文件 → 中间 git 提交时间线 → 选某 commit 取该版本内容，
 * 与当前工作树做 unified diff（DiffView 渲染）→「恢复此版本」写回当前文件。
 * 非 git 仓库 / 无历史走空态。
 */
export function VersionHistoryPanel({ workdir }: { workdir?: string }) {
  const [filePath, setFilePath] = useState<string | null>(null)
  const [commits, setCommits] = useState<FileCommit[] | null>(null)
  const [reason, setReason] = useState<string | null>(null)
  const [loadingHist, setLoadingHist] = useState(false)
  const [activeRev, setActiveRev] = useState<string | null>(null)
  const [diff, setDiff] = useState<string>('')
  const [revContent, setRevContent] = useState<string>('')
  const [restoreConfirm, setRestoreConfirm] = useState(false)
  const [restoring, setRestoring] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  const loadHistory = useCallback(async (path: string) => {
    setFilePath(path)
    setActiveRev(null)
    setDiff('')
    setNote(null)
    setCommits(null)
    setReason(null)
    setLoadingHist(true)
    try {
      const res = await fsApi.fileHistory(path)
      if (res.ok) setCommits(res.commits ?? [])
      else setReason(res.reason ?? '无法读取历史')
    } catch (e) {
      setReason(e instanceof Error ? e.message : '读取历史失败')
    } finally {
      setLoadingHist(false)
    }
  }, [])

  const selectRev = useCallback(async (rev: string) => {
    if (!filePath) return
    setActiveRev(rev)
    setNote(null)
    try {
      const res = await fsApi.fileAtRev(filePath, rev)
      if (res.ok) {
        setDiff(res.diff ?? '')
        setRevContent(res.content ?? '')
      } else {
        setDiff('')
        setNote(res.reason ?? '无法取该版本')
      }
    } catch (e) {
      setNote(e instanceof Error ? e.message : '取版本失败')
    }
  }, [filePath])

  const doRestore = useCallback(async () => {
    if (!filePath || !activeRev) return
    setRestoring(true)
    try {
      await fsApi.fileWrite(filePath, revContent)
      setNote('已恢复到该版本')
      setRestoreConfirm(false)
      // 通知 FilePreview 等监听者刷新
      window.dispatchEvent(new CustomEvent('file-changed'))
      // 回写后该版本与工作树一致，diff 清空
      setDiff('')
    } catch (e) {
      setNote(e instanceof Error ? e.message : '恢复失败')
    } finally {
      setRestoring(false)
    }
  }, [filePath, activeRev, revContent])

  if (!workdir) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        暂无工作目录
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0" data-testid="version-history">
      {/* 左：文件树 */}
      <aside className="flex w-48 flex-shrink-0 flex-col border-r border-border/60 bg-muted/10">
        <FileTree root={workdir} selectedPath={filePath ?? undefined} onSelect={loadHistory} />
      </aside>

      {/* 中：提交时间线 */}
      <div className="flex w-56 flex-shrink-0 flex-col overflow-auto border-r border-border/60">
        <div className="flex items-center gap-1.5 border-b border-border/60 px-3 py-2 text-[12px] font-medium text-muted-foreground">
          <History className="h-3.5 w-3.5" /> 提交历史
        </div>
        {!filePath && (
          <div className="p-3 text-[12px] text-muted-foreground/70">从左侧选一个文件查看其版本</div>
        )}
        {loadingHist && <div className="p-3 text-[12px] text-muted-foreground">读取中…</div>}
        {reason && (
          <div className="flex items-start gap-1.5 p-3 text-[12px] text-amber-700 dark:text-amber-400">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" /> {reason}
          </div>
        )}
        {commits && commits.length === 0 && (
          <div className="p-3 text-[12px] text-muted-foreground/70">该文件无提交历史</div>
        )}
        {commits?.map((c) => (
          <button
            key={c.sha}
            type="button"
            data-testid={`commit-${c.short}`}
            data-active={c.sha === activeRev ? 'true' : undefined}
            onClick={() => selectRev(c.sha)}
            className={cn(
              'flex flex-col gap-0.5 border-b border-border/40 px-3 py-2 text-left text-[12px] transition-colors hover:bg-accent',
              c.sha === activeRev && 'bg-brand/10',
            )}
          >
            <span className="truncate font-medium text-foreground">{c.subject}</span>
            <span className="font-mono text-[10.5px] text-muted-foreground/70">
              {c.short} · {c.author} · {c.date}
            </span>
          </button>
        ))}
      </div>

      {/* 右：diff + 恢复 */}
      <div className="flex min-w-0 flex-1 flex-col">
        {!activeRev ? (
          <div className="flex h-full items-center justify-center text-[12.5px] text-muted-foreground/70">
            选一个提交查看与当前的差异
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between gap-2 border-b border-border/60 px-3 py-1.5">
              <span className="truncate font-mono text-[11.5px] text-muted-foreground">
                {activeRev.slice(0, 8)} ↔ 当前
              </span>
              <div className="flex items-center gap-2">
                {note && <span className="text-[11.5px] text-brand">{note}</span>}
                {restoreConfirm ? (
                  <span className="flex items-center gap-1.5">
                    <button
                      type="button"
                      data-testid="restore-confirm"
                      disabled={restoring}
                      onClick={doRestore}
                      className="rounded border border-rose-300 bg-rose-50 px-2 py-1 text-[11.5px] font-medium text-rose-700 hover:bg-rose-100 disabled:opacity-50 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-300"
                    >
                      {restoring ? '恢复中…' : '确认恢复'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setRestoreConfirm(false)}
                      className="rounded border px-2 py-1 text-[11.5px] text-muted-foreground hover:bg-accent"
                    >
                      取消
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    data-testid="restore-btn"
                    onClick={() => setRestoreConfirm(true)}
                    className="flex items-center gap-1 rounded border border-brand/30 bg-brand/5 px-2 py-1 text-[11.5px] font-medium text-brand hover:bg-brand/10"
                  >
                    <RotateCcw className="h-3 w-3" /> 恢复此版本
                  </button>
                )}
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-auto">
              {diff ? (
                <DiffView unifiedDiff={diff} oldTitle={activeRev.slice(0, 8)} newTitle="当前" language="diff" />
              ) : (
                <div className="flex h-full items-center justify-center text-[12.5px] text-muted-foreground/70">
                  该版本与当前工作树无差异
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
