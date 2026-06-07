import { useEffect, useState } from 'react'
import { Button, Dialog, DialogContent, Icon, Input, Textarea } from '../ui'
import type { TemplateData, TemplateCreateInput } from '../../stores/templateStore'
import { useTemplateStore } from '../../stores/templateStore'

export interface TemplateEditorModalProps {
  open: boolean
  onClose: () => void
  template?: TemplateData | null
}

const MODEL_TIERS = ['inherit', 'fast', 'smart', 'max']

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

export function TemplateEditorModal({ open, onClose, template }: TemplateEditorModalProps) {
  const isEditing = !!template
  const createTemplate = useTemplateStore((s) => s.createTemplate)
  const updateTemplate = useTemplateStore((s) => s.updateTemplate)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [displayNameZh, setDisplayNameZh] = useState('')
  const [descriptionZh, setDescriptionZh] = useState('')
  const [modelTier, setModelTier] = useState('inherit')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (open) {
      if (template) {
        setName(template.name)
        setDescription(template.description)
        setDisplayNameZh(template.display_name_zh || '')
        setDescriptionZh(template.description_zh || '')
        setModelTier(template.model_tier || 'inherit')
        setSystemPrompt('')
        setError('')
      } else {
        setName('')
        setDescription('')
        setSystemPrompt('')
        setDisplayNameZh('')
        setDescriptionZh('')
        setModelTier('inherit')
        setError('')
      }
    }
  }, [open, template])

  const handleSave = async () => {
    if (!name.trim()) {
      setError('名称不能为空')
      return
    }
    setSaving(true)
    setError('')
    try {
      const data: TemplateCreateInput = {
        name: name.trim(),
        description: description.trim(),
        system_prompt: systemPrompt,
        model_tier: modelTier,
        recommended_skills: [],
        display_name_zh: displayNameZh.trim() || null,
        description_zh: descriptionZh.trim() || null,
        compatible_agent_systems: [],
        compatible_providers: [],
      }
      if (isEditing && template) {
        await updateTemplate(template.id, data)
      } else {
        await createTemplate(data)
      }
      onClose()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSaving(false)
    }
  }

  if (!open) return null

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-[15px] font-medium">
            {isEditing ? '编辑模板' : '新建模板'}
          </h3>
          <Button variant="ghost" size="iconSm" onClick={onClose}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        <div className="flex flex-col gap-3 overflow-y-auto p-4" style={{ maxHeight: '60vh' }}>
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
              {error}
            </div>
          )}

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">名称 (name)</span>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="模板英文标识，如 coding-assistant"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">中文名称 (display_name_zh)</span>
            <Input
              value={displayNameZh}
              onChange={(e) => setDisplayNameZh(e.target.value)}
              placeholder="如：编程助手"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">描述 (description)</span>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="简要描述模板用途"
              className="min-h-[60px]"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">中文描述 (description_zh)</span>
            <Textarea
              value={descriptionZh}
              onChange={(e) => setDescriptionZh(e.target.value)}
              placeholder="中文用户可见的描述"
              className="min-h-[60px]"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">System Prompt</span>
            <Textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="Agent 系统提示词..."
              className="min-h-[120px]"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">模型层级 (model_tier)</span>
            <select
              value={modelTier}
              onChange={(e) => setModelTier(e.target.value)}
              className="h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {MODEL_TIERS.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </label>
        </div>

        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button variant="brand" size="sm" onClick={handleSave} disabled={saving}>
            {saving ? <Spinner /> : null}
            {isEditing ? '保存' : '创建'}
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}
