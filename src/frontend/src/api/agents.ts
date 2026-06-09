import { api } from "./client";
import type { ApiAgent } from "../types";

export interface CreateAgentInput {
  name: string;
  avatar: string;
  role: string;
  /** 运行时：自动检测的 CLI (opencode/claude_code/pi_agent/codex/gemini/cursor_agent) 或 mock。 */
  agent_system: string;
  skills?: string[];
  capability_tags?: string[];
  system_prompt?: string;
  settings?: Record<string, unknown>;
  template_name?: string;
  template_id?: string;
}

/** 对应 backend `AgentUpdateRequest`（schemas/agent.py）：全字段可选，PATCH 局部更新。 */
export interface UpdateAgentInput {
  name?: string;
  avatar?: string;
  role?: string;
  agent_system?: string;
  provider?: string;
  model?: string;
  api_key?: string;
  base_url?: string;
  skills?: string[];
  capability_tags?: string[];
  settings?: Record<string, unknown>;
  system_prompt?: string;
}

/** M1#4 对话式创建：后端抽出的 Agent 草稿 */
export interface AgentDraft {
  name: string
  role: string
  system_prompt: string
  skills: string[]
  source: string
}

export const agentsApi = {
  list: () => api.get<ApiAgent[]>("/api/agents"),
  get: (id: string) => api.get<ApiAgent>(`/api/agents/${id}`),
  create: (input: CreateAgentInput) => api.post<ApiAgent>("/api/agents", input),
  update: (id: string, input: UpdateAgentInput) =>
    api.patch<ApiAgent>(`/api/agents/${id}`, input),
  remove: (id: string) => api.del<void>(`/api/agents/${id}`),
  /** 连通性检查：获取 Agent 配置确认可用 */
  ping: (id: string) => api.get<ApiAgent>(`/api/agents/${id}`),
  /** M1#4 对话式创建：自然语言 → Agent 草稿（不持久化） */
  draftFromChat: (description: string) =>
    api.post<AgentDraft>("/api/agents/draft-from-chat", { description }),
};
