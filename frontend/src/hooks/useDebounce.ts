import { useEffect, useState } from 'react'

/** 返回 value 的防抖副本：value 停止变化 delay ms 后才更新。 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState<T>(value)
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return debounced
}
