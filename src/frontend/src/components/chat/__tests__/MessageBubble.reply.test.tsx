import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
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

describe('MessageBubble reply/quote button (P1-1)', () => {
  it('renders a reply button on every message (hover-triggered via CSS, but always in DOM)', () => {
    render(<MessageBubble msg={baseMsg} agent={agent} user={user} sessionId="sid-1" />)
    // data-testid "reply-btn" 必须在 DOM（CSS 控制可见性）
    const btn = screen.getByTestId('reply-btn')
    expect(btn).toBeInTheDocument()
    expect(btn.getAttribute('aria-label')).toBe('回复消息')
  })

  it('clicking the reply button invokes onReply callback with the original msg', () => {
    const onReply = vi.fn<(m: ChatMessage) => void>()
    render(
      <MessageBubble
        msg={baseMsg}
        agent={agent}
        user={user}
        sessionId="sid-1"
        onReply={onReply}
      />,
    )
    fireEvent.click(screen.getByTestId('reply-btn'))
    expect(onReply).toHaveBeenCalledTimes(1)
    expect(onReply.mock.calls[0]?.[0]).toEqual(baseMsg)
  })

  it('renders a quote bubble (top-corner) when msg.replyTo is set, showing author + snippet', () => {
    const msg: ChatMessage = {
      ...baseMsg,
      text: '这是我的回复',
      replyTo: {
        id: 'msg-099',
        author: '编辑',
        snippet: '原消息内容摘录...',
      },
    }
    render(<MessageBubble msg={msg} agent={agent} user={user} sessionId="sid-1" />)
    const quote = screen.getByTestId('reply-quote')
    expect(quote).toBeInTheDocument()
    expect(quote.textContent).toContain('编辑')
    expect(quote.textContent).toContain('原消息内容摘录...')
  })

  it('does NOT render a quote bubble when msg.replyTo is absent', () => {
    render(<MessageBubble msg={baseMsg} agent={agent} user={user} sessionId="sid-1" />)
    expect(screen.queryByTestId('reply-quote')).not.toBeInTheDocument()
  })

  it('snippet is truncated to 60 chars to keep quote bubble compact', () => {
    const long = 'a'.repeat(200)
    const msg: ChatMessage = {
      ...baseMsg,
      replyTo: { id: 'x', author: 'X', snippet: long },
    }
    render(<MessageBubble msg={msg} agent={agent} user={user} sessionId="sid-1" />)
    const quote = screen.getByTestId('reply-quote')
    // 不允许出现 200 个 a，只取前 60（不含省略号或含省略号均可，断言「不超过 70 字符」容错）
    const aCount = (quote.textContent?.match(/a/g) ?? []).length
    expect(aCount).toBeGreaterThan(0)
    expect(aCount).toBeLessThanOrEqual(70)
  })
})
