import { useCallback, useEffect, useRef } from "react";
import { WS_BASE } from "../api/client";
import { useChatStore } from "../stores/chatStore";
import type { StreamEvent } from "../types";

const MAX_RECONNECT_DELAY = 10000;
const BASE_DELAY = 1000;

/**
 * 会话 WebSocket（key-aware）。服务端 StreamEvent 按 convKey 路由到对应消息桶。
 * @param sessionId 后端 Session id；为 null 时不连接（mock 降级）
 * @param convKey   chatStore 消息桶键（agentId:conversationId）
 */
export function useWebSocket(sessionId: string | null, convKey: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  // convKey 用 ref 持有，避免重连闭包捕获旧值；在 effect 中同步（不在 render 期写）
  const keyRef = useRef<string | null>(convKey);
  useEffect(() => {
    keyRef.current = convKey;
  }, [convKey]);

  const applyStreamEvent = useChatStore((s) => s.applyStreamEvent);
  const setConnected = useChatStore((s) => s.setConnected);
  const addUserMessage = useChatStore((s) => s.addUserMessage);

  useEffect(() => {
    if (!sessionId) return;
    let attempts = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/sessions/${sessionId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        attempts = 0;
      };

      ws.onclose = () => {
        setConnected(false);
        if (closed) return;
        const delay = Math.min(BASE_DELAY * 2 ** attempts, MAX_RECONNECT_DELAY);
        attempts += 1;
        reconnectTimer = setTimeout(connect, delay);
      };

      ws.onmessage = (e) => {
        const key = keyRef.current;
        if (!key) return;
        try {
          const event = JSON.parse(e.data as string) as StreamEvent;
          applyStreamEvent(key, event);
        } catch {
          // 忽略非 JSON 帧
        }
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [sessionId, applyStreamEvent, setConnected]);

  /** 发送用户消息。返回 false 表示未连接，调用方可降级到 mock。 */
  const sendMessage = useCallback(
    (content: string): boolean => {
      const ws = wsRef.current;
      const key = keyRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN || !key) return false;
      addUserMessage(key, content);
      ws.send(JSON.stringify({ type: "message", content }));
      return true;
    },
    [addUserMessage],
  );

  return { sendMessage };
}
