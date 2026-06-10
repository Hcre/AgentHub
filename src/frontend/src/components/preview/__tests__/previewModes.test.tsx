import { describe, it, expect, afterEach, vi, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { PREVIEW_MODES, type PreviewMode } from '../previewModes'

afterEach(cleanup)

/**
 * t1-preview-modes 单测（BDD B-4-P2-PV01）。
 * 主用例：4 个 mode (files / diff / deploy / webpage) 的 enabled 全部为 true，
 *   - 无 hint 字段（之前是 `hint: '即将到来'`）
 *   - RightPanel dropdown 渲染时 4 项全部可点击（无 disabled 灰态）
 *
 * 决策：直接对 PREVIEW_MODES 数组断言（数据源）；再加一个 dropdown 渲染 smoke
 *   test 防止后续改 const→function 漏改 enabled。
 */
describe('PREVIEW_MODES (t1-preview-modes BDD B-4-P2-PV01)', () => {
  it('exports exactly 5 modes in canonical order: files, diff, versions, deploy, webpage', () => {
    expect(PREVIEW_MODES.map((m) => m.mode)).toEqual([
      'files',
      'diff',
      'versions',
      'deploy',
      'webpage',
    ])
  })

  it('all modes have enabled=true (regression for the 3 enabled:false bug)', () => {
    for (const m of PREVIEW_MODES) {
      expect(m.enabled, `mode ${m.mode} should be enabled`).toBe(true)
    }
  })

  it.each(['files', 'diff', 'versions', 'deploy', 'webpage'] as PreviewMode[])(
    'mode "%s" has enabled=true (per-mode parity check)',
    (mode) => {
      const m = PREVIEW_MODES.find((x) => x.mode === mode)
      expect(m).toBeDefined()
      expect(m?.enabled).toBe(true)
      // 没有 hint 字段（之前是 `hint: '即将到来'`）
      expect(m?.hint).toBeUndefined()
    },
  )
})

/**
 * RightPanel dropdown 渲染测试：模拟 PREVIEW_MODES 数据 + 渲染 4 个 menuitem，
 * 确认全部 enabled（无 disabled 属性）+ 无 "即将到来" 文字。
 *
 * 注：RightPanel 自身依赖 uiStore + previewContext + workdir，e2e 已在 Playwright 里跑；
 * 这里只对 dropdown 渲染逻辑做最小 mock 验证。
 */
describe('PreviewMode dropdown rendering (RightPanel PreviewMenu smoke)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders all menuitems, all enabled (no disabled attr, no 即将到来 hint)', () => {
    // 微型镜像 RightPanel PreviewMenu 渲染逻辑（不引入 store 依赖）
    // 当 RightPanel 的 PreviewMenu 改为函数式 hook 时，本测试能继续工作
    const Menu = () => (
      <div role="menu">
        {PREVIEW_MODES.map((m) => (
          <button
            key={m.mode}
            type="button"
            role="menuitem"
            disabled={!m.enabled}
            data-testid={`menuitem-${m.mode}`}
          >
            <span>{m.title}</span>
            {!m.enabled && <span data-testid={`hint-${m.mode}`}>{m.hint}</span>}
          </button>
        ))}
      </div>
    )

    render(<Menu />)

    for (const mode of ['files', 'diff', 'versions', 'deploy', 'webpage'] as PreviewMode[]) {
      const btn = screen.getByTestId(`menuitem-${mode}`)
      expect(btn, `${mode} button should exist`).toBeInTheDocument()
      expect(
        btn.hasAttribute('disabled'),
        `${mode} button should NOT be disabled`,
      ).toBe(false)
      // 没有 "即将到来" 提示
      expect(screen.queryByTestId(`hint-${mode}`)).toBeNull()
      expect(screen.queryByText('即将到来')).toBeNull()
    }
  })

  it('clicking an enabled mode triggers the onSelect callback (dropdown selection works)', () => {
    const onSelect = vi.fn()
    const Menu = () => (
      <div role="menu">
        {PREVIEW_MODES.map((m) => (
          <button
            key={m.mode}
            type="button"
            role="menuitem"
            disabled={!m.enabled}
            onClick={() => m.enabled && onSelect(m.mode)}
            data-testid={`menuitem-${m.mode}`}
          >
            <span>{m.title}</span>
          </button>
        ))}
      </div>
    )

    render(<Menu />)
    fireEvent.click(screen.getByTestId('menuitem-diff'))
    fireEvent.click(screen.getByTestId('menuitem-deploy'))
    fireEvent.click(screen.getByTestId('menuitem-webpage'))

    expect(onSelect).toHaveBeenCalledTimes(3)
    expect(onSelect).toHaveBeenNthCalledWith(1, 'diff')
    expect(onSelect).toHaveBeenNthCalledWith(2, 'deploy')
    expect(onSelect).toHaveBeenNthCalledWith(3, 'webpage')
  })
})
