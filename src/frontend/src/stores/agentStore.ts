import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { agentsApi } from '../api/agents'
import { uid } from '../lib/id'
import type { Agent, AgentColor, AgentProfile, ApiAgent, MemoryLevel } from '../types'

export interface CreateAgentInput {
  name: string
  role: string
  /** 运行时：自动检测的 CLI (opencode/claude_code/pi_agent/codex/gemini/cursor_agent) 或 mock */
  agentSystem: string
  provider: string
  model: string
  /** claude_code 经 proxy 透传的目标端点 */
  baseUrl?: string
  apiKey: string
  /** 头像（首字母/emoji），留空则用名称首字母合成 */
  avatar?: string
  skills: string[]
  capabilityTags: string[]
  systemPrompt?: string
  settings?: Record<string, unknown>
  templateName?: string
  templateId?: string
}

const COLOR_CYCLE: AgentColor[] = ['brand', 'sage', 'clay', 'rose', 'blue']
const DEFAULT_MEMORY: MemoryLevel[] = [
  { level: 'L1', name: 'Session', count: 0, hint: '活跃对话即时上下文' },
  { level: 'L2', name: 'Project', count: 0, hint: '' },
  { level: 'L3', name: 'Persona', count: 0, hint: '' },
  { level: 'L4', name: 'World', count: 0, hint: '' },
]

/** 后端 ApiAgent → UI Agent。online 乐观置 true（后端默认 offline）。 */
function toUiAgent(a: ApiAgent, idx: number): Agent {
  return {
    id: a.id,
    name: a.name,
    role: a.role,
    color: COLOR_CYCLE[idx % COLOR_CYCLE.length] ?? 'neutral',
    online: true,
    skillCount: a.skills.length,
    agentSystem: a.agent_system,
    templateName: a.template_name ?? undefined,
  }
}

function buildProfile(input: CreateAgentInput): AgentProfile {
  return {
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
}

interface AgentState {
  agents: Agent[]
  profiles: Record<string, AgentProfile>

  /** 从后端拉真实 Agent 并入列表（去重）；失败保持 seed mock。 */
  loadAgents: () => Promise<void>
  /** 创建 Agent：先同步后端取真实 UUID；后端不可用则本地降级 mock。 */
  createAgent: (input: CreateAgentInput) => Promise<string>
  removeAgent: (id: string) => Promise<void>
  updateConfig: (id: string, patch: Partial<AgentProfile['config']>) => void
}

export const useAgentStore = create<AgentState>()(
  persist(
    (set, get) => ({
  agents: [],
  profiles: {},

  loadAgents: async () => {
    try {
      const list = await agentsApi.list()
      set(() => {
        const incoming = list
          .filter((a) => !a.is_system)
          .map((a, i) => toUiAgent(a, i))
        return { agents: incoming }
      })
    } catch (e) {
      console.error('loadAgents failed, keeping current list:', e)
      // 后端不可用 → 保持当前列表（不丢失已加载的）
    }
  },

  createAgent: async (input) => {
    const avatar = input.avatar?.trim() || input.name.slice(0, 1).toUpperCase()
    const profile = buildProfile(input)
    try {
      const created = await agentsApi.create({
        name: input.name,
        avatar,
        role: input.role,
        agent_system: input.agentSystem,
        provider: input.provider,
        model: input.model,
        base_url: input.baseUrl,
        api_key: input.apiKey,
        skills: input.skills,
        capability_tags: input.capabilityTags,
        system_prompt: input.systemPrompt,
        settings: input.settings,
        template_name: input.templateName,
        template_id: input.templateId,
      })
      const agent = toUiAgent(created, get().agents.length)
      set((s) => ({
        agents: [...s.agents, agent],
        profiles: { ...s.profiles, [agent.id]: profile },
      }))
      return agent.id
    } catch (e) {
      // 后端返回具体错误 → 抛出给 UI 展示
      if (e instanceof Error && e.message.startsWith('API ')) throw e
      // 后端完全不可用（网络断开等）→ 本地降级 mock，保证 UI 不卡
      const id = uid('ag')
      const color = COLOR_CYCLE[get().agents.length % COLOR_CYCLE.length] ?? 'neutral'
      const agent: Agent = {
        id,
        name: input.name,
        role: input.role,
        color,
        online: true,
        skillCount: input.skills.length,
        agentSystem: input.agentSystem,
        templateName: input.templateName,
      }
      set((s) => ({
        agents: [...s.agents, agent],
        profiles: { ...s.profiles, [id]: profile },
      }))
      return id
    }
  },

  removeAgent: async (id) => {
    set((s) => {
      const profiles = { ...s.profiles }
      delete profiles[id]
      return { agents: s.agents.filter((a) => a.id !== id), profiles }
    })
    try {
      await agentsApi.remove(id)
    } catch {
      // 后端不可用或 mock agent（不在后端）→ 本地已删，忽略
    }
  },

  updateConfig: (id, patch) =>
    set((s) => {
      const p = s.profiles[id]
      if (!p) return {}
      return { profiles: { ...s.profiles, [id]: { ...p, config: { ...p.config, ...patch } } } }
    }),
  ),
  { name: 'agenthub-agents', partialize: (s) => ({ agents: s.agents }) },
))
