import { api } from './client'
import type { ApiMemory, ApiMemoryStats } from '../types'

export interface CreateMemoryInput {
  name: string
  description: string
  content: string
  group_id?: string | null
  scope?: 'agent' | 'group'
  metadata?: Record<string, unknown>
}

export interface UpdateMemoryInput {
  name?: string
  description?: string
  content?: string
  pinned?: boolean
  metadata?: Record<string, unknown>
}

export const memoriesApi = {
  list: (agentId: string) =>
    api.get<ApiMemory[]>(`/api/agents/${agentId}/memories`),
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
