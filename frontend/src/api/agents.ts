import { api } from "./client";
import type { ApiAgent } from "../types";

export interface CreateAgentInput {
  name: string;
  avatar: string;
  role: string;
  /** 运行时：claude_code / anthropic_api / mock。决定后端适配器选择。 */
  agent_system: string;
  provider: string;
  model: string;
  /** claude_code 经 proxy 透传的目标端点；anthropic_api/mock 可省略。 */
  base_url?: string;
  api_key: string;
  skills?: string[];
  system_prompt?: string;
}

export const agentsApi = {
  list: () => api.get<ApiAgent[]>("/api/agents"),
  get: (id: string) => api.get<ApiAgent>(`/api/agents/${id}`),
  create: (input: CreateAgentInput) => api.post<ApiAgent>("/api/agents", input),
  remove: (id: string) => api.del<void>(`/api/agents/${id}`),
};
