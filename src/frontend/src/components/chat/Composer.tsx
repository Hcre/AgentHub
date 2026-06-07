import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type ChangeEvent,
} from 'react'
import { Code2, Reply, X } from 'lucide-react'
import { Button, Icon } from '../ui'
import {
  MonacoEditor,
  type MonacoEditorHandle,
  type MonacoLanguage,
} from '../editor/MonacoEditor'
import type { Agent, Attachment, ReplyRef } from '../../types'

/** 父组件可调用 setText 从外部塞值（prompt 建议卡点击、@提及等） */
export type ComposerHandle = {
  setText: (text: string) => void
  focus: () => void
  /**
   * P1-1 reply/quote：父组件（MessageBubble 点击回复按钮）调用此方法
   * 把被引用消息的最小快照塞进 Composer。传入 null 清空 reply 状态。
   */
  setReplyTo: (ref: ReplyRef | null) => void
}

/** 发送载荷：text 必有，attachment / replyTo 可选 */
export type ComposerPayload = {
  text: string
  attachment?: Attachment
  /**
   * P1-1 reply/quote：被引用消息的最小快照（id/author/snippet）。
   * 父组件拿到后写入 store.addUserMessage(... replyTo) + 透传给后端。
   */
  replyTo?: ReplyRef
}

export const Composer = forwardRef<
  ComposerHandle,
  { agent: Agent; onSend: (payload: ComposerPayload) => void }
