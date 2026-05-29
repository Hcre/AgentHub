import { cn } from '../../lib/cn'
import { convKey, useChatStore } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { Badge, Button, Icon } from '../ui'
import type { StageStatus } from '../../types'

function TaskCheck({ state, onClick }: { state: StageStatus; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'grid h-[18px] w-[18px] flex-shrink-0 place-items-center rounded-full border-[1.5px] transition-all hover:scale-110',
        state === 'done' && 'border-brand bg-brand text-brand-foreground',
        state === 'doing' && 'border-brand bg-background',
        state === 'todo' && 'border-border bg-background',
      )}
    >
      {state === 'done' && <Icon name="check" className="h-3 w-3" />}
      {state === 'doing' && <span className="h-1.5 w-1.5 rounded-full bg-brand" />}
    </button>
  )
}

export function RightPanel() {
  const { activeAgentId, activeConversationId } = useUIStore()
  const { stages, outputs, toggleStage } = useChatStore()
  const key =
    activeAgentId && activeConversationId ? convKey(activeAgentId, activeConversationId) : null
  const stage = key ? (stages[key] ?? []) : []
  const files = key ? (outputs[key] ?? []) : []

  const toggle = (id: string) => {
    if (activeAgentId && activeConversationId) toggleStage(activeAgentId, activeConversationId, id)
  }

  return (
    <aside className="flex h-full w-full flex-col gap-3">
      <section className="glass-panel flex max-h-[50%] min-h-0 flex-col rounded-2xl border shadow-sm">
        <header className="flex items-center justify-between border-b border-border/70 px-4 py-3">
          <div className="flex items-center gap-2">
            <Icon name="listCheck" className="h-3.5 w-3.5 text-muted-foreground" />
            <h3 className="text-[15px] font-medium tracking-tight">阶段</h3>
          </div>
          <Button variant="ghost" size="iconSm" className="text-muted-foreground">
            <Icon name="plus" className="h-3.5 w-3.5" />
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto px-2 py-2">
          {stage.length === 0 && (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">暂无任务</div>
          )}
          {stage.map((t) => (
            <div
              key={t.id}
              className="group flex items-start gap-2.5 rounded-md px-2 py-2 transition-colors hover:bg-accent/60"
            >
              <div className="pt-0.5">
                <TaskCheck state={t.state} onClick={() => toggle(t.id)} />
              </div>
              <div className="min-w-0 flex-1">
                <div
                  className={cn(
                    'text-[13px] font-medium leading-tight',
                    t.state === 'done' && 'text-muted-foreground line-through',
                  )}
                >
                  {t.label}
                </div>
                <div className="mt-1.5 flex items-center gap-2">
                  <Badge
                    variant={
                      t.state === 'doing' ? 'brand' : t.state === 'done' ? 'success' : 'outline'
                    }
                  >
                    {t.state === 'done' ? '完成' : t.state === 'doing' ? '进行中' : '待办'}
                  </Badge>
                  <span className="font-mono text-[10.5px] text-muted-foreground">
                    ~{t.eta} min
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
        <footer className="border-t border-border/70 p-2">
          <Button
            variant="secondary"
            size="sm"
            className="w-full bg-brand-soft text-brand-deep hover:bg-brand-soft/80"
          >
            <Icon name="sparkle" className="h-3 w-3" />
            建议下一步
          </Button>
        </footer>
      </section>

      <section className="glass-panel flex min-h-0 flex-1 flex-col rounded-2xl border shadow-sm">
        <header className="flex items-center justify-between border-b border-border/70 px-4 py-3">
          <div className="flex items-center gap-2">
            <Icon name="files" className="h-3.5 w-3.5 text-muted-foreground" />
            <h3 className="text-[15px] font-medium tracking-tight">任务产出</h3>
          </div>
          <Button variant="ghost" size="iconSm" className="text-muted-foreground">
            <Icon name="moreHorizontal" className="h-3.5 w-3.5" />
          </Button>
        </header>
        <div className="flex-1 overflow-y-auto p-2">
          {files.length === 0 && (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">尚无产出文件</div>
          )}
          {files.map((f) => (
            <div
              key={f.id}
              className="my-0.5 flex items-center gap-2.5 rounded-md border border-border/60 p-2.5 transition-all glass-soft hover:-translate-y-px"
            >
              <div className="grid h-8 w-8 place-items-center rounded-md border glass-strong text-muted-foreground">
                <Icon name={f.kind === 'diff' ? 'diff' : 'doc'} className="h-3.5 w-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="truncate font-mono text-[12.5px]">{f.name}</div>
                <div className="mt-0.5 font-mono text-[10.5px] text-muted-foreground">
                  {f.kind === 'diff' ? 'Diff' : 'Document'} · {f.size}
                </div>
              </div>
              <Badge variant={f.status === 'pending' ? 'brand' : 'outline'}>
                {f.status === 'input' ? '输入' : f.status === 'pending' ? '生成中' : '完成'}
              </Badge>
            </div>
          ))}
        </div>
      </section>
    </aside>
  )
}
