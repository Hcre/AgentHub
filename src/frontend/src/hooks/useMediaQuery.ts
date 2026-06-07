import { useSyncExternalStore } from 'react'

/**
 * 返回 `window.matchMedia(query).matches` 的响应式布尔值。
 *
 * 用途：移动端 H5 响应式（< 768px 折叠 4 栏 shell）。
 * 设计要点：
 *   - SSR 安全：`typeof window === 'undefined'` 时返回 `false`（默认桌面行为）
 *   - 订阅 change 事件，窗口 resize / 设备方向变化实时更新
 *   - 用 `useSyncExternalStore` 实现（无 setState-in-effect 违例）
 *
 * @example
 *   const isMobile = useMediaQuery('(max-width: 767px)')
 *   const isDesktop = useMediaQuery('(min-width: 1024px)')
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
        return () => undefined
      }
      const mq = window.matchMedia(query)
      mq.addEventListener('change', notify)
      return () => {
        mq.removeEventListener('change', notify)
      }
    },
    () => {
      if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
        return false
      }
      return window.matchMedia(query).matches
    },
    () => false, // SSR snapshot
  )
}
