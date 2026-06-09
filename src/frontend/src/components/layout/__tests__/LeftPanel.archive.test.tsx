/** 会话归档（archive）测试。
 *
 * 契约：
 * 1. 点击归档图标 → store 中 conv.archived=true，且该会话从主私聊列表移除
 * 2. 归档后出现「已归档 (N)」分区，展开后列出归档会话
 * 3. 点击取消归档 → conv.archived=false，会话回到主列表，分区消失（无归档项时）
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, fireEvent, cleanup } from '@testing-library/react'
import { LeftPanel } from '../LeftPanel'
import { useChatStore } from '../../../stores/chatStore'
import { useAgentStore } from '../../../stores/agentStore'
import { useUIStore } from '../../../stores/uiStore'
import { useGroupStore } from '../../../stores/groupStore'

vi.mock('../../../api/sessions', () => ({
  sessionsApi: {
    list: vi.fn().mockResolvedValue([]),
    createPrivate: vi.fn(),
    createGroup: vi.fn(),
    messages: vi.fn().mockResolvedValue([]),
    patch: vi.fn().mockResolvedValue({ id: 'sid' }),
  },
}))

const AGENT_ID = 'a1'
const CONV_ID = 'c1'

function resetStores() {
  useChatStore.setState({
    conversations: { [AGENT_ID]: [{ id: CONV_ID, name: 'Q4 发布稿', subtitle: '' }] },
    sessionIds: {},
    messages: {},
    typing: {},
    stages: {},
    outputs: {},
    connected: true,
    unreadByConv: {},
  })
  useAgentStore.setState({
    agents: [{ id: AGENT_ID, name: '编辑助手', role: 'r', color: 'brand', online: true }],
  })
  useGroupStore.setState({ groups: [], messagesByGroup: {} })
  useUIStore.setState({
    section: 'chat',
    activeAgentId: AGENT_ID,
    activeConversationId: CONV_ID,
    activeGroupId: null,
  })
}

describe('LeftPanel 会话归档', () => {
  beforeEach(() => resetStores())
  afterEach(() => cleanup())

  it('点击归档 → archived=true 且从主列表移除，进入「已归档」分区', () => {
    render(<LeftPanel />)
    fireEvent.click(screen.getByTestId(`archive-conv-${CONV_ID}`))
    const updated = useChatStore.getState().conversations[AGENT_ID]?.find((c) => c.id === CONV_ID)
    expect(updated?.archived).toBe(true)
    // 主列表归档按钮消失，分区计数出现
    expect(screen.queryByTestId(`archive-conv-${CONV_ID}`)).toBeNull()
    expect(screen.getByText('已归档 (1)')).toBeTruthy()
  })

  it('取消归档 → archived=false 且回到主列表', () => {
    useChatStore.setState({
      conversations: { [AGENT_ID]: [{ id: CONV_ID, name: 'Q4 发布稿', subtitle: '', archived: true }] },
    })
    render(<LeftPanel />)
    // 展开已归档分区
    fireEvent.click(screen.getByText('已归档 (1)'))
    fireEvent.click(screen.getByTestId(`unarchive-conv-${CONV_ID}`))
    const updated = useChatStore.getState().conversations[AGENT_ID]?.find((c) => c.id === CONV_ID)
    expect(updated?.archived).toBe(false)
    // 回到主列表（归档按钮重新可用），分区消失
    expect(screen.getByTestId(`archive-conv-${CONV_ID}`)).toBeTruthy()
    expect(screen.queryByText('已归档 (1)')).toBeNull()
  })

  it('归档不影响其他会话', () => {
    useChatStore.setState({
      conversations: {
        [AGENT_ID]: [
          { id: 'c1', name: 'A', subtitle: '' },
          { id: 'c2', name: 'B', subtitle: '' },
        ],
      },
    })
    render(<LeftPanel />)
    fireEvent.click(screen.getByTestId('archive-conv-c1'))
    expect(screen.queryByTestId('archive-conv-c1')).toBeNull()
    expect(screen.getByTestId('archive-conv-c2')).toBeTruthy()
  })
})
