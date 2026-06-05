import { useState } from 'react'
import { cn } from '../../lib/cn'
import { Button, Dialog, DialogContent, Icon, Input, WorkspaceBrowser } from '../ui'

type ChatMode = 'casual' | 'project'

export interface StartChatModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  agentName: string
  /** 当前已存在的会话数（用于生成默认名 "对话 N"） */
  existingCount: number
  /** 用户点「发起」后回调：把名字 + 工作目录交给父组件，让它去 addConversation + openConversation */
  onConfirm: (name: string, workdir?: string) => void
}

/**
 * 「发起私聊」弹窗（首次与某队友私聊时弹出）：
 *   - 随便聊聊：无需工作目录，直接对话
 *   - 看看我的项目：必须选一个工作目录（项目根），会作为项目上下文
 *
 * 已有会话时不弹（直接打开最近一次）。
 *
 * 父组件应当用条件渲染 `{open && <StartChatModal .../>}` 包裹，
 * 这样每次打开都是全新挂载、useState 初始化读到的 existingCount 总是最新的。
 */
export function StartChatModal({
  open,
  onOpenChange,
  agentName,
  existingCount,
  onConfirm,
}: StartChatModalProps) {
  const [mode, setMode] = useState<ChatMode>('casual')
  // 初始化用函数形式，确保 mount 时读到的 existingCount 是当前值
  const [name, setName] = useState<string>(() => `对话 ${existingCount + 1}`)
  const [workdir, setWorkdir] = useState('')
  const [wsBrowserOpen, setWsBrowserOpen] = useState(false)

  const canConfirm = mode === 'casual' || workdir.trim().length > 0

  const handleConfirm = () => {
    if (!canConfirm) return
    const finalName = name.trim() || `对话 ${existingCount + 1}`
    onConfirm(finalName, mode === 'project' ? workdir.trim() : undefined)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[480px]">
        <header className="flex items-start gap-3 border-b border-border/70 p-4">
          <div className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
            <Icon name="chat" className="h-4 w-4" strokeWidth={2} />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="text-[15px] font-semibold leading-tight">发起私聊</h2>
            <p className="mt-1 text-[12.5px] text-muted-foreground">
              与「{agentName}」开始一段对话
            </p>
          </div>
        </header>

        {/* 模式选择 */}
        <div className="grid grid-cols-2 gap-2 p-4 pb-0">
          <ModeButton
            icon="chat"
            title="随便聊聊"
            desc="无项目上下文"
            active={mode === 'casual'}
            onClick={() => setMode('casual')}
          />
          <ModeButton
            icon="files"
            title="看看我的项目"
            desc="加载项目上下文"
            active={mode === 'project'}
            onClick={() => setMode('project')}
          />
        </div>

        {/* 表单 */}
        <div className="space-y-3 p-4">
          {/* 会话名 */}
          <label className="flex flex-col gap-1.5">
            <span className="text-[12px] font-medium text-muted-foreground">会话名</span>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={`对话 ${existingCount + 1}`}
              autoFocus
            />
          </label>

          {/* 工作目录（仅 project 模式） */}
          {mode === 'project' && (
            <label className="flex flex-col gap-1.5">
              <span className="text-[12px] font-medium text-muted-foreground">
                工作目录 <span className="text-destructive">*</span>
              </span>
              <div className="flex gap-1">
                <Input
                  value={workdir}
                  onChange={(e) => setWorkdir(e.target.value)}
                  placeholder="选择项目根目录…"
                />
                <Button variant="outline" size="sm" onClick={() => setWsBrowserOpen(true)}>
                  浏览
                </Button>
              </div>
              <p className="font-mono text-[11px] text-muted-foreground/70">
                将作为该项目后续对话的上下文根
              </p>
            </label>
          )}
        </div>

        <footer className="flex justify-end gap-2 border-t border-border/70 p-3">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            variant="brand"
            size="sm"
            onClick={handleConfirm}
            disabled={!canConfirm}
          >
            发起
          </Button>
        </footer>

        <WorkspaceBrowser
          key={wsBrowserOpen ? 'open' : 'closed'}
          open={wsBrowserOpen}
          onClose={() => setWsBrowserOpen(false)}
          onSelect={(path) => {
            setWorkdir(path)
            setWsBrowserOpen(false)
          }}
        />
      </DialogContent>
    </Dialog>
  )
}

function ModeButton({
  icon,
  title,
  desc,
  active,
  onClick,
}: {
  icon: 'chat' | 'files'
  title: string
  desc: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-active={active ? 'true' : undefined}
      className={cn(
        'flex flex-col items-start gap-1.5 rounded-lg border p-3 text-left transition-colors',
        'hover:border-brand/40',
        active
          ? 'border-brand bg-brand/10 text-foreground'
          : 'border-border bg-card text-foreground/80',
      )}
    >
      <span
        className={cn(
          'grid h-7 w-7 place-items-center rounded-md',
          active ? 'bg-brand text-brand-foreground' : 'bg-muted text-muted-foreground',
        )}
      >
        <Icon name={icon} className="h-3.5 w-3.5" strokeWidth={2} />
      </span>
      <span className="text-[13px] font-medium leading-tight">{title}</span>
      <span className="font-mono text-[10.5px] text-muted-foreground">{desc}</span>
    </button>
  )
}
