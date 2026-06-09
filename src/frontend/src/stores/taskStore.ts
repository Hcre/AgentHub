import { create } from 'zustand'
import { tasksApi } from '../api/tasks'
import type { Priority, Task, TaskStatus } from '../types'

export type TaskView = 'kanban' | 'list'

export interface TaskFilter {
  status?: TaskStatus
  priority?: Priority
  assignee?: string
  q?: string
}

export interface CreateTaskInput {
  title: string
  assignee?: string
  due?: string
  priority: Priority
}

interface TaskState {
  tasks: Task[]
  view: TaskView
  showClosed: boolean
  filter: TaskFilter
  loaded: boolean
  loading: boolean

  load: () => Promise<void>
  setView: (view: TaskView) => void
  setShowClosed: (v: boolean) => void
  setFilter: (patch: Partial<TaskFilter>) => void
  moveTask: (id: string, status: TaskStatus) => void
  addTask: (status: TaskStatus, assignee?: string) => void
  createTask: (input: CreateTaskInput) => void
  removeTask: (id: string) => void
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  view: 'kanban',
  showClosed: true,
  filter: {},
  loaded: false,
  loading: false,

  load: async () => {
    if (get().loading) return
    set({ loading: true })
    try {
      const tasks = await tasksApi.list()
      set({ tasks, loaded: true })
    } catch (err) {
      console.error('加载任务失败', err)
    } finally {
      set({ loading: false })
    }
  },

  setView: (view) => set({ view }),
  setShowClosed: (showClosed) => set({ showClosed }),
  setFilter: (patch) => set((s) => ({ filter: { ...s.filter, ...patch } })),

  // 看板拖拽 / 卡片点击改状态：乐观更新 + 后端持久化，失败回滚重载。
  moveTask: (id, status) => {
    const prev = get().tasks
    set({ tasks: prev.map((t) => (t.id === id ? { ...t, status } : t)) })
    tasksApi.update(id, { status }).catch((err) => {
      console.error('更新任务状态失败', err)
      set({ tasks: prev })
    })
  },

  addTask: (status, assignee) => {
    tasksApi
      .create({ title: '未命名任务', status, priority: 'normal', assignee })
      .then((task) => set((s) => ({ tasks: [...s.tasks, task] })))
      .catch((err) => console.error('创建任务失败', err))
  },

  createTask: ({ title, assignee, due, priority }) => {
    tasksApi
      .create({ title, assignee, due, priority, status: 'todo' })
      .then((task) => set((s) => ({ tasks: [...s.tasks, task] })))
      .catch((err) => console.error('创建任务失败', err))
  },

  removeTask: (id) => {
    const prev = get().tasks
    set({ tasks: prev.filter((t) => t.id !== id) })
    tasksApi.remove(id).catch((err) => {
      console.error('删除任务失败', err)
      set({ tasks: prev })
    })
  },
}))
