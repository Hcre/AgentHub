import { create } from 'zustand'
import { agents as seedAgents } from '../data/mock'
import { agentProfiles as seedProfiles } from '../data/extra'
import { uid } from '../lib/id'
import type { Agent, AgentColor, AgentProfile, MemoryLevel } from '../types'

export interface CreateAgentInput {
  name: string
  role: string
  provider: string
  model: string
  apiKey: string
  skills: string[]
  systemPrompt?: string
}

const COLOR_CYCLE: AgentColor[] = ['brand', 'sage', 'clay', 'rose', 'blue']
const DEFAULT_MEMORY: MemoryLevel[] = [
  { level: 'L1', name: 'Session', count: 0, hint: '活跃对话即时上下文' },
  { level: 'L2', name: 'Project', count: 0, hint: '' },
  { level: 'L3', name: 'Persona', count: 0, hint: '' },
  { level: 'L4', name: 'World', count: 0, hint: '' },
]

interface AgentState {
  agents: Agent[]
  profiles: Record<string, AgentProfile>

  createAgent: (input: CreateAgentInput) => string
  removeAgent: (id: string) => void
  updateConfig: (id: string, patch: Partial<AgentProfile['config']>) => void
}

export const useAgentStore = create<AgentState>((set, get) => ({
  agents: seedAgents,
  profiles: { ...seedProfiles },

  createAgent: (input) => {
    const id = uid('ag')
    const color = COLOR_CYCLE[get().agents.length % COLOR_CYCLE.length] ?? 'neutral'
    const agent: Agent = {
      id,
      name: input.name,
      role: input.role,
      color,
      online: true,
      skillCount: input.skills.length,
    }
    const profile: AgentProfile = {
      // apiKey 不入前端 store（红线：密钥不留存明文），仅传给后端
      bio: input.systemPrompt?.trim() || input.role,
      load: 0,
      groups: [],
      capabilities: input.skills,
      memoryByLevel: DEFAULT_MEMORY,
      config: {
        provider: input.provider,
        model: input.model,
        maxTokens: 4096,
        concurrency: 1,
        temperature: 0.5,
      },
    }
    set((s) => ({
      agents: [...s.agents, agent],
      profiles: { ...s.profiles, [id]: profile },
    }))
    return id
  },

  removeAgent: (id) =>
    set((s) => {
      const profiles = { ...s.profiles }
      delete profiles[id]
      return { agents: s.agents.filter((a) => a.id !== id), profiles }
    }),

  updateConfig: (id, patch) =>
    set((s) => {
      const p = s.profiles[id]
      if (!p) return {}
      return { profiles: { ...s.profiles, [id]: { ...p, config: { ...p.config, ...patch } } } }
    }),
}))
