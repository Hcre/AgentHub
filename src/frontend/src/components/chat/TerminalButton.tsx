import { useState } from 'react'
import { Icon } from '../ui'

interface TerminalButtonProps {
  sessionId: string
}

/**
 * 在宿主机上打开一个原生终端窗口，实时 tail 当前 session 的 CLI 日志。
 *
 * 流程：
 * 1. GET  /api/sessions/{sessionId}/cli-log-path → 拿到日志文件路径
 * 2. POST /api/sessions/{sessionId}/open-terminal  → 后端在宿主机上 spawn 终端窗口
 *
 * 错误 / 后端不可用时复制对应的 paste 命令到剪贴板作为 fallback。
 */
export function TerminalButton({ sessionId }: TerminalButtonProps) {
  const [loading, setLoading] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  const openTerminal = async () => {
    if (!sessionId) return
    setLoading(true)
    setFeedback(null)

    try {
      // 1. 验证日志路径端点可用
      const pathResp = await fetch(`/api/sessions/${sessionId}/cli-log-path`)
      if (!pathResp.ok) throw new Error(`获取日志路径失败 (${pathResp.status})`)

      // 2. 尝试通过后端在宿主机上打开原生终端
      const openResp = await fetch(`/api/sessions/${sessionId}/open-terminal`, { method: 'POST' })
      if (openResp.ok) {
        setFeedback('终端已打开')
        return
      }

      // 后端 open-terminal 失败 → 回退到剪贴板
      await _copyCommandToClipboard(sessionId)
      setFeedback('命令已复制到剪贴板')
    } catch (err) {
      // 最后兜底：尝试复制命令
      try {
        await _copyCommandToClipboard(sessionId)
        setFeedback('命令已复制到剪贴板')
      } catch {
        setFeedback(err instanceof Error ? err.message : '无法打开终端')
      }
    } finally {
      setLoading(false)
      setTimeout(() => setFeedback(null), 3000)
    }
  }

  return (
    <div className="relative flex items-center">
      <button
        type="button"
        title="在终端中打开日志"
        aria-label="在终端中打开日志"
        onClick={openTerminal}
        disabled={loading}
        className="grid h-6 w-6 place-items-center rounded text-muted-foreground/60 transition-all hover:bg-accent hover:text-muted-foreground disabled:opacity-50"
      >
        <Icon name="terminal" className="h-3.5 w-3.5" />
      </button>
      {feedback && (
        <span
          role="status"
          className="ml-1 whitespace-nowrap font-mono text-[10px] text-muted-foreground/70 animate-in fade-in"
        >
          {feedback}
        </span>
      )}
    </div>
  )
}

/** 构造平台对应的终端命令并复制到剪贴板。 */
async function _copyCommandToClipboard(sessionId: string) {
  const pathResp = await fetch(`/api/sessions/${sessionId}/cli-log-path`)
  if (!pathResp.ok) throw new Error(`获取日志路径失败 (${pathResp.status})`)
  const { path: logPath } = (await pathResp.json()) as { path: string }

  const isWin = /windows/i.test(navigator.userAgent)
  const cmd = isWin
    ? `powershell -NoExit -Command "Get-Content '${logPath}' -Wait -Tail 50"`
    : `tail -f '${logPath}'`

  await navigator.clipboard.writeText(cmd)
}
