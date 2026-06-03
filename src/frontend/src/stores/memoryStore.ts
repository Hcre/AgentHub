import { create } from 'zustand'
import { memoriesApi } from '../api/memories'
import type { CreateMemoryInput, UpdateMemoryInput } from '../api/memories'
import type { ApiMemory, ApiMemoryStats, MemoryType } from '../types'

interface MemoryState {
  memories: ApiMemory[]
  stats: ApiMemoryStats | null
  filterType: MemoryType | null
  editingId: string | null
  deletingId: string | null
  loading: boolean

  load: (agentId: string) => Promise<void>
  loadStats: (agentId: string) => Promise<void>
  setFilter: (type: MemoryType | null) => void
  setEditing: (id: string | null) => void
  setDeleting: (id: string | null) => void
  createMemory: (agentId: string, input: CreateMemoryInput) => Promise<void>
  updateMemory: (agentId: string, memoryId: string, input: UpdateMemoryInput) => Promise<void>
  deleteMemory: (agentId: string, memoryId: string) => Promise<void>
  togglePin: (agentId: string, memory: ApiMemory) => Promise<void>
}

export const useMemoryStore = create<MemoryState>((set, get) => ({
  memories: [],
  stats: null,
  filterType: null,
  editingId: null,
  deletingId: null,
  loading: false,

  load: async (agentId) => {
    set({ loading: true })
    try {
      const filter = get().filterType
      const memories = await memoriesApi.list(agentId, filter ?? undefined)
      set({ memories, loading: false })
    } catch {
      set({ loading: false })
    }
  },

  loadStats: async (agentId) => {
    try {
      const stats = await memoriesApi.stats(agentId)
      set({ stats })
    } catch {
      // 后端不可用 → 保持 null
    }
  },

  setFilter: (type) => set({ filterType: type }),
  setEditing: (id) => set({ editingId: id, deletingId: null }),
  setDeleting: (id) => set({ deletingId: id, editingId: null }),

  createMemory: async (agentId, input) => {
    const created = await memoriesApi.create(agentId, input)
    set((s) => ({ memories: [created, ...s.memories] }))
  },

  updateMemory: async (agentId, memoryId, input) => {
    const updated = await memoriesApi.update(agentId, memoryId, input)
    set((s) => ({
      memories: s.memories.map((m) => (m.id === memoryId ? updated : m)),
      editingId: null,
    }))
  },

  deleteMemory: async (agentId, memoryId) => {
    await memoriesApi.remove(agentId, memoryId)
    set((s) => ({
      memories: s.memories.filter((m) => m.id !== memoryId),
      deletingId: null,
    }))
  },

  togglePin: async (agentId, memory) => {
    const updated = await memoriesApi.update(agentId, memory.id, { pinned: !memory.pinned })
    set((s) => ({
      memories: s.memories.map((m) => (m.id === memory.id ? updated : m)),
    }))
  },
}))
