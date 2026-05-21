import { api } from "@/api/client";
import type { Agent } from "@/types";

export interface CreateAgentInput {
  name: string;
  avatar: string;
  role: string;
  provider: string;
  model: string;
  api_key: string;
  skills?: string[];
  system_prompt?: string;
}

export const agentsApi = {
  list: () => api.get<Agent[]>("/api/agents"),
  get: (id: string) => api.get<Agent>(`/api/agents/${id}`),
  create: (input: CreateAgentInput) => api.post<Agent>("/api/agents", input),
  remove: (id: string) => api.del<void>(`/api/agents/${id}`),
};
