import { create } from "zustand";
import type { Agent } from "@/types";
import { agentsApi } from "@/api/agents";

interface AgentState {
  agents: Agent[];
  loading: boolean;
  load: () => Promise<void>;
}

export const useAgentStore = create<AgentState>((set) => ({
  agents: [],
  loading: false,
  load: async () => {
    set({ loading: true });
    try {
      const agents = await agentsApi.list();
      set({ agents });
    } finally {
      set({ loading: false });
    }
  },
}));
