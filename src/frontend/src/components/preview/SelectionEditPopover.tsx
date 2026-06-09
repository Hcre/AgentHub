/**
 * SelectionEditPopover — 框选代码后弹出的浮层
 *
 * M3-A 对话式局部修改（详见 M3-artifact-preview-v2.0/设计.md §二·功能点3）
 * - 用户在 CodeView 框选几行代码 → 触发浮层
 * - 输入修改需求 → 组装结构化 prompt
 * - 校验：当前预览目录 == 当前会话工作目录（不一致则拦截）
 * - 注入当前会话的 WS 通道，复用现有 Agent 执行链
 */
import { useState } from 'react'
import { Icon } from '../ui'

export interface SelectionInfo {
  /** 相对路径（不含 workdir 前缀） */
  relPath: string
  /** 起止行号（1-based，闭区间） */
  startLine: number
  endLine: number
  /** 选中的原始代码 */
  selectedText: string
  /** 当前预览面板挂载的工作目录 */
  workdir: string
}

interface Props {
  /** 当前选区；null = 隐藏浮层 */
  selection: SelectionInfo | null
  /** 当前活跃会话的工作目录（用于校验） */
  sessionWorkdir: string | undefined
  /** 当前会话的 WS 发送器 */
  onSubmit: (prompt: string) => Promise<void> | void
  onClose: () => void
}

export function SelectionEditPopover({ selection, sessionWorkdir, onSubmit, onClose }: Props) {
  const [instruction, setInstruction] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!selection) return null

  const dirMismatch =
    !!sessionWorkdir && selection.workdir && selection.workdir !== sessionWorkdir

  const handleSubmit = async () => {
    if (!instruction.trim() || submitting) return
    setSubmitting(true)
    const prompt = `请仅修改 ${selection.relPath} 第 ${selection.startLine}-${selection.endLine} 行：\n\`\`\`\n${selection.selectedText}\n\`\`\`\n需求：${instruction.trim()}`
    try {
      await onSubmit(prompt)
      setInstruction('')
      onClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      data-testid="selection-edit-popover"
      className="absolute right-4 top-12 z-50 w-80 rounded-lg border bg-popover p-3 shadow-lg"
    >
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-medium text-foreground">
          ✨ 修改选中 · 第 {selection.startLine}-{selection.endLine} 行
        </span>
        <button
          onClick={onClose}
          aria-label="关闭"
          className="rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <Icon name="x" className="h-3 w-3" />
        </button>
      </div>

      {dirMismatch ? (
        <div className="rounded border border-destructive/30 bg-destructive/10 p-2 text-[11px] text-destructive">
          ⚠️ 预览目录与会话工作目录不一致，无法就地修改。
        </div>
      ) : (
        <>
          <textarea
            data-testid="selection-edit-input"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="描述你想要的修改..."
            className="mb-2 h-16 w-full resize-none rounded border bg-background p-2 text-[12px] outline-none placeholder:text-muted-foreground/60 focus:border-brand"
            disabled={submitting}
          />
          <div className="flex justify-end gap-1.5">
            <button
              onClick={onClose}
              disabled={submitting}
              className="rounded px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent"
            >
              取消
            </button>
            <button
              onClick={handleSubmit}
              disabled={!instruction.trim() || submitting}
              data-testid="selection-edit-submit"
              className="rounded bg-brand px-2 py-1 text-[11px] font-medium text-brand-foreground disabled:opacity-40"
            >
              {submitting ? '发送中…' : '发送'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}