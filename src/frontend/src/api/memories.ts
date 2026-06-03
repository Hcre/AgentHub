import { api } from './client'
import type { ApiMemory, ApiMemoryStats, MemoryType } from '../types'

export interface CreateMemoryInput {
  name: string
  description: string
  memory_type: MemoryType
  content: string
  scope?: 'agent' | 'group'
  group_id?: string | null
  metadata?: Record<string, unknown>
}

export interface UpdateMemoryInput {
  content?: string
  memory_type?: MemoryType
  pinned?: boolean
  metadata?: Record<string, unknown>
}

export const memoriesApi = {
  list: (agentId: string, type?: string) => {
    const params = type ? `?memory_type=${type}` : ''
    return api.get<ApiMemory[]>(`/api/agents/${agentId}/memories${params}`)
  },
  stats: (agentId: string) =>
    api.get<ApiMemoryStats>(`/api/agents/${agentId}/memories/stats`),
  get: (agentId: string, memoryId: string) =>
    api.get<ApiMemory>(`/api/agents/${agentId}/memories/${memoryId}`),
  create: (agentId: string, input: CreateMemoryInput) =>
    api.post<ApiMemory>(`/api/agents/${agentId}/memories`, input),
  update: (agentId: string, memoryId: string, input: UpdateMemoryInput) =>
    api.patch<ApiMemory>(`/api/agents/${agentId}/memories/${memoryId}`, input),
  remove: (agentId: string, memoryId: string) =>
    api.del<void>(`/api/agents/${agentId}/memories/${memoryId}`),
}
