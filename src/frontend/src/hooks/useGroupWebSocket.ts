import { useEffect, useRef } from 'react'
import { WS_BASE } from '../api/client'
import { useGroupStore } from '../stores/groupStore'
import type { StreamEvent } from '../types'

const MAX_RECONNECT_DELAY = 10000
const BASE_DELAY = 1000

/**
 * 群聊 WebSocket。逐 StreamEvent 路由到 groupStore.applyGroupStreamEvent(groupId, ...)。
 * @param groupId   当前激活的 UI Group id（即 messagesByGroup 的桶 key）
 * @param sessionId 后端 Session id；为 null 时不连接（等待 findOrCreateSession）
 */
export function useGroupWebSocket(groupId: string | null, sessionId: string | null) {
  const wsRef = useRef<WebSocket | null>(null)
  // groupId 用 ref 持有，避免重连闭包捕获旧值
  const gidRef = useRef<string | null>(groupId)
  useEffect(() => {
    gidRef.current = groupId
  }, [groupId])

  const apply = useGroupStore((s) => s.applyGroupStreamEvent)
  const setWs = useGroupStore((s) => s.setWs)
  const setConnected = useGroupStore((s) => s.setConnected)
  const flushPending = useGroupStore((s) => s.flushPending)

  useEffect(() => {
    if (!sessionId) return
    let closed = false
    let attempts = 0
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null

    const connect = () => {
      const ws = new WebSocket(`${WS_BASE}/ws/sessions/${sessionId}`)
      wsRef.current = ws
      setWs(ws)

      ws.onopen = () => {
        setConnected(true)
        attempts = 0
        // 把 CONNECTING 期间用户已点 send 但未发出去的消息回放
        const gid = gidRef.current
        if (gid) flushPending(gid)
      }

      ws.onclose = () => {
        setConnected(false)
        setWs(null)
        if (closed) return
        const delay = Math.min(BASE_DELAY * 2 ** attempts, MAX_RECONNECT_DELAY)
        attempts += 1
        reconnectTimer = setTimeout(connect, delay)
      }

      ws.onmessage = (e) => {
        const gid = gidRef.current
        if (!gid) return
        try {
          const event = JSON.parse(e.data as string) as StreamEvent
          apply(gid, event)
        } catch {
          // 忽略非 JSON 帧
        }
      }
    }

    connect()

    return () => {
      closed = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      wsRef.current?.close()
      wsRef.current = null
      setWs(null)
      setConnected(false)
    }
  }, [sessionId, apply, setWs, setConnected, flushPending])
}
