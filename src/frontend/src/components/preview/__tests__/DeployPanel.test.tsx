import { describe, it, expect, afterEach, beforeEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { DeployPanel } from '../DeployPanel'

const list = vi.fn()
const start = vi.fn()
const remove = vi.fn()

vi.mock('../../../api/deploy', () => ({
  deployApi: {
    list: (...a: unknown[]) => list(...a),
    start: (...a: unknown[]) => start(...a),
    remove: (...a: unknown[]) => remove(...a),
    get: vi.fn(),
  },
}))

const SESSION = '11111111-1111-1111-1111-111111111111'

afterEach(cleanup)
beforeEach(() => {
  list.mockReset()
  start.mockReset()
  remove.mockReset()
  list.mockResolvedValue([])
})

describe('DeployPanel — 新建部署触发', () => {
  it('无有效 session 时显示选择会话提示，不渲染列表', () => {
    render(<DeployPanel sessionId={null} />)
    expect(screen.getByText(/请先选择一个聊天会话/)).toBeInTheDocument()
  })

  it('点「新建」打开表单，提交后调用 deployApi.start（static_site + index.html）', async () => {
    start.mockResolvedValue({ id: 'd1', status: 'ready' })
    render(<DeployPanel sessionId={SESSION} />)

    await waitFor(() => expect(list).toHaveBeenCalled())

    fireEvent.click(screen.getByTestId('deploy-new'))
    expect(screen.getByTestId('deploy-html-input')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('deploy-submit'))

    await waitFor(() => expect(start).toHaveBeenCalledTimes(1))
    const arg = start.mock.calls[0][0]
    expect(arg.session_id).toBe(SESSION)
    expect(arg.target).toBe('static_site')
    expect(arg.entry_file).toBe('index.html')
    expect(arg.files['index.html']).toContain('<!doctype html>')
    // 提交成功后重新拉取列表
    await waitFor(() => expect(list).toHaveBeenCalledTimes(2))
  })

  it('切换到「源码打包」后 entry_file 为 undefined', async () => {
    start.mockResolvedValue({ id: 'd2', status: 'ready' })
    render(<DeployPanel sessionId={SESSION} />)
    await waitFor(() => expect(list).toHaveBeenCalled())

    fireEvent.click(screen.getByTestId('deploy-new'))
    fireEvent.click(screen.getByLabelText('源码打包'))
    fireEvent.click(screen.getByTestId('deploy-submit'))

    await waitFor(() => expect(start).toHaveBeenCalledTimes(1))
    const arg = start.mock.calls[0][0]
    expect(arg.target).toBe('package')
    expect(arg.entry_file).toBeUndefined()
  })
})
