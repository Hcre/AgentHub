import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { WebPreviewCard } from '../WebPreviewCard'

afterEach(cleanup)

describe('WebPreviewCard fullscreen (P1-3)', () => {
  it('clicking 展开 opens a Dialog fullscreen modal (90vh, ESC-closable)', () => {
    render(<WebPreviewCard url="https://example.com/docs" title="Example Docs" />)

    // 1. 初始：折叠态，无 Dialog
    expect(screen.queryByTestId('webpreview-fullscreen-dialog')).not.toBeInTheDocument()
    const inlineIframe = document.querySelector('iframe')
    expect(inlineIframe).toBeNull() // 折叠态不挂 iframe

    // 2. 点「全屏预览」按钮（不是普通的「展开」）
    const fullscreenBtn = screen.getByTestId('fullscreen-btn')
    fireEvent.click(fullscreenBtn)

    // 3. Dialog 出现，承载内联卡片副本 + close button
    const dialog = screen.getByTestId('webpreview-fullscreen-dialog')
    expect(dialog).toBeInTheDocument()

    // 4. Dialog 里有 close 按钮
    const closeBtn = screen.getByTestId('fullscreen-close-btn')
    expect(closeBtn).toBeInTheDocument()

    // 5. 高度：DialogContent (dialog 的孙子 div) className 应有 h-[90vh]
    const content = dialog.querySelector('div.flex.flex-col') as HTMLElement | null
    expect(content).toBeTruthy()
    expect(content!.className).toMatch(/90vh/)

    // 6. 关闭按钮 click → Dialog 消失
    fireEvent.click(closeBtn)
    expect(screen.queryByTestId('webpreview-fullscreen-dialog')).not.toBeInTheDocument()
  })

  it('the inline 展开 button still toggles inline iframe (regression: existing behavior unchanged)', () => {
    render(<WebPreviewCard url="https://example.com" title="Inline" />)
    const inlineBtn = screen.getByRole('button', { name: /展开/ })
    fireEvent.click(inlineBtn)
    const iframe = screen.getByTitle('Inline') as HTMLIFrameElement
    expect(iframe).toBeInTheDocument()
    // 全屏 Dialog 不应被触发
    expect(screen.queryByTestId('webpreview-fullscreen-dialog')).not.toBeInTheDocument()
  })

  it('clicking the backdrop of the fullscreen Dialog closes it (regression: Dialog backdrop close)', () => {
    render(<WebPreviewCard url="https://example.com" title="X" />)
    fireEvent.click(screen.getByTestId('fullscreen-btn'))
    const dialog = screen.getByTestId('webpreview-fullscreen-dialog')
    expect(dialog).toBeInTheDocument()
    // backdrop 是 dialog 内（同一 fixed wrapper）的第一个子 div（className 含 'absolute inset-0'）
    const backdrop = dialog.querySelector('div.absolute.inset-0') as HTMLElement | null
    expect(backdrop).toBeTruthy()
    fireEvent.click(backdrop!)
    expect(screen.queryByTestId('webpreview-fullscreen-dialog')).not.toBeInTheDocument()
  })
})
