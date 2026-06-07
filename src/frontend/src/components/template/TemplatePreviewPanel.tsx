import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { Button, Icon } from '../ui'
import { cn } from '../../lib/cn'
import type { TemplateData, TemplateDetail } from '../../stores/templateStore'
import { useTemplateStore } from '../../stores/templateStore'

export interface TemplatePreviewPanelProps {
  template: TemplateData
  onClose: () => void
  onEdit?: (template: TemplateData) => void
  /** Called when user clicks "使用此模板" — parent navigates to CreateAgentModal */
  onUseTemplate?: (template: TemplateData) => void
}

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

function label(t: TemplateData): string {
  return t.display_name_zh || t.name
}

export function TemplatePreviewPanel({ template, onClose, onEdit, onUseTemplate }: TemplatePreviewPanelProps) {
  const getTemplateDetail = useTemplateStore((s) => s.getTemplateDetail)
  const deleteTemplate = useTemplateStore((s) => s.deleteTemplate)
  const loadTemplates = useTemplateStore((s) => s.loadTemplates)

  const [detail, setDetail] = useState<TemplateDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    setLoading(true)
    setError('')
    setDetail(null)
    getTemplateDetail(template.id)
      .then((d) => setDetail(d))
      .catch((e) => setError(e instanceof Error ? e.message : 'failed to load'))
      .finally(() => setLoading(false))
  }, [template.id, getTemplateDetail])

  const isLocal = template.source === 'local'

  const handleDelete = async () => {
    if (!window.confirm('Delete template "' + label(template) + '"?')) return
    setDeleting(true)
    try {
      await deleteTemplate(template.id)
      onClose()
      loadTemplates()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'delete failed')
    } finally {
      setDeleting(false)
    }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      const r = await fetch('/api/templates/' + template.id + '/export')
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        throw new Error(d.detail || 'export failed')
      }
      const blob = await r.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const disposition = r.headers.get('Content-Disposition') || ''
      const m = disposition.match(/filename="?([^"]+)"?/)
      a.download = (m && m[1]) ? m[1] : template.name + '.md'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'export failed')
    } finally {
      setExporting(false)
    }
  }

  const panel = (
    <div className="fixed inset-0 z-50">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      {/* Slide-in panel from right */}
      <div
        className={cn(
          'absolute right-0 top-0 h-full w-full max-w-lg overflow-y-auto border-l border-border/60 bg-background shadow-xl glass-soft',
          'animate-[var(--animate-slide-in-right)]',
        )}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border/70 px-5 py-3.5">
            <h2 className="text-[15px] font-semibold truncate pr-4">{label(template)}</h2>
            <Button variant="ghost" size="iconSm" onClick={onClose}>
              <Icon name="x" className="h-3.5 w-3.5" />
            </Button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-5">
            {loading && (
              <div className="flex items-center justify-center py-12">
                <Spinner />
                <span className="ml-2 text-[13px] text-muted-foreground">加载详情…</span>
              </div>
            )}

            {error && (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600 mb-3">
                {error}
              </div>
            )}

            {detail && !loading && (
              <div className="flex flex-col gap-3">
                <div className="rounded-lg border border-border/60 p-3 space-y-1.5">
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className="font-medium text-muted-foreground w-16">名称</span>
                    <span className="font-mono text-[12.5px]">{template.name}</span>
                  </div>
                  {template.display_name_zh && (
                    <div className="flex items-center gap-2 text-[12px]">
                      <span className="font-medium text-muted-foreground w-16">CN</span>
                      <span>{template.display_name_zh}</span>
                    </div>
                  )}
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className="font-medium text-muted-foreground w-16">来源</span>
                    <span className={cn(
                      'rounded px-1.5 py-0.5 text-[10px] font-medium',
                      template.source === 'local'
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-blue-100 text-blue-700',
                    )}>
                      {template.source === 'local' ? '本地' : template.source}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className="font-medium text-muted-foreground w-16">层级</span>
                    <span>{template.model_tier}</span>
                  </div>
                </div>

                {(template.description || template.description_zh) && (
                  <div className="rounded-lg border border-border/60 p-3">
                    <h4 className="text-[12px] font-medium text-muted-foreground mb-1">描述</h4>
                    <p className="text-[12.5px] leading-relaxed">
                      {template.description_zh || template.description}
                    </p>
                  </div>
                )}

                {detail.system_prompt && (
                  <div className="rounded-lg border border-border/60 p-3">
                    <h4 className="text-[12px] font-medium text-muted-foreground mb-1">System Prompt</h4>
                    <pre className="whitespace-pre-wrap text-[12px] leading-relaxed text-foreground/80 font-mono max-h-48 overflow-y-auto">
                      {detail.system_prompt}
                    </pre>
                  </div>
                )}

                {template.recommended_skills.length > 0 && (
                  <div className="rounded-lg border border-border/60 p-3">
                    <h4 className="text-[12px] font-medium text-muted-foreground mb-1">推荐 Skills</h4>
                    <div className="flex flex-wrap gap-1">
                      {template.recommended_skills.map((s) => (
                        <span key={s} className="rounded bg-muted/60 px-2 py-0.5 text-[11px]">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {template.compatible_agent_systems.length > 0 && (
                  <div className="rounded-lg border border-border/60 p-3">
                    <h4 className="text-[12px] font-medium text-muted-foreground mb-1">兼容 CLI</h4>
                    <div className="flex flex-wrap gap-1">
                      {template.compatible_agent_systems.map((c) => (
                        <span key={c} className="rounded bg-muted/60 px-2 py-0.5 text-[11px] font-mono">
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Footer actions */}
          <div className="border-t border-border/70 px-5 py-3.5">
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={onClose}>
                <Icon name="chevronLeft" className="h-3.5 w-3.5" />
                返回列表
              </Button>
              {isLocal && onEdit && (
                <Button variant="outline" size="sm" onClick={() => onEdit(template)}>
                  <Icon name="pencil" className="h-3.5 w-3.5" />
                  编辑
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
                {exporting ? <Spinner /> : <Icon name="files" className="h-3.5 w-3.5" />}
                导出 .md
              </Button>
              <div className="flex-1" />
              {isLocal && (
                <Button variant="destructive" size="sm" onClick={handleDelete} disabled={deleting}>
                  <Icon name="trash2" className="h-3.5 w-3.5" />
                  删除
                </Button>
              )}
              {onUseTemplate && (
                <Button variant="brand" size="sm" onClick={() => onUseTemplate(template)}>
                  <Icon name="rocket" className="h-3.5 w-3.5" />
                  使用此模板
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )

  return createPortal(panel, document.body)
}
