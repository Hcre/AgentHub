import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { TokenMonitorPanel } from '../TokenMonitorPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

/**
 * BDD B-4-P2-T6（Day 2 t6-m5-5-3-token-ui）— Token 监控 UI 暴露
 *
 * 验收点（来自 docs/specs/04-commands §6.4.8 B-4-P2-T6）：
 *   When-1 打开 dialog → 自动拉 /api/usage/global?window={1h|24h|7d} 3 端点
 *   When-2 数据返回 → 3 卡片展示 prompt / completion / total
 *   When-3 任一端点非 200 → 卡片显示「—」+ 全局 error 提示
 *
 * 3 个 it：renders / fetches / displays。
 */
describe('TokenMonitorPanel (B-4-P2-T6)', () => {
  it('renders 3 cards with window labels (1h/24h/7d)', () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        window: '1h',
        total_tokens: 100,
        prompt_tokens: 60,
        completion_tokens: 40,
        since: '2026-06-08T10:00:00Z',
        by_agent: [],
      }),
    } as Response)

    render(<TokenMonitorPanel open onOpenChange={() => {}} />)
    expect(screen.getByTestId('usage-card-1h')).toBeInTheDocument()
    expect(screen.getByTestId('usage-card-24h')).toBeInTheDocument()
    expect(screen.getByTestId('usage-card-7d')).toBeInTheDocument()
  })

  it('fetches /api/usage/global?window=1h|24h|7d on open', async () => {
    const fetchSpy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({
        window: '1h',
        total_tokens: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
        since: '2026-06-08T10:00:00Z',
        by_agent: [],
      }),
    } as Response)

    render(<TokenMonitorPanel open onOpenChange={() => {}} />)

    await waitFor(() => {
      const urls = fetchSpy.mock.calls.map((c) => String(c[0]))
      expect(urls).toContain('/api/usage/global?window=1h')
      expect(urls).toContain('/api/usage/global?window=24h')
      expect(urls).toContain('/api/usage/global?window=7d')
    })
  })

  it('displays total_tokens for each card after fetch resolves', async () => {
    vi.spyOn(global, 'fetch').mockImplementation((url) =>
      Promise.resolve({
        ok: true,
        json: async () => ({
          window: String(url).match(/window=(\w+)/)?.[1] ?? '1h',
          total_tokens: 12345,
          prompt_tokens: 7000,
          completion_tokens: 5345,
          since: '2026-06-08T10:00:00Z',
          by_agent: [],
        }),
      } as Response),
    )

    render(<TokenMonitorPanel open onOpenChange={() => {}} />)
    await waitFor(() => {
      const cards = ['1h', '24h', '7d'].map((w) =>
        screen.getByTestId(`usage-card-${w}`),
      )
      for (const c of cards) {
        expect(c.textContent).toContain('12345')
      }
    })
  })
})
