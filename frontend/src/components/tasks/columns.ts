import type { Priority, TaskStatus } from '../../types'

export interface ColumnDef {
  id: TaskStatus
  label: string
  dotClass: string
}

export const COLUMNS: ColumnDef[] = [
  { id: 'todo', label: '待处理', dotClass: 'border-2 border-muted-foreground/40' },
  { id: 'doing', label: '进行中', dotClass: 'bg-brand/60 border-2 border-brand' },
  { id: 'blocked', label: '阻塞', dotClass: 'bg-amber-400 border-2 border-amber-500' },
  { id: 'done', label: '完成', dotClass: 'bg-emerald-500 border-2 border-emerald-600' },
]

export const PRIORITY_LABEL: Record<Priority, string> = {
  low: '低',
  normal: '普通',
  high: '高',
  critical: '紧急',
}
