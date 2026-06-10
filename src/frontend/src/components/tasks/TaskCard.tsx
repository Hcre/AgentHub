import type { DragEvent } from 'react'
import { Avatar, Badge } from '../ui'
import type { Agent, Task } from '../../types'

export function TaskCard({
  task,
  assignee,
  onClick,
  onDispatch,
}: {
  task: Task
  assignee?: Agent
  onClick: () => void
  onDispatch?: () => void
}) {
  const onDragStart = (e: DragEvent<HTMLDivElement>) => {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', task.id)
  }
  return (
    <div
      draggable
      onDragStart={onDragStart}
      onClick={onClick}
      title="点击循环状态 · 拖到其他列改状态"
      className="cursor-grab space-y-2 rounded-md border bg-background p-3 transition-all hover:-translate-y-px hover:shadow-sm active:cursor-grabbing"
    >
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
          {task.id}
        </span>
        {task.priority === 'high' && <Badge variant="brand">高</Badge>}
        {task.priority === 'critical' && <Badge variant="destructive">紧急</Badge>}
        {task.priority === 'low' && (
          <Badge variant="outline" className="text-muted-foreground">
            低
          </Badge>
        )}
      </div>
      <div className="text-[13px] font-medium leading-snug">{task.title}</div>
      <div className="flex items-center justify-between pt-1">
        <span className="font-mono text-[11px] text-muted-foreground">{task.due}</span>
        {assignee && <Avatar initial={assignee.name[0] ?? '?'} color={assignee.color} size={32} />}
      </div>
      {onDispatch && task.status === 'todo' && (
        <button
          type="button"
          data-testid="task-dispatch-btn"
          onClick={(e) => {
            e.stopPropagation()
            onDispatch()
          }}
          title="派发给编排引擎真跑（多 Agent 并行执行）"
          className="flex w-full items-center justify-center gap-1 rounded border border-brand/30 bg-brand/5 px-2 py-1 text-[11.5px] font-medium text-brand transition-colors hover:bg-brand/10"
        >
          ▶ 派发执行
        </button>
      )}
    </div>
  )
}
