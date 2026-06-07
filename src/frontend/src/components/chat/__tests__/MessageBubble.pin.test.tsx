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
// 对齐后端真实路由（src/backend/app/api/routers/sessions.py:91-99）：
//   POST   /api/messages/{message_id}/pin?session_id={session_id}
//   DELETE /api/messages/{message_id}/pin?session_id={session_id}
// 注意 session_id 在 query，不在 path。MSG_ID 也是 message_id（直接挂在 msg.id 上）。
const EXPECTED_URL = `/api/messages/${baseMsg.id}/pin?session_id=${SESSION_ID}`
const URL_CONTAINS_MSG_ID = `/api/messages/${baseMsg.id}/pin`

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

  it('click on unpinned Pin calls POST /api/messages/{mid}/pin?session_id={sid} and flips state optimistically', async () => {
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

    // fetch 被以 POST 调到了正确的 URL（对齐后端真实路由：session_id 在 query）
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

  /**
   * Schema 钉死：URL 模板必须**始终**走「path = /api/messages/{id}/pin」+ 「query = session_id」
   * 这个 schema，跟后端 sessions.py:91-99 的实际定义严格对应。verifier 上轮
   * 抓到的 bug 就是前端 URL drift（path 写成 /sessions/{sid}/messages/{mid}），
   * 跟后端路由不对齐；本 test 把 schema 钉在测试里，下次再 drift 立刻挂。
   */
  it('URL template matches backend sessions.py:91-99 schema (path + query, no drift)', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 204 }))
    global.fetch = fetchMock as unknown as typeof fetch

    render(<MessageBubble msg={baseMsg} agent={agent} user={user} sessionId={SESSION_ID} />)
    fireEvent.click(screen.getByTestId('pin-btn'))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit]
    // path 必须是 /api/messages/{msg_id}/pin
    expect(url).toContain(URL_CONTAINS_MSG_ID)
    // 完整 URL 形式：path + ?session_id=...，session_id 必须在 query
    const u = new URL(url, 'http://localhost')
    expect(u.pathname).toBe(`/api/messages/${baseMsg.id}/pin`)
    expect(u.searchParams.get('session_id')).toBe(SESSION_ID)
    // 反向断言：绝不能写成 path 里有 /sessions/{sid}/messages/...（即 spec 笔误版）
    expect(url).not.toMatch(/\/sessions\/[^/]+\/messages\//)
  })
})
