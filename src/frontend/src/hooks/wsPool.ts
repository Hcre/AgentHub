/** 持久 WebSocket 池 — 切换会话时旧连接继续收流 */
const _pool: Record<string, WebSocket> = {}

export function getPoolWs(key: string): WebSocket | undefined {
  return _pool[key]
}

export function setPoolWs(key: string, ws: WebSocket): void {
  _pool[key] = ws
}

export function closePoolWs(key: string): void {
  const ws = _pool[key]
  if (ws) {
    ws.close()
    delete _pool[key]
  }
}

/** 关闭指定 session 的所有连接（删除会话时清理） */
export function closeSessionWs(sessionId: string): void {
  const prefix = `${sessionId}:`
  for (const key of Object.keys(_pool)) {
    if (key.startsWith(prefix)) {
      _pool[key].close()
      delete _pool[key]
    }
  }
}