>(function Composer({ agent, onSend }, ref) {
  const [val, setVal] = useState('')
  const [attachment, setAttachment] = useState<Attachment | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  // P1-1 reply mode：当前正在回复的消息引用；null = 普通模式
  const [replyTo, setReplyTo] = useState<ReplyRef | null>(null)
  // P2-1 代码模式：开启后用 Monaco 替换 textarea；发送时把 val 包成 ```lang\n...\n```
  const [codeMode, setCodeMode] = useState(false)
  const [codeLang, setCodeLang] = useState<MonacoLanguage>('typescript')
  const taRef = useRef<HTMLTextAreaElement>(null)
  const monacoRef = useRef<MonacoEditorHandle>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useImperativeHandle(ref, () => ({
    setText: (text: string) => {
      setVal(text)
      // 触发 autosize / Monaco focus
      requestAnimationFrame(() => {
        if (codeMode) {
          monacoRef.current?.focus()
          return
        }
        const ta = taRef.current
        if (!ta) return
        ta.style.height = 'auto'
        ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
        ta.focus()
      })
    },
    focus: () => {
      if (codeMode) monacoRef.current?.focus()
      else taRef.current?.focus()
    },
    setReplyTo: (ref: ReplyRef | null) => {
      setReplyTo(ref)
      // 进入 reply mode → 自动 focus 到 textarea
      requestAnimationFrame(() => {
        if (codeMode) monacoRef.current?.focus()
        else taRef.current?.focus()
      })
    },
  }))

  const send = () => {
    const text = val.trim()
    if (!text && !attachment) return
    // 代码模式：把 val 包成 ```lang\n...\n``` 围栏发出去，接收端 ReactMarkdown 自动高亮
    const payloadText =
      codeMode && text
        ? '```' + codeLang + '\n' + text + '\n```'
        : text
    onSend({
      text: payloadText,
      attachment: attachment ?? undefined,
      replyTo: replyTo ?? undefined,
    })
    setVal('')
    setAttachment(null)
    setUploadError(null)
    setReplyTo(null)
    const ta = taRef.current
    if (ta) ta.style.height = 'auto'
  }

  const cancelReply = () => setReplyTo(null)

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

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
  }

  const uploadFile = async (file: File) => {
    setUploading(true)
    setUploadError(null)
    try {
      const fd = new FormData()
      fd.append('file', file)
      const resp = await fetch('/api/attachments/multipart', {
        method: 'POST',
        body: fd,
      })
      if (!resp.ok) {
        const detail =
          resp.status === 413
            ? '文件超过 10MB 限制'
            : resp.status === 415
              ? '文件类型不支持'
              : `上传失败 (${resp.status})`
        setUploadError(detail)
        return
      }
      const data = (await resp.json()) as {
        id: string
        name: string
        size: number
        mime: string
        url: string
      }
      setAttachment({ name: data.name, size: formatSize(data.size), url: data.url })
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : '网络错误')
    } finally {
      setUploading(false)
    }
  }

  const onFilePick = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    // 重置 input value 以便重复选同一文件
    e.target.value = ''
    if (file) void uploadFile(file)
  }

  const removeAttachment = () => {
    setAttachment(null)
    setUploadError(null)
  }

  return (
    <div className="composer-mobile-tight mx-4 mb-4 rounded-xl border bg-background shadow-sm transition-all focus-within:ring-2 focus-within:ring-ring">
      {/* P1-1 reply 引文条：紧贴 textarea 上方。显示作者 + snippet + 取消按钮。
          max-height 限制：snippet 超过 60 字符自动省略，与 MessageBubble.replyTo 保持视觉一致。 */}
      {replyTo && (
        <div
          data-testid="reply-badge"
          data-reply-to-id={replyTo.id}
          className="mx-2 mt-2 flex items-start gap-1.5 rounded-md border-l-2 border-brand/60 bg-muted/40 px-2 py-1 text-[12px] text-muted-foreground"
        >
          <Reply className="mt-0.5 h-3 w-3 flex-shrink-0 text-brand" strokeWidth={2} />
          <div className="min-w-0 flex-1">
            <div className="truncate font-medium text-foreground/80">
              回复 {replyTo.author}
            </div>
            <div className="line-clamp-2 break-words">{replyTo.snippet}</div>
          </div>
          <button
            type="button"
            data-testid="reply-cancel"
            aria-label="取消回复"
            title="取消回复"
            onClick={cancelReply}
            className="grid h-5 w-5 flex-shrink-0 place-items-center rounded text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}
      <textarea
        ref={taRef}
        rows={1}
        placeholder={replyTo
          ? `Ask ${agent.role.toLowerCase()} · 回复 ${replyTo.author}…`
          : `Ask ${agent.role.toLowerCase()}…`}
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
        hidden={codeMode}
      />
      {codeMode && (
        <div className="px-3 py-2" data-testid="composer-code-pane">
          <div className="mb-1 flex items-center justify-between">
            <span className="font-mono text-[11px] text-muted-foreground">
              代码模式 · 发送时自动包 {`\`\`\`${codeLang}\n…\n\`\`\``}
            </span>
            <select
              aria-label="选择语言"
              value={codeLang}
              onChange={(e) => setCodeLang(e.target.value as MonacoLanguage)}
              className="rounded border bg-background px-1.5 py-0.5 font-mono text-[11px]"
            >
              <option value="typescript">TypeScript</option>
              <option value="javascript">JavaScript</option>
              <option value="python">Python</option>
              <option value="json">JSON</option>
              <option value="markdown">Markdown</option>
              <option value="plaintext">纯文本</option>
            </select>
          </div>
          <MonacoEditor
            ref={monacoRef}
            value={val}
            language={codeLang}
            onChange={(next) => setVal(next ?? '')}
            aria-label="Composer 代码编辑器"
          />
        </div>
      )}
      {(attachment || uploadError || uploading) && (
        <div className="flex flex-wrap items-center gap-2 border-t px-3 py-2 text-[12px]">
          {uploading && (
            <span className="font-mono text-muted-foreground">上传中…</span>
          )}
          {uploadError && (
            <span className="font-mono text-destructive">{uploadError}</span>
          )}
          {attachment && !uploading && (
            <span className="inline-flex items-center gap-2 rounded border bg-muted/40 px-2 py-1 font-mono">
              <Icon name="paperclip" className="h-3 w-3 text-muted-foreground" />
              <span className="max-w-[180px] truncate">{attachment.name}</span>
              <span className="text-muted-foreground">{attachment.size}</span>
              <button
                type="button"
                aria-label="移除附件"
                onClick={removeAttachment}
                className="text-muted-foreground hover:text-foreground"
              >
                <Icon name="x" className="h-3 w-3" />
              </button>
            </span>
          )}
        </div>
      )}
      <div className="flex items-center justify-between px-2 py-2">
        <div className="flex gap-0.5">
          <input
            ref={fileRef}
            type="file"
            accept="image/png,image/jpeg,image/gif,application/pdf,text/markdown,text/plain,application/zip"
            onChange={onFilePick}
            className="hidden"
            aria-label="上传附件"
          />
          <Button
            variant="ghost"
            size="iconSm"
            title="附件"
            disabled={uploading}
            onClick={() => fileRef.current?.click()}
            className="h-7 w-7 text-muted-foreground"
          >
            <Icon name="paperclip" className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="iconSm"
            title="粗体"
            onClick={() => insert('**', '**')}
            className="composer-desktop-extras h-7 w-7 text-muted-foreground"
          >
            <Icon name="bold" className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="iconSm"
            title={codeMode ? '切回普通文本' : '切到代码模式（Monaco）'}
            aria-pressed={codeMode}
            data-testid="composer-code-toggle"
            onClick={() => setCodeMode((v) => !v)}
            className={
              codeMode
                ? 'h-7 w-7 text-brand'
                : 'h-7 w-7 text-muted-foreground'
            }
          >
            <Code2 className="h-3.5 w-3.5" strokeWidth={1.75} />
          </Button>
          <Button
            variant="ghost"
            size="iconSm"
            title="表情"
            onClick={() => insert('🙂 ', '')}
            className="composer-desktop-extras h-7 w-7 text-muted-foreground"
          >
            <Icon name="smile" className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="iconSm"
            title="提及"
            onClick={() => insert(`@${agent.name} `, '')}
            className="composer-desktop-extras h-7 w-7 text-muted-foreground"
          >
            <Icon name="atSign" className="h-3.5 w-3.5" />
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[11px] text-muted-foreground">↵ 发送</span>
          <Button
            variant="brand"
            size="iconSm"
            className="h-7 w-7"
            onClick={send}
            disabled={uploading || (!val.trim() && !attachment)}
          >
            <Icon name="send" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </div>
  )
})
