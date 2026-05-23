import { useState } from 'react'
import { agents } from '../../data/mock'
import { useTaskStore } from '../../stores/taskStore'
import { Button, Dialog, DialogContent, Icon, Input } from '../ui'
import { PRIORITY_LABEL } from './columns'
import type { Priority } from '../../types'

const SELECT_CLS =
  'h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring'

export function CreateTaskModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const createTask = useTaskStore((s) => s.createTask)
  const [title, setTitle] = useState('')
  const [assignee, setAssignee] = useState<string>('')
  const [due, setDue] = useState('')
  const [priority, setPriority] = useState<Priority>('normal')

  const reset = () => {
    setTitle('')
    setAssignee('')
    setDue('')
    setPriority('normal')
  }

  const submit = () => {
    if (!title.trim()) return
    createTask({ title: title.trim(), assignee: assignee || undefined, due, priority })
    reset()
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-[15px] font-medium">创建任务</h3>
          <Button variant="ghost" size="iconSm" onClick={onClose}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        <div className="flex flex-col gap-3 p-4">
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">标题 *</span>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="任务标题"
              autoFocus
            />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-muted-foreground">负责人</span>
              <select
                className={SELECT_CLS}
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
              >
                <option value="">未指派</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-[12px] font-medium text-muted-foreground">优先级</span>
              <select
                className={SELECT_CLS}
                value={priority}
                onChange={(e) => setPriority(e.target.value as Priority)}
              >
                {(['low', 'normal', 'high', 'critical'] as Priority[]).map((p) => (
                  <option key={p} value={p}>
                    {PRIORITY_LABEL[p]}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">截止</span>
            <Input
              value={due}
              onChange={(e) => setDue(e.target.value)}
              placeholder="如 Today / Wed / 05-30"
            />
          </label>
        </div>

        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button variant="brand" size="sm" onClick={submit} disabled={!title.trim()}>
            创建
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}
