import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
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

/**
 * P0-5 复制代码测试。
 * 主用例：消息文本含 2 段 ```lang\n...\n``` 围栏，点「复制代码」按钮后
 *   - navigator.clipboard.writeText 被以拼接后的围栏内容调用
 *   - 行旁出现「已复制 2 段代码」inline 状态
 * 备选用例：「重新生成」按钮总是 disabled（后端无端点）+ tooltip「即将支持」
 */
describe('MessageBubble Copy / Regenerate (P0-5)', () => {
  const originalClipboard = navigator.clipboard

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    // 还原 navigator.clipboard（避免跨 test 污染）
    Object.defineProperty(navigator, 'clipboard', {
      value: originalClipboard,
      configurable: true,
      writable: true,
    })
  })

  it('click 复制代码 extracts code fences, calls navigator.clipboard.writeText with joined payload, and shows 已复制 N 段代码 status', async () => {
    // mock clipboard
    const writeText = vi.fn(async () => undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
      writable: true,
    })

    const textWithFences = [
      '下面是两段代码示例：',
      '```python',
      "print('hi')",
      '```',
      '第二段：',
      '```js',
      'console.log("world")',
      '```',
      '收尾段落。',
    ].join('\n')

    const msg: ChatMessage = {
      id: 'm-copy',
      from: 'agent',
      time: '12:00',
      text: textWithFences,
      actions: ['复制代码', '重新生成'],
    }

    render(<MessageBubble msg={msg} agent={agent} user={user} />)
    const copyBtn = screen.getByTestId('copy-code-btn')
    expect(copyBtn).toBeInTheDocument()
    expect(copyBtn.textContent).toContain('复制代码')

    fireEvent.click(copyBtn)

    // clipboard.writeText 被调
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1))

    // 抓到的 payload 必须是 2 段围栏内容按 \n\n 拼接（顺序：print('hi') + console.log("world")）
    const payload = writeText.mock.calls[0]?.[0] as string
    expect(payload).toBe(`print('hi')\n\nconsole.log("world")`)

    // inline 状态「已复制 2 段代码」出现
    const status = await screen.findByTestId('copy-status')
    expect(status.textContent).toBe('已复制 2 段代码')
  })

  it('重新生成 button is disabled with title="即将支持" (no backend endpoint yet)', () => {
    const msg: ChatMessage = {
      id: 'm-regen',
      from: 'agent',
      time: '12:00',
      text: 'no fences here',
      actions: ['复制代码', '重新生成'],
    }
    render(<MessageBubble msg={msg} agent={agent} user={user} />)
    const regenBtn = screen.getByTestId('regenerate-btn')
    expect(regenBtn).toBeDisabled()
    expect(regenBtn.getAttribute('title')).toBe('即将支持')
  })
})
