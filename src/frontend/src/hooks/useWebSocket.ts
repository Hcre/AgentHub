import { useCallback, useEffect, useRef } from "react";
import { WS_BASE } from "../api/client";
import { useChatStore } from "../stores/chatStore";
import { getPoolWs, setPoolWs } from "./wsPool";
import type { Attachment, ReplyRef, StreamEvent } from "../types";

const MAX_RECONNECT_DELAY = 10000;
const BASE_DELAY = 1000;

export function useWebSocket(sessionId: string | null, convKey: string | null) {
  const applyStreamEvent = useChatStore((s) => s.applyStreamEvent);
  const setConnected = useChatStore((s) => s.setConnected);
  const addUserMessage = useChatStore((s) => s.addUserMessage);
  const keyRef = useRef(convKey);
  keyRef.current = convKey;

  useEffect(() => {
    if (!sessionId || !convKey) return;
    const poolKey = `${sessionId}:${convKey}`;

    // 已有活跃连接 → 复用
    const existing = getPoolWs(poolKey);
    if (existing && existing.readyState === WebSocket.OPEN) {
      setConnected(true);
      return;
    }

    let attempts = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/sessions/${sessionId}`);
      setPoolWs(poolKey, ws);

      ws.onopen = () => { setConnected(true); attempts = 0; };
      ws.onclose = () => {
        setConnected(false);
        const delay = Math.min(BASE_DELAY * 2 ** attempts, MAX_RECONNECT_DELAY);
        attempts += 1;
        reconnectTimer = setTimeout(connect, delay);
      };
      ws.onmessage = (e) => {
        try {
          applyStreamEvent(keyRef.current!, JSON.parse(e.data) as StreamEvent);
        } catch { /* ignore */ }
      };
    };

    connect();

    return () => {
      // 组件卸载不关 WS — 后台继续收流
      if (reconnectTimer) clearTimeout(reconnectTimer);
    };
  }, [sessionId, convKey, applyStreamEvent, setConnected]);

  const sendMessage = useCallback(
    (content: string, attachment?: Attachment, replyTo?: ReplyRef): boolean => {
      if (!sessionId || !convKey) return false;
      const ws = getPoolWs(`${sessionId}:${convKey}`);
      if (!ws || ws.readyState !== WebSocket.OPEN) return false;
      addUserMessage(convKey, content, attachment, replyTo);
      ws.send(JSON.stringify({
        type: "message",
        content: attachment?.url
          ? `${content}\n\n[attachment] ${attachment.name} ${attachment.url}`
          : content,
        ...(replyTo ? { reply_to_id: replyTo.id } : {}),
      }));
      return true;
    },
    [addUserMessage, sessionId, convKey],
  );

  return { sendMessage, cancel: () => {
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'cancel' }))
    }
  } };
}
