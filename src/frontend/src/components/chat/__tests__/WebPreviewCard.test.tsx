import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { WebPreviewCard } from '../WebPreviewCard'
import { collectUrls, extractUrls } from '../webPreviewUrl'
import { MessageBubble } from '../MessageBubble'
import type { Agent, UserInfo, ChatMessage } from '../../../types'

afterEach(cleanup)

const agent: Agent = {
  id: 'editor',
  name: '编辑',
  role: 'Content editor',
  color: 'brand',
  online: true,
}

const user: UserInfo = { handle: 't', name: 't', initial: 'T' }

describe('WebPreviewCard', () => {
  it('renders collapsed: shows title/url + 展开 button, hides iframe', () => {
    render(<WebPreviewCard url="https://example.com/docs" title="Example Docs" />)
    // 标题与 URL 都展示
    expect(screen.getByText('Example Docs')).toBeInTheDocument()
    expect(screen.getByText('https://example.com/docs')).toBeInTheDocument()
    // 折叠态不挂 iframe
    expect(screen.queryByTitle('Example Docs')).not.toBeInTheDocument()
    // 展开按钮存在
    expect(screen.getByRole('button', { name: /展开/ })).toBeInTheDocument()
  })

  it('uses url host as fallback title when title not provided', () => {
    render(<WebPreviewCard url="https://news.ycombinator.com/item?id=1" />)
    expect(screen.getByText('news.ycombinator.com')).toBeInTheDocument()
  })

  it('expands to mount iframe when 展开 clicked, then 收起 removes it', () => {
    render(<WebPreviewCard url="https://example.com" title="Example" />)
    const btn = screen.getByRole('button', { name: /展开/ })
    fireEvent.click(btn)
    // 展开后 iframe 出现
    const iframe = screen.getByTitle('Example')
    expect(iframe).toBeInTheDocument()
    expect(iframe.getAttribute('src')).toBe('https://example.com')
    expect(iframe.getAttribute('sandbox')).toBe('allow-scripts allow-same-origin')
    // 按钮文案变成「收起」
    expect(screen.getByRole('button', { name: /收起/ })).toBeInTheDocument()
    // 再点收起，iframe 卸载
    fireEvent.click(screen.getByRole('button', { name: /收起/ }))
    expect(screen.queryByTitle('Example')).not.toBeInTheDocument()
  })
})

describe('extractUrls (URL regex fallback)', () => {
  it('extracts http(s) URLs from free text', () => {
    expect(extractUrls('看 https://example.com/a 这篇')).toEqual(['https://example.com/a'])
  })

  it('extracts multiple URLs and de-dupes by insertion order', () => {
    const txt = 'first https://a.com/x then https://b.com/y and again https://a.com/x'
    expect(extractUrls(txt)).toEqual(['https://a.com/x', 'https://b.com/y'])
  })

  it('ignores non-http schemes', () => {
    expect(extractUrls('not a url ftp://x.com and file:///etc/host')).toEqual([])
  })

  it('returns [] for empty / null-ish text', () => {
    expect(extractUrls('')).toEqual([])
  })
})

describe('collectUrls (msg.urls + text fallback merge)', () => {
  it('declared urls win + text-extracted urls appended (de-duped)', () => {
    const out = collectUrls(
      'see https://b.com and https://c.com',
      ['https://a.com', 'https://b.com'],
    )
    expect(out).toEqual(['https://a.com', 'https://b.com', 'https://c.com'])
  })

  it('works with declared = undefined', () => {
    const out = collectUrls('hi https://x.com')
    expect(out).toEqual(['https://x.com'])
  })
})

describe('MessageBubble URL integration', () => {
  it('renders WebPreviewCard for urls declared in msg.urls (agent only)', () => {
    const msg: ChatMessage = {
      id: 'a1',
      from: 'agent',
      time: '12:00',
      text: '请看这个',
      urls: ['https://example.com/a'],
    }
    render(<MessageBubble msg={msg} agent={agent} user={user} />)
    expect(screen.getByText('https://example.com/a')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /展开/ })).toBeInTheDocument()
  })

  it('falls back to URL regex when msg.urls is absent', () => {
    const msg: ChatMessage = {
      id: 'a2',
      from: 'agent',
      time: '12:01',
      text: '推荐一篇 https://news.ycombinator.com/item?id=42 给你',
    }
    render(<MessageBubble msg={msg} agent={agent} user={user} />)
    expect(screen.getByText('news.ycombinator.com')).toBeInTheDocument()
  })

  it('does NOT render WebPreviewCard for user messages (only agent)', () => {
    const msg: ChatMessage = {
      id: 'u1',
      from: 'user',
      time: '12:02',
      text: '我贴一个 https://example.com/u',
    }
    render(<MessageBubble msg={msg} agent={agent} user={user} />)
    // 用户的链接仍然走 markdown 渲染（text 里有它）但不应出现「展开」按钮
    expect(screen.queryByRole('button', { name: /展开/ })).not.toBeInTheDocument()
  })
})
