import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Composer, type ComposerPayload } from '../Composer'
import type { Agent } from '../../../types'

const testAgent: Agent = {
  id: 'a-1',
  name: 'Coda',
  role: 'Codebase Assistant',
  color: 'brand',
  online: true,
}

/** 创建一个测试用的 File，并通过隐藏的 file input 触发上传 */
function pickFile(file: File) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement
  expect(input).toBeTruthy()
  Object.defineProperty(input, 'files', {
    value: [file],
    configurable: true,
  })
  fireEvent.change(input)
}

describe('Composer upload flow (P0-3)', () => {
  const originalFetch = global.fetch

  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    global.fetch = originalFetch
  })

  it('uploads file via /api/attachments/multipart and injects url into onSend payload', async () => {
    const user = userEvent.setup()
    const onSend = vi.fn<(p: ComposerPayload) => void>()
    const mockJson = {
      id: 'abc123',
      name: 'notes.txt',
      size: 28,
      mime: 'text/plain',
      url: '/api/attachments/abc123',
    }
    const fetchMock = vi.fn(async () => ({
      ok: true,
      status: 200,
      json: async () => mockJson,
    }))
    global.fetch = fetchMock as unknown as typeof fetch

    render(<Composer agent={testAgent} onSend={onSend} />)

    // 模拟用户选文件 → 触发 fetch
    const file = new File(['hello attachments upload test!'], 'notes.txt', {
      type: 'text/plain',
    })
    pickFile(file)

    // 等待 fetch 被调用
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('/api/attachments/multipart')
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    const fd = init.body as FormData
    expect(fd.get('file')).toBe(file)

    // 上传成功后，preview 出现附件名
    await waitFor(() =>
      expect(screen.getByText('notes.txt')).toBeInTheDocument(),
    )

    // 输入文本 + 发送
    const ta = screen.getByPlaceholderText(/Ask/i) as HTMLTextAreaElement
    await user.type(ta, '请看附件')
    const sendBtn = screen.getByTitle('附件').parentElement?.querySelectorAll('button')[3]
      // fallback：直接通过占位符定位 send button（最后一个 brand button）
    // send button 是 footer 右侧的 brand variant，用 role 不可靠，直接 fireEvent.click 找最近 button
    const buttons = screen.getAllByRole('button')
    const send = buttons.find((b) => b.querySelector('svg')?.classList.contains('lucide-send'))
      ?? buttons[buttons.length - 1]
    void sendBtn
    fireEvent.click(send)

    expect(onSend).toHaveBeenCalledTimes(1)
    const payload = onSend.mock.calls[0]?.[0]
    expect(payload.text).toBe('请看附件')
    expect(payload.attachment).toBeDefined()
    expect(payload.attachment?.url).toBe('/api/attachments/abc123')
    expect(payload.attachment?.name).toBe('notes.txt')
  })

  it('shows error message when upload fails with 413', async () => {
    const onSend = vi.fn<(p: ComposerPayload) => void>()
    global.fetch = vi.fn(async () => ({
      ok: false,
      status: 413,
      json: async () => ({ detail: 'too big' }),
    })) as unknown as typeof fetch

    render(<Composer agent={testAgent} onSend={onSend} />)

    pickFile(new File(['x'], 'big.bin', { type: 'text/plain' }))

    await waitFor(() =>
      expect(screen.getByText(/10MB/)).toBeInTheDocument(),
    )
    expect(onSend).not.toHaveBeenCalled()
  })
})
