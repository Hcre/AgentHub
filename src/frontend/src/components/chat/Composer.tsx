import { forwardRef, useImperativeHandle, useRef, useState } from 'react'
import { Button, Icon } from '../ui'
import type { Agent } from '../../types'

/** 父组件可调用 setText 从外部塞值（prompt 建议卡点击、@提及等） */
export type ComposerHandle = {
  setText: (text: string) => void
  focus: () => void
}

export const Composer = forwardRef<ComposerHandle, { agent: Agent; onSend: (text: string) => void }>(
  function Composer({ agent, onSend }, ref) {
  const [val, setVal] = useState('')
  const taRef = useRef<HTMLTextAreaElement>(null)

  useImperativeHandle(ref, () => ({
    setText: (text: string) => {
      setVal(text)
      // 触发 autosize
      requestAnimationFrame(() => {
        const ta = taRef.current
        if (!ta) return
        ta.style.height = 'auto'
        ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
        ta.focus()
      })
    },
    focus: () => taRef.current?.focus(),
  }))

  const send = () => {
    const text = val.trim()
    if (!text) return
    onSend(text)
    setVal('')
    const ta = taRef.current
    if (ta) ta.style.height = 'auto'
  }

  const autosize = () => {
    const ta = taRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
  }

  const insert = (open: string, close = '') => {
    const ta = taRef.current
    if (!ta) return
    const { selectionStart: start, selectionEnd: end } = ta
    const sel = val.slice(start, end) || '文本'
    setVal(val.slice(0, start) + open + sel + close + val.slice(end))
    setTimeout(() => {
      ta.focus()
      ta.setSelectionRange(start + open.length, start + open.length + sel.length)
    }, 0)
  }

  return (
    <div className="mx-4 mb-4 rounded-xl border bg-background shadow-sm transition-all focus-within:ring-2 focus-within:ring-ring">
      <textarea
        ref={taRef}
        rows={1}
        placeholder={`Ask ${agent.role.toLowerCase()}…`}
        value={val}
        onChange={(e) => {
          setVal(e.target.value)
          autosize()
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            send()
          }
        }}
        className="w-full resize-none rounded-t-xl border-0 bg-transparent px-3 py-3 text-[14px] outline-none placeholder:text-muted-foreground"
        style={{ maxHeight: 200 }}
      />
      <div className="flex items-center justify-between px-2 py-2">
        <div className="flex gap-0.5">
          <Button
            variant="ghost"
            size="iconSm"
            title="附件"
            onClick={() => insert('📎 ', '')}
            className="h-7 w-7 text-muted-foreground"
          >
            <Icon name="paperclip" className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="iconSm"
            title="粗体"
            onClick={() => insert('**', '**')}
            className="h-7 w-7 text-muted-foreground"
          >
            <Icon name="bold" className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="iconSm"
            title="表情"
            onClick={() => insert('🙂 ', '')}
            className="h-7 w-7 text-muted-foreground"
          >
            <Icon name="smile" className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="iconSm"
            title="提及"
            onClick={() => insert(`@${agent.name} `, '')}
            className="h-7 w-7 text-muted-foreground"
          >
            <Icon name="atSign" className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-muted-foreground">↵ 发送</span>
          <Button variant="brand" size="iconSm" className="h-7 w-7" onClick={send}>
            <Icon name="send" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
  },
)
