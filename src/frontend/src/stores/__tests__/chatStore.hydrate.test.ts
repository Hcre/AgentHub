import { describe, it, expect, beforeEach } from 'vitest'
import { useChatStore, convKey } from '../chatStore'
import type { Session } from '../../types'

function mkSession(over: Partial<Session>): Session {
  return {
    id: 'sess-1',
    type: 'private',
    title: '',
    group_id: null,
    agent_id: 'agent-1',
    workspace_path: '',
    pinned: false,
    created_at: '2026-06-10T00:00:00Z',
    ...over,
  }
}

describe('chatStore.hydrateFromSessions', () => {
  beforeEach(() => {
    useChatStore.setState({ conversations: {}, sessionIds: {} })
  })

  it('回灌 private session → 建会话 + 写 sessionIds（用 session.id 当 conv id）', () => {
    useChatStore.getState().hydrateFromSessions([
      mkSession({ id: 'sess-a', agent_id: 'agent-1', title: '登录页讨论', pinned: true }),
    ])
    const { conversations, sessionIds } = useChatStore.getState()
    expect(conversations['agent-1']).toHaveLength(1)
    expect(conversations['agent-1'][0]).toMatchObject({ id: 'sess-a', name: '登录页讨论', pinned: true })
    // sessionIds 让 ChatView 能续聊真实后端 session
    expect(sessionIds[convKey('agent-1', 'sess-a')]).toBe('sess-a')
  })

  it('幂等：重复 hydrate 不重复建会话，只回填后端真值', () => {
    const s = mkSession({ id: 'sess-a', agent_id: 'agent-1', title: '初版' })
    useChatStore.getState().hydrateFromSessions([s])
    useChatStore.getState().hydrateFromSessions([{ ...s, title: '改名后', pinned: true }])
    const conv = useChatStore.getState().conversations['agent-1']
    expect(conv).toHaveLength(1)
    expect(conv[0]).toMatchObject({ name: '改名后', pinned: true })
  })

  it('保留本地 archived 状态（hydrate 不覆盖）', () => {
    useChatStore.setState({
      conversations: { 'agent-1': [{ id: 'sess-a', name: '旧', subtitle: '', archived: true }] },
      sessionIds: {},
    })
    useChatStore.getState().hydrateFromSessions([mkSession({ id: 'sess-a', agent_id: 'agent-1', title: '新名' })])
    const conv = useChatStore.getState().conversations['agent-1'][0]
    expect(conv.archived).toBe(true) // 本地归档保留
    expect(conv.name).toBe('新名') // 后端真值回填
  })

  it('跳过群聊 / 无 agent_id 的 session', () => {
    useChatStore.getState().hydrateFromSessions([
      mkSession({ id: 'g1', type: 'group', agent_id: null, group_id: 'grp-1' }),
      mkSession({ id: 'p1', type: 'private', agent_id: null }),
    ])
    expect(Object.keys(useChatStore.getState().conversations)).toHaveLength(0)
  })

  it('无标题时回退到「私聊」默认名', () => {
    useChatStore.getState().hydrateFromSessions([mkSession({ id: 'sess-a', agent_id: 'agent-1', title: '' })])
    expect(useChatStore.getState().conversations['agent-1'][0].name).toBe('私聊')
  })
})
