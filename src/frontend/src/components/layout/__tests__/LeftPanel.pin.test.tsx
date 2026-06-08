/** t7 B-4-P2-CL01 会话置顶 icon 测试。
 *
 * 契约：
 * 1. 点击 pin 图标 → store 中 conv.pinned 翻转（optimistic 或 pessimistic 都行 — 终态对即可）
 * 2. 点击 pin 图标 → sessionsApi.patch 被调用，body.pinned 传入新值
 * 3. 缺失 sessionId 时不 throw（降级：只本地翻转）
 * 4. 视觉上 pinned=true 的图标显示 brand 色 + opacity-100
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react'
import { LeftPanel } from '../LeftPanel'
import { useChatStore, convKey } from '../../../stores/chatStore'
import { useAgentStore } from '../../../stores/agentStore'
import { useUIStore } from '../../../stores/uiStore'
import { useGroupStore } from '../../../stores/groupStore'
import { sessionsApi } from '../../../api/sessions'

vi.mock('../../../api/sessions', () => ({
  sessionsApi: {
    list: vi.fn().mockResolvedValue([]),
    createPrivate: vi.fn(),
    createGroup: vi.fn(),
    messages: vi.fn().mockResolvedValue([]),
    patch: vi.fn().mockResolvedValue({ id: 'sid', pinned: true }),
  },
}))

const AGENT_ID = 'a1'
const CONV_ID = 'c1'
const SESSION_ID = 's1'

function resetStores() {
  useChatStore.setState({
    conversations: { [AGENT_ID]: [{ id: CONV_ID, name: '技术负责人', subtitle: '' }] },
    sessionIds: { [convKey(AGENT_ID, CONV_ID)]: SESSION_ID },
    messages: {},
    typing: {},
    stages: {},
    outputs: {},
    connected: true,
    unreadByConv: {},
  })
  useAgentStore.setState({
    agents: [{ id: AGENT_ID, name: '技术负责人', role: 'r', color: 'brand', online: true }],
  })
  useGroupStore.setState({ groups: [], messagesByGroup: {} })
  useUIStore.setState({
    section: 'chat',
    activeAgentId: AGENT_ID,
    activeConversationId: CONV_ID,
    activeGroupId: null,
  })
  vi.mocked(sessionsApi.patch).mockClear()
}

describe('LeftPanel pin icon (t7 B-4-P2-CL01)', () => {
  beforeEach(() => resetStores())
  afterEach(() => cleanup())

  it('clicking pin icon flips store pinned and calls sessionsApi.patch with { pinned: true }', async () => {
    render(<LeftPanel />)
    const pin = screen.getByTestId(`pin-conv-${CONV_ID}`)
    expect(pin.getAttribute('data-pinned')).toBe('false')
    await act(async () => {
      fireEvent.click(pin)
    })
    const updated = useChatStore.getState().conversations[AGENT_ID]?.find((c) => c.id === CONV_ID)
    expect(updated?.pinned).toBe(true)
    expect(sessionsApi.patch).toHaveBeenCalledWith(SESSION_ID, { pinned: true })
    expect(pin.getAttribute('data-pinned')).toBe('true')
  })

  it('clicking already-pinned icon toggles back to false and PATCH with { pinned: false }', async () => {
    useChatStore.setState({
      conversations: {
        [AGENT_ID]: [{ id: CONV_ID, name: '技术负责人', subtitle: '', pinned: true }],
      },
    })
    render(<LeftPanel />)
    const pin = screen.getByTestId(`pin-conv-${CONV_ID}`)
    expect(pin.getAttribute('data-pinned')).toBe('true')
    await act(async () => {
      fireEvent.click(pin)
    })
    const updated = useChatStore.getState().conversations[AGENT_ID]?.find((c) => c.id === CONV_ID)
    expect(updated?.pinned).toBe(false)
    expect(sessionsApi.patch).toHaveBeenCalledWith(SESSION_ID, { pinned: false })
  })

  it('missing sessionId does not throw — local toggle still works', async () => {
    useChatStore.setState({ sessionIds: {} })
    render(<LeftPanel />)
    const pin = screen.getByTestId(`pin-conv-${CONV_ID}`)
    await act(async () => {
      fireEvent.click(pin)
    })
    const updated = useChatStore.getState().conversations[AGENT_ID]?.find((c) => c.id === CONV_ID)
    expect(updated?.pinned).toBe(true)
  })
})
