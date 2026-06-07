import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { GroupMessageItem } from '../GroupMessageItem'
import type { GroupMessage } from '../../../types'

afterEach(cleanup)

const msgWithCode: GroupMessage = {
  id: 'gmsg-code-1',
  from: 'agent',
  who: 'claude',
  time: '12:00',
  text: '看这段代码：\n\n```ts\nexport const hello = () => "hi"\n```\n\n搞定。',
}
const msgWithoutCode: GroupMessage = {
  id: 'gmsg-nocode-1',
  from: 'agent',
  who: 'claude',
  time: '12:00',
  text: '没有代码，纯文本消息。',
}

describe('GroupMessageItem Copy code button (P0-5 group extension)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('does not render copy button when text has no code fence', () => {
    render(<GroupMessageItem msg={msgWithoutCode} />)
    expect(screen.queryByTestId('group-copy-code-btn')).toBeNull()
  })

  it('renders copy button when text contains code fence', () => {
    render(<GroupMessageItem msg={msgWithCode} />)
    expect(screen.getByTestId('group-copy-code-btn')).toBeInTheDocument()
  })

  it('click copy code writes fence content to clipboard and shows ok status', async () => {
    const writeText = vi.fn(async () => undefined)
    Object.assign(navigator, { clipboard: { writeText } })

    render(<GroupMessageItem msg={msgWithCode} />)
    fireEvent.click(screen.getByTestId('group-copy-code-btn'))

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1))
    expect(writeText.mock.calls[0][0]).toContain('export const hello')
    await waitFor(() => {
      expect(screen.getByTestId('group-copy-status')).toBeInTheDocument()
    })
    const status = screen.getByTestId('group-copy-status')
    expect(status.textContent).toMatch(/已复制/)
  })

  it('shows error status when clipboard.writeText rejects', async () => {
    const writeText = vi.fn(async () => {
      throw new Error('clipboard blocked')
    })
    Object.assign(navigator, { clipboard: { writeText } })
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    render(<GroupMessageItem msg={msgWithCode} />)
    fireEvent.click(screen.getByTestId('group-copy-code-btn'))

    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1))
    await waitFor(() => {
      const s = screen.queryByTestId('group-copy-status')
      expect(s?.textContent).toBe('复制失败')
    })
    expect(consoleError).toHaveBeenCalled()
    consoleError.mockRestore()
  })
})
