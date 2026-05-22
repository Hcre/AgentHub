import { useCallback, useEffect, useRef } from "react";
import { WS_BASE } from "@/api/client";
import { useChatStore } from "@/stores/chatStore";
import type { StreamEvent } from "@/types";

const MAX_RECONNECT_DELAY = 10000;
const BASE_DELAY = 1000;

export function useWebSocket(sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptRef = useRef(0);
  const applyStreamEvent = useChatStore((s) => s.applyStreamEvent);
  const setConnected = useChatStore((s) => s.setConnected);
  const addUserMessage = useChatStore((s) => s.addUserMessage);

  const connect = useCallback(
    (id: string) => {
      const ws = new WebSocket(`${WS_BASE}/ws/sessions/${id}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        attemptRef.current = 0;
      };

      ws.onclose = () => {
        setConnected(false);
        const delay = Math.min(
          BASE_DELAY * Math.pow(2, attemptRef.current),
          MAX_RECONNECT_DELAY
        );
        attemptRef.current += 1;
        reconnectTimer.current = setTimeout(() => connect(id), delay);
      };

      ws.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data) as StreamEvent;
          applyStreamEvent(event);
        } catch {
          // ignore non-JSON
        }
      };
    },
    [applyStreamEvent, setConnected]
  );

  useEffect(() => {
    if (!sessionId) return;
    connect(sessionId);

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [sessionId, connect]);

  const sendMessage = useCallback(
    (content: string) => {
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) return;
      addUserMessage(content);
      ws.send(JSON.stringify({ type: "message", content }));
    },
    [addUserMessage]
  );

  return { sendMessage };
}
