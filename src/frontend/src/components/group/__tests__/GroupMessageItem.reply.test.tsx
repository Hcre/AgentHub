import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { GroupMessageItem } from '../GroupMessageItem'
import type { GroupMessage, ReplyRef } from '../../../types'

afterEach(cleanup)

const baseMsg: GroupMessage = {
  id: 'gmsg-1',
  from: 'agent',
  who: 'claude',
  time: '12:00',
  text: '一段群聊消息',
}

const sampleRef: ReplyRef = {
  id: 'gmsg-99',
  author: '协调者',
  snippet: '被引用的内容',
}

describe('GroupMessageItem reply/quote (P1-1 group extension)', () => {
  it('renders a reply button on every message', () => {
    render(<GroupMessageItem msg={baseMsg} sessionId="sess-1" />)
    const btn = screen.getByTestId('group-reply-btn')
    expect(btn).toBeInTheDocument()
    expect(btn.getAttribute('aria-label')).toBe('回复消息')
  })

  it('clicking reply button invokes onReply with the original msg', () => {
    const onReply = vi.fn<(m: GroupMessage) => void>()
    render(
      <GroupMessageItem
        msg={baseMsg}
        sessionId="sess-1"
        onReply={onReply}
      />,
    )
    fireEvent.click(screen.getByTestId('group-reply-btn'))
    expect(onReply).toHaveBeenCalledTimes(1)
    expect(onReply.mock.calls[0]?.[0]).toEqual(baseMsg)
  })

  it('renders a quote bubble when msg.replyTo is set, showing author + snippet', () => {
    const msg: GroupMessage = {
      ...baseMsg,
      text: '我的回复',
      replyTo: sampleRef,
    }
    render(<GroupMessageItem msg={msg} sessionId="sess-1" />)
    const quote = screen.getByTestId('group-reply-quote')
    expect(quote).toBeInTheDocument()
    expect(quote.textContent).toContain('协调者')
    expect(quote.textContent).toContain('被引用的内容')
  })

  it('does NOT render a quote bubble when msg.replyTo is absent', () => {
    render(<GroupMessageItem msg={baseMsg} sessionId="sess-1" />)
    expect(screen.queryByTestId('group-reply-quote')).not.toBeInTheDocument()
  })
})
