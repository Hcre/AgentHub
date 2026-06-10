import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { WebPreviewCard } from '../WebPreviewCard'
import { useUIStore } from '../../../stores/uiStore'

afterEach(cleanup)

// 设计变更（侧栏预览取代旧的就地全屏 Dialog）：点「侧栏」按钮把网页作为 preview tab
// 推进右侧栏（useUIStore.addPreviewTab + setActivePreviewTab + 展开右栏），不再渲染
// webpreview-fullscreen-dialog。这些用例断言新行为。
describe('WebPreviewCard sidebar preview (P1-3)', () => {
  beforeEach(() => {
    useUIStore.setState({ previewTabs: [], activePreviewTabId: null, rightPanelCollapsed: true })
  })

  it('clicking 侧栏 opens the URL as a webpage preview tab and expands the right panel', () => {
    render(<WebPreviewCard url="https://example.com/docs" title="Example Docs" />)

    // 初始：无 preview tab，右栏折叠
    expect(useUIStore.getState().previewTabs).toHaveLength(0)
    expect(useUIStore.getState().rightPanelCollapsed).toBe(true)

    fireEvent.click(screen.getByTestId('fullscreen-btn'))

    const { previewTabs, activePreviewTabId, rightPanelCollapsed } = useUIStore.getState()
    expect(previewTabs).toHaveLength(1)
    expect(previewTabs[0]).toMatchObject({ type: 'webpage', url: 'https://example.com/docs' })
    expect(previewTabs[0].label).toBe('Example Docs')
    // 该 tab 被设为 active，右栏展开
    expect(activePreviewTabId).toBe(previewTabs[0].id)
    expect(rightPanelCollapsed).toBe(false)
    // 不再有就地全屏 Dialog
    expect(screen.queryByTestId('webpreview-fullscreen-dialog')).not.toBeInTheDocument()
  })

  it('the inline 展开 button still toggles inline iframe (existing behavior unchanged)', () => {
    render(<WebPreviewCard url="https://example.com" title="Inline" />)
    const inlineBtn = screen.getByRole('button', { name: /展开/ })
    fireEvent.click(inlineBtn)
    const iframe = screen.getByTitle('Inline') as HTMLIFrameElement
    expect(iframe).toBeInTheDocument()
    // 内联展开不触碰右栏 preview tab
    expect(useUIStore.getState().previewTabs).toHaveLength(0)
  })

  it('falls back to host as label when no title is given', () => {
    render(<WebPreviewCard url="https://docs.example.org/path" />)
    fireEvent.click(screen.getByTestId('fullscreen-btn'))
    expect(useUIStore.getState().previewTabs[0].label).toBe('docs.example.org')
  })
})
