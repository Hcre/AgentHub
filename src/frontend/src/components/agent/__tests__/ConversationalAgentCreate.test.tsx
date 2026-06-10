import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { ConversationalAgentCreate } from '../ConversationalAgentCreate'

const draftFromChat = vi.fn()
const create = vi.fn()
const loadAgents = vi.fn()

vi.mock('../../../api/agents', () => ({
  agentsApi: {
    draftFromChat: (...a: unknown[]) => draftFromChat(...a),
    create: (...a: unknown[]) => create(...a),
  },
}))
vi.mock('../../../stores/agentStore', () => ({
  useAgentStore: (sel: (s: unknown) => unknown) => sel({ loadAgents }),
}))

afterEach(cleanup)
beforeEach(() => {
  draftFromChat.mockReset()
  create.mockReset()
  loadAgents.mockReset()
})

const DRAFT = {
  name: '前端专家',
  role: 'React 性能优化',
  avatar: '🎨',
  system_prompt: '你专注前端性能。',
  capability_tags: ['React', '性能'],
}

describe('ConversationalAgentCreate', () => {
  it('open=false 不渲染', () => {
    render(<ConversationalAgentCreate open={false} onClose={() => {}} />)
    expect(screen.queryByTestId('conv-agent-create')).not.toBeInTheDocument()
  })

  it('生成按钮在描述为空时禁用', () => {
    render(<ConversationalAgentCreate open onClose={() => {}} />)
    expect(screen.getByTestId('conv-generate-btn')).toBeDisabled()
  })

  it('描述→生成→预览草稿→创建 全流程', async () => {
    draftFromChat.mockResolvedValue(DRAFT)
    create.mockResolvedValue({ id: 'a1' })
    loadAgents.mockResolvedValue(undefined)
    const onClose = vi.fn()
    render(<ConversationalAgentCreate open onClose={onClose} />)

    fireEvent.change(screen.getByPlaceholderText(/React 性能优化/), {
      target: { value: '一个会 React 性能优化的前端专家' },
    })
    fireEvent.click(screen.getByTestId('conv-generate-btn'))

    await waitFor(() => expect(screen.getByTestId('conv-draft-preview')).toBeInTheDocument())
    expect(draftFromChat).toHaveBeenCalledWith('一个会 React 性能优化的前端专家')
    expect(screen.getByDisplayValue('前端专家')).toBeInTheDocument()
    expect(screen.getByDisplayValue('React 性能优化')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('conv-create-btn'))
    await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
    expect(create).toHaveBeenCalledWith(
      expect.objectContaining({ name: '前端专家', avatar: '🎨', agent_system: 'mock' }),
    )
    await waitFor(() => expect(onClose).toHaveBeenCalled())
  })

  it('生成失败显示错误', async () => {
    draftFromChat.mockRejectedValue(new Error('LLM 不可用'))
    render(<ConversationalAgentCreate open onClose={() => {}} />)
    fireEvent.change(screen.getByPlaceholderText(/React 性能优化/), { target: { value: 'x' } })
    fireEvent.click(screen.getByTestId('conv-generate-btn'))
    await waitFor(() => expect(screen.getByTestId('conv-error')).toHaveTextContent('LLM 不可用'))
  })
})
