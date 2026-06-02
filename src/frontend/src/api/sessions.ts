import { api } from "./client";
import type { Session } from "../types";

export interface MessageOut {
  id: string;
  role: string;
  content: string;
  content_type: string;
  sender_agent_id?: string | null;
  mentions?: string[];
  created_at?: string;
}

export const sessionsApi = {
  list: (params?: { type?: string }) => {
    const qs = params?.type ? `?type=${encodeURIComponent(params.type)}` : "";
    return api.get<Session[]>(`/api/sessions${qs}`);
  },
  createPrivate: (agentId: string, title = "", workspacePath = "") =>
    api.post<Session>("/api/sessions", {
      type: "private",
      agent_id: agentId,
      title,
      workspace_path: workspacePath,
    }),
  createGroup: (groupId: string, title = "", workspacePath = "") =>
    api.post<Session>("/api/sessions", {
      type: "group",
      group_id: groupId,
      title,
      workspace_path: workspacePath,
    }),
  messages: (sessionId: string) =>
    api.get<MessageOut[]>(`/api/sessions/${sessionId}/messages`),
};
