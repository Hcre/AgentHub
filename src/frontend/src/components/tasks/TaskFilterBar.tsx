import { useEffect, useState } from 'react'
import { agents } from '../../data/mock'
import { useTaskStore, type TaskFilter } from '../../stores/taskStore'
import { Avatar, Button, Icon } from '../ui'
import { COLUMNS, PRIORITY_LABEL } from './columns'
import type { Priority } from '../../types'

type MenuId = 'status' | 'priority' | 'assignee'
const PRIORITIES: Priority[] = ['high', 'normal', 'low']

function Pill({
  id,
  label,
  active,
  isOpen,
  onToggle,
  onClear,
  onSelect,
}: {
  id: MenuId
  label: string
  active: boolean
  isOpen: boolean
  onToggle: () => void
  onClear: () => void
  onSelect: (patch: Partial<TaskFilter>) => void
}) {
  return (
    <div className="relative" onClick={(e) => e.stopPropagation()}>
      <Button variant={active ? 'secondary' : 'outline'} size="sm" onClick={onToggle}>
        {label}
        <Icon name="chevronDown" className="h-3 w-3" />
      </Button>
      {active && (
        <button
          onClick={onClear}
          className="absolute -right-1 -top-1 grid h-4 w-4 place-items-center rounded-full bg-muted text-muted-foreground hover:bg-accent"
          title="清除"
        >
          <Icon name="x" className="h-2.5 w-2.5" />
        </button>
      )}
      {isOpen && (
        <div className="absolute left-0 top-9 z-20 w-48 rounded-lg border bg-popover p-1 shadow-lg">
          {id === 'status' &&
            COLUMNS.map((c) => (
              <button
                key={c.id}
                onClick={() => onSelect({ status: c.id })}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[12.5px] hover:bg-accent"
              >
                <span className={`h-2 w-2 rounded-full ${c.dotClass}`} /> {c.label}
              </button>
            ))}
          {id === 'priority' &&
            PRIORITIES.map((p) => (
              <button
                key={p}
                onClick={() => onSelect({ priority: p })}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[12.5px] hover:bg-accent"
              >
                {PRIORITY_LABEL[p]}
              </button>
            ))}
          {id === 'assignee' &&
            agents.map((a) => (
              <button
                key={a.id}
                onClick={() => onSelect({ assignee: a.id })}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[12.5px] hover:bg-accent"
              >
                <Avatar initial={a.name[0] ?? '?'} color={a.color} size={32} /> {a.name}
              </button>
            ))}
        </div>
      )}
    </div>
  )
}

export function TaskFilterBar({ total }: { total: number }) {
  const { filter, setFilter } = useTaskStore()
  const [open, setOpen] = useState<MenuId | null>(null)

  useEffect(() => {
    if (!open) return
    const close = () => setOpen(null)
    window.addEventListener('click', close)
    return () => window.removeEventListener('click', close)
  }, [open])

  const select = (patch: Partial<TaskFilter>) => {
    setFilter(patch)
    setOpen(null)
  }
  const statusLabel = filter.status
    ? (COLUMNS.find((c) => c.id === filter.status)?.label ?? '状态')
    : '状态'
  const assigneeLabel = filter.assignee
    ? (agents.find((a) => a.id === filter.assignee)?.name ?? '负责人')
    : '负责人'

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex h-8 items-center gap-1.5 rounded-md border bg-background px-2.5 text-muted-foreground">
        <Icon name="search" className="h-3.5 w-3.5" />
        <input
          placeholder="搜索任务…"
          value={filter.q ?? ''}
          onChange={(e) => setFilter({ q: e.target.value })}
          className="w-40 bg-transparent text-[12.5px] outline-none placeholder:text-muted-foreground"
        />
      </div>
      <Pill
        id="status"
        label={statusLabel}
        active={!!filter.status}
        isOpen={open === 'status'}
        onToggle={() => setOpen(open === 'status' ? null : 'status')}
        onClear={() => setFilter({ status: undefined })}
        onSelect={select}
      />
      <Pill
        id="priority"
        label={filter.priority ? PRIORITY_LABEL[filter.priority] : '优先级'}
        active={!!filter.priority}
        isOpen={open === 'priority'}
        onToggle={() => setOpen(open === 'priority' ? null : 'priority')}
        onClear={() => setFilter({ priority: undefined })}
        onSelect={select}
      />
      <Pill
        id="assignee"
        label={assigneeLabel}
        active={!!filter.assignee}
        isOpen={open === 'assignee'}
        onToggle={() => setOpen(open === 'assignee' ? null : 'assignee')}
        onClear={() => setFilter({ assignee: undefined })}
        onSelect={select}
      />
      <span className="ml-1 font-mono text-[11px] text-muted-foreground">{total} 个结果</span>
    </div>
  )
}
