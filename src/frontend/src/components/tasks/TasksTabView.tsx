import { useEffect, useMemo, useState, type DragEvent } from 'react'
import { cn } from '../../lib/cn'
import { agents } from '../../data/mock'
import { useTaskStore } from '../../stores/taskStore'
import { Avatar, Badge, Button, Icon, Tabs, TabsList, TabsTrigger } from '../ui'
import { COLUMNS, PRIORITY_LABEL } from './columns'
import { CreateTaskModal } from './CreateTaskModal'
import { TaskCard } from './TaskCard'
import { TaskFilterBar } from './TaskFilterBar'
import type { Task, TaskStatus } from '../../types'

const STATUS_ORDER: TaskStatus[] = ['todo', 'doing', 'blocked', 'done']
const agentsById = Object.fromEntries(agents.map((a) => [a.id, a]))

export function TasksTabView() {
  const { tasks, view, showClosed, filter, setView, setShowClosed, moveTask, addTask, load } =
    useTaskStore()
  const [createOpen, setCreateOpen] = useState(false)
  const [dragOver, setDragOver] = useState<TaskStatus | null>(null)

  useEffect(() => {
    void load()
  }, [load])

  const filtered = useMemo(
    () =>
      tasks.filter((t) => {
        if (!showClosed && t.status === 'done') return false
        if (filter.status && t.status !== filter.status) return false
        if (filter.priority && t.priority !== filter.priority) return false
        if (filter.assignee && t.assignee !== filter.assignee) return false
        if (filter.q) {
          const q = filter.q.toLowerCase()
          const name = t.assignee ? (agentsById[t.assignee]?.name ?? '') : ''
          if (!`${t.title} ${t.id} ${name}`.toLowerCase().includes(q)) return false
        }
        return true
      }),
    [tasks, showClosed, filter],
  )

  const cycle = (t: Task) => {
    const next = STATUS_ORDER[(STATUS_ORDER.indexOf(t.status) + 1) % STATUS_ORDER.length]!
    moveTask(t.id, next)
  }
  const onDrop = (status: TaskStatus) => (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(null)
    const id = e.dataTransfer.getData('text/plain')
    if (id) moveTask(id, status)
  }

  return (
    <div className="flex h-full flex-col gap-4 px-6 py-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Tabs value={view} onValueChange={(v) => setView(v as 'kanban' | 'list')}>
            <TabsList className="h-8">
              <TabsTrigger value="list" className="h-6 px-2">
                <Icon name="list" className="h-3 w-3" />
              </TabsTrigger>
              <TabsTrigger value="kanban" className="h-6 px-2">
                <Icon name="grid" className="h-3 w-3" />
              </TabsTrigger>
            </TabsList>
          </Tabs>
          <Button
            variant={showClosed ? 'secondary' : 'outline'}
            size="sm"
            onClick={() => setShowClosed(!showClosed)}
          >
            {showClosed ? '显示已关闭' : '隐藏已关闭'}
          </Button>
        </div>
        <div className="flex items-center gap-3">
          <span className="font-mono text-[11.5px] text-muted-foreground">
            {tasks.length} 个任务
          </span>
          <Button variant="brand" size="sm" onClick={() => setCreateOpen(true)}>
            <Icon name="plus" className="h-3.5 w-3.5" />
            创建任务
          </Button>
        </div>
      </div>

      <TaskFilterBar total={filtered.length} />

      {view === 'kanban' ? (
        <div className="grid min-h-0 flex-1 grid-cols-4 gap-3">
          {COLUMNS.map((c) => {
            const colTasks = filtered.filter((t) => t.status === c.id)
            return (
              <div
                key={c.id}
                onDragOver={(e) => {
                  e.preventDefault()
                  setDragOver(c.id)
                }}
                onDragLeave={() => setDragOver((d) => (d === c.id ? null : d))}
                onDrop={onDrop(c.id)}
                className={cn(
                  'flex flex-col rounded-xl border bg-muted/30 transition-all',
                  dragOver === c.id && 'bg-brand/5 ring-2 ring-brand',
                )}
              >
                <header className="flex items-center justify-between border-b px-3 py-2.5">
                  <div className="flex items-center gap-2">
                    <span className={cn('h-2 w-2 rounded-full', c.dotClass)} />
                    <span className="text-[13px] font-medium tracking-tight">{c.label}</span>
                  </div>
                  <span className="font-mono text-[10.5px] tabular-nums text-muted-foreground">
                    {colTasks.length}
                  </span>
                </header>
                <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-2">
                  {colTasks.length === 0 ? (
                    <div className="px-3 py-8 text-center font-mono text-[11px] text-muted-foreground/70">
                      空
                    </div>
                  ) : (
                    colTasks.map((t) => (
                      <TaskCard
                        key={t.id}
                        task={t}
                        assignee={t.assignee ? agentsById[t.assignee] : undefined}
                        onClick={() => cycle(t)}
                      />
                    ))
                  )}
                </div>
                <button
                  onClick={() => addTask(c.id)}
                  className="m-2 flex items-center gap-1.5 rounded-md border border-dashed px-2.5 py-1.5 text-[12px] text-muted-foreground transition-colors hover:border-brand/30 hover:bg-accent hover:text-foreground"
                >
                  <Icon name="plus" className="h-3 w-3" /> 添加
                </button>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border bg-card">
          <table className="w-full text-[13px]">
            <thead className="bg-muted/50">
              <tr className="text-left font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                <th className="px-3 py-2">任务</th>
                <th className="w-24 px-3 py-2">状态</th>
                <th className="w-20 px-3 py-2">优先级</th>
                <th className="w-40 px-3 py-2">负责人</th>
                <th className="w-20 px-3 py-2">截止</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((t) => {
                const a = t.assignee ? agentsById[t.assignee] : undefined
                const col = COLUMNS.find((c) => c.id === t.status)
                return (
                  <tr
                    key={t.id}
                    onClick={() => cycle(t)}
                    className="cursor-pointer border-t transition-colors hover:bg-muted/30"
                  >
                    <td className="px-3 py-2.5">
                      <span className="mr-2 font-mono text-[10.5px] text-muted-foreground">
                        {t.id}
                      </span>
                      {t.title}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-1.5">
                        <span className={cn('h-2 w-2 rounded-full', col?.dotClass)} />
                        {col?.label}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      {t.priority === 'high' || t.priority === 'critical' ? (
                        <Badge variant="brand">{PRIORITY_LABEL[t.priority]}</Badge>
                      ) : (
                        <span className="text-muted-foreground">{PRIORITY_LABEL[t.priority]}</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      {a ? (
                        <span className="inline-flex items-center gap-1.5">
                          <Avatar initial={a.name[0] ?? '?'} color={a.color} size={32} />
                          {a.name}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">未指派</span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-[11px] text-muted-foreground">
                      {t.due}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      <CreateTaskModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}
