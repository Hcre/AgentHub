/**
 * SlideView — PPT 预览组件（M3-B）
 * 左侧缩略图列表 + 右侧当前页文本内容
 * 复用 fsApi.pptxSlides 后端抽页端点
 */
import { useEffect, useState } from 'react'
import { fsApi } from '../../api/fs'
import { cn } from '../../lib/cn'

interface Props {
  path: string
  name: string
}

interface Slide {
  index: number
  texts: string[]
  text_count: number
}

export function SlideView({ path, name }: Props) {
  const [slides, setSlides] = useState<Slide[]>([])
  const [active, setActive] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    fsApi
      .pptxSlides(path)
      .then((out) => {
        if (cancelled) return
        setSlides(out.slides)
        setActive(0)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err?.message ?? '无法加载 PPT')
      })
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [path])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-[12px] text-muted-foreground">
        正在解析 {name}…
      </div>
    )
  }

  if (error || slides.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-[12px] text-destructive">
        ⚠️ {error ?? '无法打开此 PPT 文件'}
      </div>
    )
  }

  const current = slides[active]

  return (
    <div className="flex h-full">
      {/* 左侧缩略图列表 */}
      <div className="w-32 flex-shrink-0 overflow-y-auto border-r bg-white dark:bg-black">
        {slides.map((s, i) => (
          <button
            key={s.index}
            onClick={() => setActive(i)}
            data-testid={`slide-thumb-${s.index}`}
            data-active={i === active ? 'true' : undefined}
            className={cn(
              'flex w-full flex-col items-center border-b p-2 text-[10px] transition-colors',
              i === active
                ? 'bg-brand/10 text-brand'
                : 'text-muted-foreground hover:bg-accent',
            )}
          >
            <div className="mb-1 flex h-12 w-20 items-center justify-center rounded border bg-background text-[10px]">
              第 {s.index} 页
            </div>
            <span className="truncate">{s.text_count} 段</span>
          </button>
        ))}
      </div>

      {/* 右侧大图（文本内容） */}
      <div className="flex-1 overflow-y-auto bg-white p-6 dark:bg-black">
        <div className="mb-3 text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
          第 {current.index} 页 / 共 {slides.length} 页
        </div>
        {current.texts.length === 0 ? (
          <p className="text-[12px] italic text-muted-foreground">（本页无文本内容）</p>
        ) : (
          <div className="space-y-3">
            {current.texts.map((t, i) => (
              <p
                key={i}
                className="border-l-2 border-brand/30 pl-3 text-[13.5px] leading-relaxed text-foreground"
              >
                {t}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}