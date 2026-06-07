import { describe, expect, it, vi, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Composer, type ComposerPayload } from '../Composer'
import type { Agent, ReplyRef } from '../../../types'

const testAgent: Agent = {
  id: 'a-1',
  name: 'Coda',
  role: 'Codebase Assistant',
  color: 'brand',
  online: true,
}

const sampleRef: ReplyRef = {
  id: 'msg-099',
  author: '编辑',
  snippet: '这是被引用的消息内容',
}

afterEach(() => {
  // 不污染全局 fetch — Composer 上传链路靠 mock，但 reply 不需要
})

describe('Composer reply mode (P1-1)', () => {
  it('initial state: no reply badge, onSend payload has no replyTo', async () => {
    const onSend = vi.fn<(p: ComposerPayload) => void>()
    render(<Composer agent={testAgent} onSend={onSend} />)

    // 不应有 reply 引文条
    expect(screen.queryByTestId('reply-badge')).not.toBeInTheDocument()

    // 输入 + 发送
    const ta = screen.getByPlaceholderText(/Ask/i) as HTMLTextAreaElement
    const user = userEvent.setup()
    await user.type(ta, '你好')
    fireEvent.keyDown(ta, { key: 'Enter' })

    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1))
    const payload = onSend.mock.calls[0]?.[0]
    expect(payload?.text).toBe('你好')
    expect(payload?.replyTo).toBeUndefined()
  })

  it('setReplyTo() imperatively: reply badge appears, onSend payload carries replyTo', async () => {
    const onSend = vi.fn<(p: ComposerPayload) => void>()
    const ref = { current: null as null | ((r: ReplyRef | null) => void) }
    const ComposerWithRef = () => {
      // 拿到 Composer handle 后调 setReplyTo
      const handle = (
        <Composer
          ref={(h) => {
            if (h && !ref.current) ref.current = h.setReplyTo
          }}
          agent={testAgent}
          onSend={onSend}
        />
      )
      return handle
    }
    render(<ComposerWithRef />)

    // 1. 调 setReplyTo(sampleRef) — 引文条出现
    expect(ref.current).toBeTruthy()
    act(() => ref.current?.(sampleRef))
    expect(screen.getByTestId('reply-badge')).toBeInTheDocument()
    expect(screen.getByTestId('reply-badge').textContent).toContain('编辑')
    expect(screen.getByTestId('reply-badge').textContent).toContain('这是被引用的消息内容')

    // 2. 输入文字 + 发送 → payload.replyTo 携带
    const ta = screen.getByPlaceholderText(/Ask/i) as HTMLTextAreaElement
    const user = userEvent.setup()
    await user.type(ta, '回复正文')
    fireEvent.keyDown(ta, { key: 'Enter' })

    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1))
    const payload = onSend.mock.calls[0]?.[0]
    expect(payload?.text).toBe('回复正文')
    expect(payload?.replyTo).toEqual(sampleRef)

    // 3. 发送后状态清空：badge 消失
    await waitFor(() => expect(screen.queryByTestId('reply-badge')).not.toBeInTheDocument())
  })

  it('clicking the cancel button on reply badge clears reply state and excludes replyTo from next send', async () => {
    const onSend = vi.fn<(p: ComposerPayload) => void>()
    const ref = { current: null as null | ((r: ReplyRef | null) => void) }
    render(
      <Composer
        ref={(h) => {
          if (h && !ref.current) ref.current = h.setReplyTo
        }}
        agent={testAgent}
        onSend={onSend}
      />,
    )

    // 进入 reply mode
    act(() => ref.current?.(sampleRef))
    expect(screen.getByTestId('reply-badge')).toBeInTheDocument()

    // 点取消按钮
    fireEvent.click(screen.getByTestId('reply-cancel'))

    // badge 消失
    await waitFor(() => expect(screen.queryByTestId('reply-badge')).not.toBeInTheDocument())

    // 再次输入 + 发送 → replyTo 不应在 payload 里
    const ta = screen.getByPlaceholderText(/Ask/i) as HTMLTextAreaElement
    const user = userEvent.setup()
    await user.type(ta, '二次发送')
    fireEvent.keyDown(ta, { key: 'Enter' })

    await waitFor(() => expect(onSend).toHaveBeenCalledTimes(1))
    const payload = onSend.mock.calls[0]?.[0]
    expect(payload?.text).toBe('二次发送')
    expect(payload?.replyTo).toBeUndefined()
  })
})

// act 来自 react（避免额外 import 路径差异）
import { act } from 'react'
