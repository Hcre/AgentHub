import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { GroupMessageItem } from '../GroupMessageItem'
import type { GroupMessage } from '../../../types'

afterEach(cleanup)

const SESSION_ID = 'group-sess-xyz'
const baseMsg: GroupMessage = {
  id: 'gmsg-001',
  from: 'agent',
  who: 'claude',
  time: '12:00',
  text: '一段普通消息',
}

const URL_CONTAINS_MSG_ID = `/api/messages/${baseMsg.id}/pin`

describe('GroupMessageItem Pin button (P0-4 group extension)', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('renders Pin button with outline state when msg.pinned is undefined', () => {
    render(<GroupMessageItem msg={baseMsg} sessionId={SESSION_ID} />)
    const btn = screen.getByTestId('group-pin-btn')
    expect(btn).toBeInTheDocument()
    expect(btn.getAttribute('data-pinned')).toBe('false')
    expect(btn.getAttribute('aria-pressed')).toBe('false')
    expect(btn.getAttribute('aria-label')).toBe('置顶消息')
  })

  it('renders Pin button with filled/brand state when msg.pinned is true', () => {
    const pinnedMsg: GroupMessage = { ...baseMsg, pinned: true }
    render(<GroupMessageItem msg={pinnedMsg} sessionId={SESSION_ID} />)
    const btn = screen.getByTestId('group-pin-btn')
    expect(btn.getAttribute('data-pinned')).toBe('true')
    expect(btn.getAttribute('aria-pressed')).toBe('true')
    expect(btn.getAttribute('aria-label')).toBe('取消置顶')
    expect(btn.className).toContain('text-brand')
  })

  it('click on unpinned Pin calls POST /api/messages/{mid}/pin?session_id={sid}', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 204 }))
    global.fetch = fetchMock as unknown as typeof fetch

    render(<GroupMessageItem msg={baseMsg} sessionId={SESSION_ID} />)
    const btn = screen.getByTestId('group-pin-btn')

    expect(btn.getAttribute('data-pinned')).toBe('false')
    fireEvent.click(btn)

    await waitFor(() => {
      expect(btn.getAttribute('data-pinned')).toBe('true')
    })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`/api/messages/${baseMsg.id}/pin?session_id=${SESSION_ID}`)
    expect(init.method).toBe('POST')
  })

  it('click on pinned Pin calls DELETE same URL and flips back', async () => {
    const pinnedMsg: GroupMessage = { ...baseMsg, pinned: true }
    const fetchMock = vi.fn(async () => ({ ok: true, status: 204 }))
    global.fetch = fetchMock as unknown as typeof fetch

    render(<GroupMessageItem msg={pinnedMsg} sessionId={SESSION_ID} />)
    fireEvent.click(screen.getByTestId('group-pin-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('group-pin-btn').getAttribute('data-pinned')).toBe('false')
    })
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe(`/api/messages/${baseMsg.id}/pin?session_id=${SESSION_ID}`)
    expect(init.method).toBe('DELETE')
  })

  it('rolls back optimistic state and logs (no inline error) when API returns 5xx', async () => {
    const fetchMock = vi.fn(async () => ({ ok: false, status: 500 }))
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    global.fetch = fetchMock as unknown as typeof fetch

    render(<GroupMessageItem msg={baseMsg} sessionId={SESSION_ID} />)
    fireEvent.click(screen.getByTestId('group-pin-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('group-pin-btn').getAttribute('data-pinned')).toBe('true')
    })
    await waitFor(() => {
      expect(screen.getByTestId('group-pin-btn').getAttribute('data-pinned')).toBe('false')
    })
    // commit 11b4c6c 起：失败只 console.error，不渲染 inline error 元素（对齐 MessageBubble）。
    expect(screen.queryByTestId('group-pin-error')).not.toBeInTheDocument()
    expect(consoleError).toHaveBeenCalled()
    consoleError.mockRestore()
  })

  it('without sessionId, click flips state but does NOT call fetch (degraded mode)', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 204 }))
    global.fetch = fetchMock as unknown as typeof fetch

    render(<GroupMessageItem msg={baseMsg} />)
    fireEvent.click(screen.getByTestId('group-pin-btn'))

    await waitFor(() => {
      expect(screen.getByTestId('group-pin-btn').getAttribute('data-pinned')).toBe('true')
    })
    expect(fetchMock).not.toHaveBeenCalled()
  })

  /**
   * Schema 钉死：URL 必须走「path = /api/messages/{id}/pin」+「query = session_id」，
   * 与 MessageBubble 同一来源（sessions.py:91-99）。前端早期 drift 过（path 写成
   * /sessions/{sid}/messages/{mid}），本 test 阻止再次 drift。
   */
  it('URL template matches backend sessions.py:91-99 schema (path + query, no drift)', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true, status: 204 }))
    global.fetch = fetchMock as unknown as typeof fetch

    render(<GroupMessageItem msg={baseMsg} sessionId={SESSION_ID} />)
    fireEvent.click(screen.getByTestId('group-pin-btn'))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toContain(URL_CONTAINS_MSG_ID)
    const u = new URL(url, 'http://localhost')
    expect(u.pathname).toBe(`/api/messages/${baseMsg.id}/pin`)
    expect(u.searchParams.get('session_id')).toBe(SESSION_ID)
    expect(url).not.toMatch(/\/sessions\/[^/]+\/messages\//)
  })
})
