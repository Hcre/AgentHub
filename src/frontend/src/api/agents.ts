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

export const agentsApi = {
  list: () => api.get<ApiAgent[]>("/api/agents"),
  get: (id: string) => api.get<ApiAgent>(`/api/agents/${id}`),
  create: (input: CreateAgentInput) => api.post<ApiAgent>("/api/agents", input),
  remove: (id: string) => api.del<void>(`/api/agents/${id}`),
  /** 连通性检查：获取 Agent 配置确认可用 */
  ping: (id: string) => api.get<ApiAgent>(`/api/agents/${id}`),
};
