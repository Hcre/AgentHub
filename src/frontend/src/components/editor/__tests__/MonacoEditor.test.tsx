import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createRef, useEffect } from 'react'
import type { ChangeEvent, ReactNode } from 'react'
import {
  MonacoEditor,
  type MonacoEditorHandle,
  type MonacoLanguage,
} from '../MonacoEditor'

/**
 * 3 路径覆盖：
 *   1. mount    — 渲染时拿到 testid + 把受控 value 正确写入容器（@monaco-editor/react 在
 *                 jsdom 下渲染占位，断言容器 div + props 透传，不依赖 Monaco 内部 textarea）
 *   2. edit     — 用户在 Monaco 内部编辑（jsdom fallback：直接用 onChange 模拟；真实浏览器
 *                 下 @monaco-editor/react 会在 onChange 里把新值透传出来）
 *   3. onChange — onChange 回调被触发，签名是 @monaco-editor/react 的 OnChange 类型
 *                 （value: string | undefined）— 验证父组件能正确收到新值
 *
 * jsdom 限制：@monaco-editor/react 在 jsdom 找不到 Web Worker，会 fallback 到
 * 「loading」div 或者直接抛错（取决于配置）。我们用 vi.mock 让它返回受控的
 * <textarea> 占位，验证 props 透传 + onChange 链路 + ref focus/getValue。
 */

type MockEditorProps = {
  value?: string
  onChange?: (v: string | undefined) => void
  onMount?: (ed: unknown) => void
  language?: string
  theme?: string
  options?: { readOnly?: boolean; fontSize?: number }
  height?: number | string
  loading?: ReactNode
}

vi.mock('@monaco-editor/react', () => {
  function MockEditor(props: MockEditorProps) {
    const onMount = props.onMount
    const value = props.value
    useEffect(() => {
      if (onMount) {
        onMount({
          focus: () => undefined,
          getModel: () => ({
            getLineCount: () => (value ?? '').split('\n').length,
            getLineMaxColumn: () =>
              (value ?? '').split('\n').slice(-1)[0]?.length ?? 0,
          }),
          getValue: () => value ?? '',
          setPosition: () => undefined,
        })
      }
    }, [onMount, value])
    return (
      <div
        data-mock-monaco="true"
        data-language={props.language}
        data-theme={props.theme}
        data-readonly={props.options?.readOnly ? 'true' : 'false'}
        data-font-size={props.options?.fontSize}
        style={{ height: props.height }}
      >
        <textarea
          data-testid="mock-monaco-textarea"
          value={props.value ?? ''}
          readOnly={props.options?.readOnly}
          onChange={(e: ChangeEvent<HTMLTextAreaElement>) =>
            props.onChange?.(e.target.value)
          }
        />
        {props.loading}
      </div>
    )
  }
  return {
    default: Object.assign(
      (p: MockEditorProps) => <MockEditor {...p} />,
      { displayName: 'MockMonacoEditor' },
    ),
  }
})

describe('MonacoEditor (P2-1)', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('mount: renders container with testid and forwards language/theme/value props', () => {
    const ref = createRef<MonacoEditorHandle>()
    render(
      <MonacoEditor
        ref={ref}
        value="const x = 1"
        language={'typescript' as MonacoLanguage}
        theme="vs-dark"
        aria-label="test monaco"
      />,
    )
    const el = screen.getByTestId('monaco-editor')
    expect(el).toBeInTheDocument()
    expect(el.getAttribute('data-monaco-language')).toBe('typescript')
    expect(el.getAttribute('data-monaco-theme')).toBe('vs-dark')
    expect(el.getAttribute('aria-label')).toBe('test monaco')
    // Mock 子 textarea 把受控 value 写进去
    const ta = screen.getByTestId('mock-monaco-textarea') as HTMLTextAreaElement
    expect(ta.value).toBe('const x = 1')
  })

  it('edit: typing in the editor propagates new value to the parent via onChange', () => {
    const onChange = vi.fn()
    render(
      <MonacoEditor
        value="hello"
        onChange={onChange}
        language={'python' as MonacoLanguage}
      />,
    )
    const ta = screen.getByTestId('mock-monaco-textarea') as HTMLTextAreaElement
    fireEvent.change(ta, { target: { value: 'print("hi")' } })
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith('print("hi")')
  })

  it('onChange: ref handle.focus + getValue are exposed and reflect latest value', async () => {
    const onChange = vi.fn()
    const ref = createRef<MonacoEditorHandle>()
    const { rerender } = render(
      <MonacoEditor
        ref={ref}
        value="initial"
        onChange={onChange}
        language={'json' as MonacoLanguage}
      />,
    )

    // 等 onMount 触发 + ref 就绪（useEffect 异步）
    await waitFor(() => expect(ref.current).not.toBeNull())
    // 初始 getValue = 初始 value
    expect(ref.current?.getValue()).toBe('initial')

    // 用户在 Monaco 内部编辑
    const ta = screen.getByTestId('mock-monaco-textarea') as HTMLTextAreaElement
    await act(async () => {
      fireEvent.change(ta, { target: { value: '{"a":1}' } })
    })
    expect(onChange).toHaveBeenCalledWith('{"a":1}')

    // 父组件把新 value 传回来（受控），rerender
    rerender(
      <MonacoEditor
        ref={ref}
        value='{"a":1}'
        onChange={onChange}
        language={'json' as MonacoLanguage}
      />,
    )
    // 等 mock useEffect 重新挂载后的新 onMount
    await waitFor(() => expect(ref.current?.getValue()).toBe('{"a":1}'))

    // focus() 不应抛错（mock 里是 noop）
    expect(() => ref.current?.focus()).not.toThrow()
  })
})
