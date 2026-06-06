import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MessageBubble } from '../MessageBubble'
import type { Agent, ChatMessage, UserInfo } from '../../../types'

afterEach(cleanup)

const agent: Agent = {
  id: 'editor',
  name: '编辑',
  role: 'Content editor',
  color: 'brand',
  online: true,
}

const user: UserInfo = { handle: 't', name: 't', initial: 'T' }

const baseMsg: ChatMessage = {
  id: 'msg-001',
  from: 'agent',
  time: '12:00',
  text: '一段普通消息文本',
}

const SESSION_ID = 'sess-abc-123'
const EXPECTED_URL = `/api/sessions/${SESSION_ID}/messages/${baseMsg.id}/pin`

describe('MessageBubble Pin button (P0-4)', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('renders Pin button with outline state when msg.pinned is undefined/false', () => {
    render(<MessageBubble msg={baseMsg} agent={agent} user={user} sessionId={SESSION_ID} />)
    const btn = screen.getByTestId('pin-btn')
    expect(btn).toBeInTheDocument()
    expect(btn.getAttribute('data-pinned')).toBe('false')
    expect(btn.getAttribute('aria-pressed')).toBe('false')
    expect(btn.getAttribute('aria-label')).toBe('置顶消息')
  })

  it('renders Pin button with filled/brand state when msg.pinned is true', () => {
    const pinnedMsg: ChatMessage = { ...baseMsg, pinned: true }
    render(<MessageBubble msg={pinnedMsg} agent={agent} user={user} sessionId={SESSION_ID} />)
    const btn = screen.getByTestId('pin-btn')
    expect(btn.getAttribute('data-pinned')).toBe('true')
    expect(btn.getAttribute('aria-pressed')).toBe('true')
    expect(btn.getAttribute('aria-label')).toBe('取消置顶')
    // 已 pinned 时 className 走 brand 主色分支
    expect(btn.className).toContain('text-brand')
  })

  it('click on unpinned Pin calls POST /api/sessions/{sid}/messages/{mid}/pin and flips state optimistically', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 204,
    }))
    global.fetch = fetchMock as unknown as typeof fetch

    render(<MessageBubble msg={baseMsg} agent={agent} user={user} sessionId={SESSION_ID} />)
    const btn = screen.getByTestId('pin-btn')

    // 初始未 pinned
    expect(btn.getAttribute('data-pinned')).toBe('false')

    fireEvent.click(btn)

    // 乐观更新：状态立刻翻
    await waitFor(() => {
      expect(btn.getAttribute('data-pinned')).toBe('true')
    })

    // fetch 被以 POST 调到了正确的 URL
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(EXPECTED_URL)
    expect(init.method).toBe('POST')
  })

  it('click on pinned Pin calls DELETE same URL and flips back to unpinned', async () => {
    const pinnedMsg: ChatMessage = { ...baseMsg, pinned: true }
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 204,
    }))
    global.fetch = fetchMock as unknown as typeof fetch

    render(<MessageBubble msg={pinnedMsg} agent={agent} user={user} sessionId={SESSION_ID} />)
    const btn = screen.getByTestId('pin-btn')

    // 初始已 pinned
    expect(btn.getAttribute('data-pinned')).toBe('true')

    fireEvent.click(btn)

    await waitFor(() => {
      expect(btn.getAttribute('data-pinned')).toBe('false')
    })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(EXPECTED_URL)
    expect(init.method).toBe('DELETE')
  })

  it('rolls back optimistic state and shows error when API returns non-2xx', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: false,
      status: 500,
    }))
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    global.fetch = fetchMock as unknown as typeof fetch

    render(<MessageBubble msg={baseMsg} agent={agent} user={user} sessionId={SESSION_ID} />)
    const btn = screen.getByTestId('pin-btn')

    expect(btn.getAttribute('data-pinned')).toBe('false')

    fireEvent.click(btn)

    // 乐观更新：先翻成 true
    await waitFor(() => {
      expect(btn.getAttribute('data-pinned')).toBe('true')
    })

    // 失败 → 回滚到 false
    await waitFor(() => {
      expect(btn.getAttribute('data-pinned')).toBe('false')
    })

    // 错误提示出现
    expect(screen.getByTestId('pin-error')).toBeInTheDocument()
    expect(consoleError).toHaveBeenCalled()

    consoleError.mockRestore()
  })

  it('without sessionId, click flips state but does NOT call fetch (degraded mock mode)', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 204 }))
    global.fetch = fetchMock as unknown as typeof fetch

    render(<MessageBubble msg={baseMsg} agent={agent} user={user} />)
    const btn = screen.getByTestId('pin-btn')

    expect(btn.getAttribute('data-pinned')).toBe('false')

    fireEvent.click(btn)

    await waitFor(() => {
      expect(btn.getAttribute('data-pinned')).toBe('true')
    })

    // 不发请求
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
