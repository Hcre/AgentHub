import { useState } from 'react'
import type { PptxSlide } from '../../api/fs'

/**
 * PPT 预览：左侧缩略图导航（页码 + 标题）+ 右侧大图（标题 + 正文要点 + 讲者备注）。
 * 纯文本渲染（后端 python-pptx 抽文本），不内嵌真实幻灯片渲染图。
 */
export function SlideView({ slides }: { slides: PptxSlide[] }) {
  const [active, setActive] = useState(0)

  if (slides.length === 0) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        空演示文稿（0 页）
      </div>
    )
  }

  const cur = slides[Math.min(active, slides.length - 1)]

  return (
    <div className="flex h-full min-h-0" data-testid="slide-view">
      {/* 左：缩略图导航 */}
      <aside className="flex w-44 flex-shrink-0 flex-col gap-1 overflow-auto border-r border-border/60 bg-muted/10 p-2">
        {slides.map((s, i) => (
          <button
            key={s.index}
            type="button"
            data-testid={`slide-thumb-${i}`}
            data-active={i === active ? 'true' : undefined}
            onClick={() => setActive(i)}
            className={
              'flex flex-col gap-0.5 rounded-md border px-2 py-1.5 text-left text-[11.5px] transition-colors ' +
              (i === active
                ? 'border-brand/40 bg-brand/10 text-foreground'
                : 'border-transparent text-muted-foreground hover:bg-accent hover:text-foreground')
            }
          >
            <span className="font-mono text-[10px] text-muted-foreground/70">{i + 1}</span>
            <span className="truncate font-medium">{s.title || `第 ${i + 1} 页`}</span>
          </button>
        ))}
      </aside>

      {/* 右：当前页大图 */}
      <div className="flex min-w-0 flex-1 flex-col overflow-auto p-6">
        <div className="mx-auto flex aspect-[16/9] w-full max-w-3xl flex-col rounded-lg border bg-card p-8 shadow-sm">
          <div className="mb-1 font-mono text-[11px] text-muted-foreground/60">
            第 {active + 1} / {slides.length} 页
          </div>
          {cur.title && (
            <h2 className="mb-4 text-xl font-semibold text-foreground" data-testid="slide-title">
              {cur.title}
            </h2>
          )}
          <ul className="flex-1 space-y-2 text-[14px] leading-relaxed text-foreground/90">
            {cur.texts.map((t, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-brand/60" />
                <span className="whitespace-pre-wrap">{t}</span>
              </li>
            ))}
            {cur.texts.length === 0 && (
              <li className="text-muted-foreground/60">（本页无文本内容）</li>
            )}
          </ul>
        </div>
        {cur.notes && (
          <div className="mx-auto mt-4 w-full max-w-3xl rounded-md border border-border/60 bg-muted/20 px-4 py-2 text-[12.5px] text-muted-foreground">
            <span className="mr-1 font-medium text-foreground/70">讲者备注：</span>
            <span className="whitespace-pre-wrap">{cur.notes}</span>
          </div>
        )}
      </div>
    </div>
  )
}
