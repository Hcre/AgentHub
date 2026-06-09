// Tasks API client — 封装后端 /api/tasks 端点
// 对齐 `src/backend/app/api/routers/tasks.py` + `app/schemas/task.py`
//
// 词表映射：后端存领域枚举（status 7 态 / priority 4 级），前端看板用 4 列简化词表。
//   status:   todo<->pending  doing<->running  blocked<->blocked  done<->completed
//   priority: normal<->medium  其余同名

import type { Priority, Task, TaskStatus } from '../types'
import { api } from './client'

interface BackendTask {
  id: string
  title: string
  description: string
  status: string
  priority: string
  assignee: string | null
  due: string | null
  source: string
  session_id: string | null
  created_at: string
  updated_at: string
}

interface BackendTaskList {
  items: BackendTask[]
  total: number
}

const STATUS_TO_UI: Record<string, TaskStatus> = {
  pending: 'todo',
  running: 'doing',
  verifying: 'doing',
  blocked: 'blocked',
  failed: 'blocked',
  completed: 'done',
  cancelled: 'done',
}

const STATUS_TO_BACKEND: Record<TaskStatus, string> = {
  todo: 'pending',
  doing: 'running',
  blocked: 'blocked',
  done: 'completed',
}

const toUiPriority = (p: string): Priority => (p === 'medium' ? 'normal' : (p as Priority))
const toBackendPriority = (p: Priority): string => (p === 'normal' ? 'medium' : p)

function toUiTask(b: BackendTask): Task {
  return {
    id: b.id,
    title: b.title,
    status: STATUS_TO_UI[b.status] ?? 'todo',
    priority: toUiPriority(b.priority),
    assignee: b.assignee ?? undefined,
    due: b.due ?? '—',
  }
}

export interface CreateTaskBody {
  title: string
  status?: TaskStatus
  priority?: Priority
  assignee?: string
  due?: string
}

export interface UpdateTaskBody {
  title?: string
  status?: TaskStatus
  priority?: Priority
  assignee?: string | null
  due?: string | null
}

export const tasksApi = {
  list: async (): Promise<Task[]> => {
    const res = await api.get<BackendTaskList>('/api/tasks')
    return res.items.map(toUiTask)
  },

  create: async (body: CreateTaskBody): Promise<Task> => {
    const payload: Record<string, unknown> = { title: body.title }
    if (body.status) payload.status = STATUS_TO_BACKEND[body.status]
    if (body.priority) payload.priority = toBackendPriority(body.priority)
    if (body.assignee !== undefined) payload.assignee = body.assignee
    if (body.due !== undefined && body.due !== '—') payload.due = body.due
    return toUiTask(await api.post<BackendTask>('/api/tasks', payload))
  },

  update: async (id: string, body: UpdateTaskBody): Promise<Task> => {
    const payload: Record<string, unknown> = {}
    if (body.title !== undefined) payload.title = body.title
    if (body.status !== undefined) payload.status = STATUS_TO_BACKEND[body.status]
    if (body.priority !== undefined) payload.priority = toBackendPriority(body.priority)
    if (body.assignee !== undefined) payload.assignee = body.assignee
    if (body.due !== undefined) payload.due = body.due
    return toUiTask(await api.patch<BackendTask>(`/api/tasks/${id}`, payload))
  },

  remove: (id: string) => api.del<void>(`/api/tasks/${id}`),
}
