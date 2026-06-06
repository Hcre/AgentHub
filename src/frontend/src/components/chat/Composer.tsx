import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type ChangeEvent,
} from 'react'
import { Button, Icon } from '../ui'
import type { Agent, Attachment } from '../../types'

/** 父组件可调用 setText 从外部塞值（prompt 建议卡点击、@提及等） */
export type ComposerHandle = {
  setText: (text: string) => void
  focus: () => void
}

/** 发送载荷：text 必有，attachment 可选（先上传拿到 url 再回显） */
export type ComposerPayload = {
  text: string
  attachment?: Attachment
}

export const Composer = forwardRef<
  ComposerHandle,
  { agent: Agent; onSend: (payload: ComposerPayload) => void }
>(function Composer({ agent, onSend }, ref) {
  const [val, setVal] = useState('')
  const [attachment, setAttachment] = useState<Attachment | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const taRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

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
    if (!text && !attachment) return
    onSend({ text, attachment: attachment ?? undefined })
    setVal('')
    setAttachment(null)
    setUploadError(null)
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
