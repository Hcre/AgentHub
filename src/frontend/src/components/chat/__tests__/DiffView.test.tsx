import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { MessageBubble } from '../MessageBubble'
import { DiffView } from '../DiffView'
import { extractDiffFences, parseUnifiedDiff } from '../diffParse'
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

describe('parseUnifiedDiff', () => {
  it('extracts added lines into newValue, removed into oldValue, context into both', () => {
    const { oldValue, newValue, hasChanges } = parseUnifiedDiff(
      ' line 1\n-old line\n+new line\n line 2',
    )
    expect(oldValue).toBe('line 1\nold line\nline 2')
    expect(newValue).toBe('line 1\nnew line\nline 2')
    expect(hasChanges).toBe(true)
  })

  it('skips git header lines (--- / +++ / @@ / No newline)', () => {
    const { oldValue, newValue } = parseUnifiedDiff(
      '--- a/foo.ts\n+++ b/foo.ts\n@@ -1,1 +1,1 @@\n-a\n+b\n\\ No newline at end of file',
    )
    expect(oldValue).toBe('a')
    expect(newValue).toBe('b')
  })

  it('returns hasChanges=false when no + or - line is present', () => {
    const { hasChanges } = parseUnifiedDiff(' line 1\n line 2')
    expect(hasChanges).toBe(false)
  })
})

describe('extractDiffFences', () => {
  it('captures content between ```diff and closing ```', () => {
    const text = 'intro\n```diff\n+added\n-removed\n```\noutro'
    const out = extractDiffFences(text)
    expect(out.hasDiffFence).toBe(true)
    expect(out.before).toBe('intro\n')
    expect(out.after).toBe('\noutro')
    expect(out.diffBody).toBe('+added\n-removed\n')
  })

  it('returns hasDiffFence=false for text without ```diff fence', () => {
    const out = extractDiffFences('普通 markdown，无围栏')
    expect(out.hasDiffFence).toBe(false)
    expect(out.before).toBe('普通 markdown，无围栏')
  })

  it('does NOT match ```ts / ```js fences (only ```diff)', () => {
    const out = extractDiffFences('```ts\nconst x = 1\n```')
    expect(out.hasDiffFence).toBe(false)
  })

  it('merges multiple ```diff fences into one body', () => {
    const text = '```diff\n+a\n```\nmiddle\n```diff\n-b\n```'
    const out = extractDiffFences(text)
    expect(out.hasDiffFence).toBe(true)
    expect(out.diffBody).toBe('+a\n\n-b\n')
    expect(out.before).toBe('')
    expect(out.after).toBe('')
  })
})

describe('MessageBubble DiffView integration (P0-2)', () => {
  it('renders DiffView (and its 全屏 button) when msg.text contains ```diff fence', () => {
    const msg: ChatMessage = {
      id: 'd1',
      from: 'agent',
      time: '12:34',
      text: '我改了一处：\n```diff\n+added line\n-removed line\n context line\n```\n收工。',
    }
    render(<MessageBubble msg={msg} agent={agent} user={user} />)

    // DiffView 渲染了：data-testid 是它独有的标记
    const diffRoot = screen.getByTestId('diff-view')
    expect(diffRoot).toBeInTheDocument()
    expect(diffRoot.getAttribute('data-has-changes')).toBe('true')

    // 「全屏」按钮存在 —— 这是 DiffView 独有的按钮（WebPreviewCard 是「展开/收起」），
    // 因此可作为「DiffView 被调用」的可靠信号。
    const fullscreenBtn = screen.getByRole('button', { name: /全屏/ })
    expect(fullscreenBtn).toBeInTheDocument()

    // 围栏前/后的 markdown 段落照常渲染（"我改了一处：" 和 "收工。"）
    expect(screen.getByText(/我改了一处/)).toBeInTheDocument()
    expect(screen.getByText(/收工/)).toBeInTheDocument()

    // 原始围栏标记（```diff / ``` ）不再以纯文本出现 —— 已被拆出走 DiffView
    expect(screen.queryByText('```diff')).not.toBeInTheDocument()
  })

  it('opens Dialog when 全屏 button is clicked (fullscreen overlay mounted)', () => {
    const msg: ChatMessage = {
      id: 'd2',
      from: 'agent',
      time: '12:35',
      text: '```diff\n+only one\n-old one\n```',
    }
    render(<MessageBubble msg={msg} agent={agent} user={user} />)
    fireEvent.click(screen.getByRole('button', { name: /全屏/ }))

    // Dialog 打开后会有第二个「全屏」按钮 + 「关闭」按钮
    // （内联卡片还在 DOM 里，Dialog 内容也在）
    expect(screen.getByRole('button', { name: /关闭全屏/ })).toBeInTheDocument()
  })

  it('does NOT render DiffView for non-diff fences (```ts stays as raw code block)', () => {
    const msg: ChatMessage = {
      id: 'd3',
      from: 'agent',
      time: '12:36',
      text: '```ts\nconst x = 1\n```',
    }
    render(<MessageBubble msg={msg} agent={agent} user={user} />)
    // 无 diff 围栏 → DiffView 不应被渲染
    expect(screen.queryByTestId('diff-view')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /全屏/ })).not.toBeInTheDocument()
  })

  it('does NOT render DiffView for user messages (only agent)', () => {
    const msg: ChatMessage = {
      id: 'd4',
      from: 'user',
      time: '12:37',
      text: '```diff\n+only one\n```',
    }
    render(<MessageBubble msg={msg} agent={agent} user={user} />)
    expect(screen.queryByTestId('diff-view')).not.toBeInTheDocument()
  })
})

describe('DiffView component (standalone)', () => {
  it('renders empty-diff placeholder when unifiedDiff is empty/whitespace', () => {
    render(<DiffView unifiedDiff="" />)
    expect(screen.getByText(/\(empty diff\)/)).toBeInTheDocument()
    expect(screen.queryByTestId('diff-view')).not.toBeInTheDocument()
  })

  it('renders data-testid root + 全屏 button for a real diff', () => {
    render(<DiffView unifiedDiff="+a\n-b" oldTitle="a.ts" newTitle="b.ts" />)
    expect(screen.getByTestId('diff-view')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /全屏/ })).toBeInTheDocument()
  })
})
