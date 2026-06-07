/**
 * URL 解析工具 —— 给 WebPreviewCard 与 MessageBubble 共享。
 * 拆出来是为了避开 react-refresh/only-export-components：
 * 任何 .tsx 文件只导出 React 组件时，HMR 才能稳定工作。
 */

/**
 * 从 text 中抓 http(s) URL —— 退化路径（当 msg.urls 缺失时使用）。
 * 实现细节：贪婪匹配 url，到第一个空白/标点结束（避免抓括号里的尾巴）。
 */
const URL_REGEX = /https?:\/\/[^\s<>"']+/g

export function extractUrls(text: string): string[] {
  if (!text) return []
  const matches = text.match(URL_REGEX)
  if (!matches) return []
  // 去重保序
  const seen = new Set<string>()
  const result: string[] = []
  for (const m of matches) {
    if (!seen.has(m)) {
      seen.add(m)
      result.push(m)
    }
  }
  return result
}

/**
 * 合并显式 urls 字段 + 从 text 抓的退化 URL，去重保序。
 * 这是 MessageBubble 里调用的入口。
 */
export function collectUrls(text: string, declared?: readonly string[]): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  const push = (u: string) => {
    if (!seen.has(u)) {
      seen.add(u)
      out.push(u)
    }
  }
  for (const u of declared ?? []) push(u)
  for (const u of extractUrls(text)) push(u)
  return out
}

/**
 * 从 url 推导 host（用于展示「站点名 + favicon」）。
 * 解析失败时回落到 url 本身。
 */
export function getHost(url: string): string {
  try {
    return new URL(url).hostname
  } catch {
    return url
  }
}
