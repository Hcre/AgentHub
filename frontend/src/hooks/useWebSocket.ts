import { useCallback, useEffect, useRef } from "react";
import { WS_BASE } from "@/api/client";
import { useChatStore } from "@/stores/chatStore";
import type { StreamEvent } from "@/types";

/**
 * 管理某个会话的 WebSocket 连接，将流式事件喂给 chatStore。
 * 返回 sendMessage 供输入框调用。
 */
export function useWebSocket(sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const applyStreamEvent = useChatStore((s) => s.applyStreamEvent);
  const setConnected = useChatStore((s) => s.setConnected);
  const addUserMessage = useChatStore((s) => s.addUserMessage);

  useEffect(() => {
    if (!sessionId) return;
    const ws = new WebSocket(`${WS_BASE}/ws/sessions/${sessionId}`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as StreamEvent;
        applyStreamEvent(event);
      } catch {
        // 忽略非 JSON 帧
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [sessionId, applyStreamEvent, setConnected]);

  const sendMessage = useCallback(
    (content: string) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      addUserMessage(content);
      ws.send(JSON.stringify({ type: "message", content }));
    },
    [addUserMessage],
  );

  return { sendMessage };
}
