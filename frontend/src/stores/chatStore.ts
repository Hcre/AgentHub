import { create } from "zustand";
import type { ChatMessage, StreamEvent } from "@/types";

interface ChatState {
  messages: ChatMessage[];
  connected: boolean;
  setConnected: (v: boolean) => void;
  addUserMessage: (content: string) => void;
  /** 处理来自 WS 的流式事件，增量更新当前 assistant 气泡。 */
  applyStreamEvent: (event: StreamEvent) => void;
  reset: (messages?: ChatMessage[]) => void;
}

const STREAMING_ID = "__streaming__";

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  connected: false,

  setConnected: (v) => set({ connected: v }),

  addUserMessage: (content) =>
    set((s) => ({
      messages: [
        ...s.messages,
        { id: crypto.randomUUID(), role: "user", content },
      ],
    })),

  applyStreamEvent: (event) =>
    set((s) => {
      const messages = [...s.messages];
      const idx = messages.findIndex((m) => m.id === STREAMING_ID);

      switch (event.type) {
        case "text": {
          if (idx === -1) {
            messages.push({
              id: STREAMING_ID,
              role: "assistant",
              content: event.content ?? "",
              streaming: true,
            });
          } else {
            messages[idx] = {
              ...messages[idx],
              content: messages[idx].content + (event.content ?? ""),
            };
          }
          return { messages };
        }
        case "done": {
          if (idx !== -1) {
            messages[idx] = {
              ...messages[idx],
              id: crypto.randomUUID(),
              streaming: false,
            };
          }
          return { messages };
        }
        case "error": {
          messages.push({
            id: crypto.randomUUID(),
            role: "system",
            content: `⚠️ ${event.content ?? "未知错误"}`,
          });
          return { messages };
        }
        default:
          return { messages: s.messages };
      }
    }),

  reset: (messages = []) => set({ messages }),
}));
