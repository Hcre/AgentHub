import { forwardRef, useCallback, useImperativeHandle, useRef } from 'react'
import Editor, { type OnChange, type OnMount } from '@monaco-editor/react'

export type MonacoLanguage = 'typescript' | 'javascript' | 'python' | 'json' | 'markdown' | 'plaintext'

export type MonacoEditorHandle = {
  /** 暴露给父组件（Composer）的 imperative 入口：把光标聚焦到编辑器 + 末尾 */
  focus: () => void
  /** 让父组件把 Monaco 当前值拿出来（编辑器内部 value 走受控，这里只暴露 getter） */
  getValue: () => string
}

export type MonacoEditorProps = {
  /** 受控值：父组件在 onChange 拿到新值后自己 setState，再传回来。 */
  value: string
  /** 每次内容变化都回调，签名对齐 @monaco-editor/react 的 OnChange。 */
  onChange?: OnChange
  /** 编辑器语言（影响语法高亮 + 自动补全）。 */
  language?: MonacoLanguage
  /** 编辑器主题：跟随系统 / 浅色 / 暗色。 */
  theme?: 'vs' | 'vs-dark' | 'hc-black'
  /** 占满父容器高度（默认 220px，最小 160px，最大 360px）。 */
  minHeight?: number
  maxHeight?: number
  /** aria 标签，方便测试 + 屏幕阅读器。 */
  'aria-label'?: string
  /** 测试 id（默认 'monaco-editor'）。 */
  'data-testid'?: string
  /** 是否禁用（true = 只读 + 灰色背景）。 */
  disabled?: boolean
}

/**
 * MonacoEditor — 包一层 @monaco-editor/react 让 Composer 等调用方能：
 *   1. 受控 value（Composer 自己 useState 管 value）
 *   2. 接到 onChange 拿到最新内容
 *   3. 通过 ref 主动 focus（Composer 外部点「代码模式」时自动聚焦）
 *   4. 测试里能 getByTestId('monaco-editor') 定位（@monaco-editor/react 默认容器无 role）
 *
 * 不暴露的语言 + 主题走默认值。窗口高度用 CSS 控（min/max height 由父容器约束）。
 * 在 jsdom 测试里 @monaco-editor/react 会 fallback 到占位 div（`No valid Monaco
 * loader configured`）—— 测试断言不依赖 Monaco 内部内容，只断言 onChange 链路通。
 */
export const MonacoEditor = forwardRef<MonacoEditorHandle, MonacoEditorProps>(function MonacoEditor(
  {
    value,
    onChange,
    language = 'typescript',
    theme = 'vs',
    minHeight = 160,
    maxHeight = 360,
    disabled = false,
    'aria-label': ariaLabel = '代码编辑器',
    'data-testid': dataTestid = 'monaco-editor',
  },
  ref,
) {
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null)

  const handleMount: OnMount = useCallback((ed) => {
    editorRef.current = ed
  }, [])

  useImperativeHandle(
    ref,
    () => ({
      focus: () => {
        const ed = editorRef.current
        if (!ed) return
        ed.focus()
        // 把光标移到末尾（不调 setPosition Monaco API，直接用原生 end-of-text）
        const model = ed.getModel()
        if (model) {
          const lineCount = model.getLineCount()
          const lastCol = model.getLineMaxColumn(lineCount)
          ed.setPosition({ lineNumber: lineCount, column: lastCol })
        }
      },
      getValue: () => editorRef.current?.getValue() ?? value,
    }),
    [value],
  )

  return (
    <div
      data-testid={dataTestid}
      data-monaco-language={language}
      data-monaco-theme={theme}
      data-monaco-disabled={disabled ? 'true' : 'false'}
      aria-label={ariaLabel}
      role="textbox"
      style={{
        minHeight,
        maxHeight,
        border: '1px solid hsl(var(--border))',
        borderRadius: 8,
        overflow: 'hidden',
        background: disabled ? 'hsl(var(--muted) / 0.4)' : 'transparent',
      }}
    >
      <Editor
        value={value}
        onChange={onChange}
        onMount={handleMount}
        language={language}
        theme={theme}
        height={`${Math.max(minHeight, 180)}px`}
        options={{
          readOnly: disabled,
          minimap: { enabled: false },
          fontSize: 13,
          fontFamily: 'var(--font-mono, ui-monospace, SFMono-Regular, monospace)',
          scrollBeyondLastLine: false,
          automaticLayout: true,
          tabSize: 2,
          wordWrap: 'on',
          padding: { top: 8, bottom: 8 },
          renderLineHighlight: 'gutter',
          scrollbar: { vertical: 'auto', horizontal: 'auto' },
        }}
        loading={<div className="p-3 font-mono text-[12px] text-muted-foreground">加载编辑器…</div>}
      />
    </div>
  )
})
