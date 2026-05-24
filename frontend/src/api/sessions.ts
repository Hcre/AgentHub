import { api } from "./client";
import type { Session } from "../types";

interface MessageOut {
  id: string;
  role: string;
  content: string;
  content_type: string;
}

export const sessionsApi = {
  list: () => api.get<Session[]>("/api/sessions"),
  createPrivate: (agentId: string, title = "") =>
    api.post<Session>("/api/sessions", {
      type: "private",
      agent_id: agentId,
      title,
    }),
  messages: (sessionId: string) =>
    api.get<MessageOut[]>(`/api/sessions/${sessionId}/messages`),
};
