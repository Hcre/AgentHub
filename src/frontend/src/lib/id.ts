/** 生成短随机 id（mock 用，正式由后端发号）。 */
export function uid(prefix = 'id'): string {
  return prefix + Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
}

/** HH:MM 时间戳。 */
export function nowStamp(): string {
  const n = new Date()
  return `${String(n.getHours()).padStart(2, '0')}:${String(n.getMinutes()).padStart(2, '0')}`
}
