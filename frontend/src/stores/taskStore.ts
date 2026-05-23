import { create } from 'zustand'
import { tasks as mockTasks } from '../data/mock'
import { uid } from '../lib/id'
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

  setView: (view: TaskView) => void
  setShowClosed: (v: boolean) => void
  setFilter: (patch: Partial<TaskFilter>) => void
  moveTask: (id: string, status: TaskStatus) => void
  addTask: (status: TaskStatus, assignee?: string) => void
  createTask: (input: CreateTaskInput) => void
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: mockTasks,
  view: 'kanban',
  showClosed: true,
  filter: {},

  setView: (view) => set({ view }),
  setShowClosed: (showClosed) => set({ showClosed }),
  setFilter: (patch) => set((s) => ({ filter: { ...s.filter, ...patch } })),

  moveTask: (id, status) =>
    set((s) => ({ tasks: s.tasks.map((t) => (t.id === id ? { ...t, status } : t)) })),

  addTask: (status, assignee) => {
    const n = get().tasks.length + 1
    const task: Task = {
      id: `T-${n}`,
      title: '未命名任务',
      status,
      priority: 'normal',
      assignee,
      due: '—',
    }
    set((s) => ({ tasks: [...s.tasks, task] }))
  },

  createTask: ({ title, assignee, due, priority }) => {
    const task: Task = {
      id: uid('T-'),
      title,
      status: 'todo',
      priority,
      assignee,
      due: due || '—',
    }
    set((s) => ({ tasks: [...s.tasks, task] }))
  },
}))
