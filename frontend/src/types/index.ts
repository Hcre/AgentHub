// 与后端契约对齐的类型（StreamEvent / DTO）。

export type StreamEventType =
  | "text"
  | "thinking"
  | "tool_call"
  | "tool_result"
  | "request_approval"
  | "task_plan"
  | "error"
  | "done";

export interface StreamEvent {
  type: StreamEventType;
  seq: number;
  content?: string | null;
  tool_call?: unknown;
  tool_result?: unknown;
  task_plan?: Record<string, unknown> | null;
  metadata?: Record<string, unknown>;
}

export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  streaming?: boolean;
  contentType?: string;
}

export interface Agent {
  id: string;
  name: string;
  avatar: string;
  role: string;
  provider: string;
  model: string;
  status: string;
  skills: string[];
  capability_tags: string[];
  is_system: boolean;
  created_at: string;
}

export interface Session {
  id: string;
  type: "group" | "private";
  title: string;
  group_id: string | null;
  agent_id: string | null;
  created_at: string;
}
