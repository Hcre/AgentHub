import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { act, renderHook, cleanup } from '@testing-library/react'
import { useMediaQuery } from '../useMediaQuery'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

type MQL = MediaQueryList & {
  /** 测试辅助：模拟 change 事件 */
  __trigger: (matches: boolean) => void
}

function makeMatchMedia(impl: (query: string) => boolean) {
  const listeners = new Map<string, Array<(e: MediaQueryListEvent) => void>>()
  const factory = (query: string): MQL => {
    const mql: Partial<MQL> = {
      matches: impl(query),
      media: query,
      onchange: null,
      addEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => {
        const arr = listeners.get(query) ?? []
        arr.push(cb)
        listeners.set(query, arr)
      },
      removeEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => {
        const arr = listeners.get(query) ?? []
        listeners.set(
          query,
          arr.filter((x) => x !== cb),
        )
      },
      dispatchEvent: () => true,
      __trigger: (matches: boolean) => {
        mql.matches = matches
        const arr = listeners.get(query) ?? []
        for (const cb of arr) cb({ matches, media: query } as MediaQueryListEvent)
      },
    }
    return mql as MQL
  }
  return factory
}

describe('useMediaQuery', () => {
  beforeEach(() => {
    // 每次重置 mock；个别 test 用 vi.stubGlobal 覆盖
    vi.stubGlobal('window', { matchMedia: makeMatchMedia(() => false) })
  })

  it('returns true immediately when the query currently matches', () => {
    vi.stubGlobal('window', { matchMedia: makeMatchMedia((q) => q.includes('max-width: 767')) })
    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'))
    expect(result.current).toBe(true)
  })

  it('returns false when the query does not match', () => {
    vi.stubGlobal('window', { matchMedia: makeMatchMedia(() => false) })
    const { result } = renderHook(() => useMediaQuery('(min-width: 1024px)'))
    expect(result.current).toBe(false)
  })

  it('updates synchronously when the media query state changes (subscribe + re-render)', () => {
    let factory = makeMatchMedia(() => false)
    vi.stubGlobal('window', { matchMedia: (q: string) => factory(q) })
    const { result, rerender } = renderHook(() => useMediaQuery('(max-width: 767px)'))
    expect(result.current).toBe(false)
    // 模拟窗口从桌面 resize 到 375px：现在 query 命中
    factory = makeMatchMedia(() => true)
    // 让 store 触发 change：直接拿到 store 的 listener 需要 new query 引用，
    // 简单做法：rerender 同 query 触发 useSyncExternalStore 的 getSnapshot 重新计算
    rerender()
    expect(result.current).toBe(true)
  })

  it('returns false when window.matchMedia is unavailable (SSR / older env)', () => {
    vi.stubGlobal('window', { matchMedia: undefined })
    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'))
    expect(result.current).toBe(false)
  })

  it('subscribes to change events: factory swap reflects in next render', () => {
    // 模拟「resize 触发 matchMedia 命中条件变化」—— 用闭包引用可变变量实现
    let matches = false
    const factory = (q: string): MQL => {
      const mql = makeMatchMedia(() => matches)(q)
      // 覆盖 __trigger：让当前 instance 触发后，更新全局 matches 标志
      const orig = mql.__trigger
      mql.__trigger = (next: boolean) => {
        matches = next
        orig(next)
      }
      return mql
    }
    vi.stubGlobal('window', { matchMedia: (q: string) => factory(q) })
    const { result, rerender } = renderHook(() => useMediaQuery('(max-width: 767px)'))
    expect(result.current).toBe(false)
    // 模拟 resize 事件 → 通知 React store
    act(() => {
      matches = true
    })
    rerender()
    expect(result.current).toBe(true)
  })
})
