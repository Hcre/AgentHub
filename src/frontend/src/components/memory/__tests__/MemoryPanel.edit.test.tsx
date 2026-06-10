import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryPanel } from '../MemoryPanel'
import type { ApiMemory } from '../../../types'

// 验证 STATUS 缺口 #11：MemoryPanel 编辑 → memoriesApi.update (PATCH) 真实调用。
const update = vi.fn()
const list = vi.fn()
const stats = vi.fn()
const remove = vi.fn()

vi.mock('../../../api/memories', () => ({
  memoriesApi: {
    list: (...a: unknown[]) => list(...a),
    stats: (...a: unknown[]) => stats(...a),
    create: vi.fn(),
    update: (...a: unknown[]) => update(...a),
    remove: (...a: unknown[]) => remove(...a),
    get: vi.fn(),
  },
}))

const MEM: ApiMemory = {
  id: 'm1',
  agent_id: 'a1',
  group_id: null,
  user_id: 'u1',
  scope: 'agent',
  name: '索引优化偏好',
  description: '描述',
  memory_type: 'preferences',
  content: '原始内容',
  source: 'manual',
  pinned: false,
  hits: 3,
  metadata: {},
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

afterEach(cleanup)
beforeEach(() => {
  update.mockReset()
  list.mockReset()
  stats.mockReset()
  list.mockResolvedValue([MEM])
  stats.mockResolvedValue({ total: 1, by_type: { preferences: 1 } })
})

describe('MemoryPanel 编辑（缺口 #11）', () => {
  it('点编辑 → 改内容 → 保存 调用 memoriesApi.update(PATCH)', async () => {
    update.mockResolvedValue({ ...MEM, content: '改后的内容' })
    render(<MemoryPanel agentId="a1" agentName="索引专家" />)

    await waitFor(() => expect(screen.getByText('原始内容')).toBeInTheDocument())

    // hover actions 用 title 定位「编辑」按钮
    fireEvent.click(screen.getByTitle('编辑'))
    const textarea = screen.getByDisplayValue('原始内容')
    fireEvent.change(textarea, { target: { value: '改后的内容' } })
    fireEvent.click(screen.getByText('保存'))

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1))
    expect(update).toHaveBeenCalledWith('a1', 'm1', { content: '改后的内容' })
  })
})
