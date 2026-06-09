import { useState, type KeyboardEvent } from 'react'
import { Button, Dialog, DialogContent, Icon, Input, Textarea } from '../ui'
import { cn } from '../../lib/cn'
import { skillsApi } from '../../api/skills'

function Spinner() {
  return (
    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  )
}

type CreateTab = 'quick' | 'ai' | 'guided'

interface GeneratedFields {
  name: string
  description: string
  triggers: string[]
  instructions: string
}

export interface CreateSkillDialogProps {
  open: boolean
  onClose: () => void
  /** Optional callback when a skill was created successfully */
  onCreated?: () => void
}

export function CreateSkillDialog({ open, onClose, onCreated }: CreateSkillDialogProps) {
  const [activeTab, setActiveTab] = useState<CreateTab>('quick')

  // Quick create form
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [triggers, setTriggers] = useState<string[]>([])
  const [triggerInput, setTriggerInput] = useState('')
  const [instructions, setInstructions] = useState('')
  const [examples, setExamples] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  // AI generate state
  const [aiPrompt, setAiPrompt] = useState('')
  const [generating, setGenerating] = useState(false)
  const [generated, setGenerated] = useState<GeneratedFields | null>(null)

  const reset = () => {
    setName('')
    setDescription('')
    setTriggers([])
    setTriggerInput('')
    setInstructions('')
    setExamples('')
    setSaving(false)
    setError('')
    setAiPrompt('')
    setGenerating(false)
    setGenerated(null)
    setActiveTab('quick')
  }

  const handleClose = () => {
    if (saving || generating) return
    reset()
    onClose()
  }

  const addTrigger = () => {
    const t = triggerInput.trim()
    if (t && !triggers.includes(t)) {
      setTriggers([...triggers, t])
    }
    setTriggerInput('')
  }

  const removeTrigger = (t: string) => {
    setTriggers(triggers.filter((x) => x !== t))
  }

  const handleTriggerKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      addTrigger()
    }
  }

  const handleCreate = async () => {
    if (!name.trim()) {
      setError('名称不能为空')
      return
    }
    if (!description.trim()) {
      setError('描述不能为空')
      return
    }
    setSaving(true)
    setError('')
    try {
      // Parse examples as array of strings
      const exampleList = examples.trim()
        ? examples.split('\n').filter((l) => l.trim())
        : []

      await skillsApi.createLibrary({
        name: name.trim(),
        description: description.trim(),
        triggers,
        instructions: instructions.trim(),
        examples: exampleList,
      })
      reset()
      onClose()
      onCreated?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : '创建失败')
    } finally {
      setSaving(false)
    }
  }

  const handleGenerate = async () => {
    if (!aiPrompt.trim()) {
      setError('请输入 skill 描述')
      return
    }
    setGenerating(true)
    setError('')
    setGenerated(null)
    try {
      const data = await skillsApi.generateLibrary(aiPrompt.trim())
      // Pre-fill form fields from generated data
      const fields: GeneratedFields = {
        name: data.name || '',
        description: data.description || aiPrompt.trim(),
        triggers: data.triggers || [],
        instructions: data.instructions || '',
      }
      setGenerated(fields)
      setName(fields.name)
      setDescription(fields.description)
      setTriggers(fields.triggers)
      setInstructions(fields.instructions)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'AI 生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const handleGuidedStart = () => {
    // Close dialog - parent can handle navigation to CreateAgentModal
    onClose()
  }

  if (!open) return null

  const tabClass = (tab: CreateTab) =>
    cn(
      'rounded-md px-3 py-1.5 text-[12.5px] transition-colors',
      activeTab === tab
        ? 'bg-brand/15 text-brand font-medium'
        : 'text-muted-foreground hover:text-foreground',
    )

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent className="w-[600px]">
        {/* Header */}
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-[15px] font-medium">创建 Skill</h3>
          <Button variant="ghost" size="iconSm" onClick={handleClose}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        {/* Tab bar */}
        <div className="flex items-center gap-1 border-b border-border/60 px-4 py-2">
          <button type="button" onClick={() => setActiveTab('quick')} className={tabClass('quick')}>
            <Icon name="zap" className="h-3 w-3 mr-1 inline" />
            快速创建
          </button>
          <button type="button" onClick={() => setActiveTab('ai')} className={tabClass('ai')}>
            <Icon name="sparkle" className="h-3 w-3 mr-1 inline" />
            AI 生成
          </button>
          <button type="button" onClick={() => setActiveTab('guided')} className={tabClass('guided')}>
            <Icon name="users" className="h-3 w-3 mr-1 inline" />
            AI 助手引导
          </button>
        </div>

        {/* Content area */}
        <div className="flex flex-col gap-3 overflow-y-auto p-4" style={{ maxHeight: '55vh' }}>
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
              {error}
            </div>
          )}

          {/* ── Tab 1: Quick Create ── */}
          {activeTab === 'quick' && (
            <>
              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-muted-foreground">名称</span>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="my-skill"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-muted-foreground">描述</span>
                <Textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="一句话描述 skill 功能"
                  className="min-h-[60px]"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-muted-foreground">触发词</span>
                <div className="flex items-center gap-1">
                  <Input
                    value={triggerInput}
                    onChange={(e) => setTriggerInput(e.target.value)}
                    onKeyDown={handleTriggerKeyDown}
                    placeholder="输入触发词后按 Enter 添加"
                  />
                  <Button variant="outline" size="sm" onClick={addTrigger} type="button">
                    <Icon name="plus" className="h-3 w-3" />
                  </Button>
                </div>
                {triggers.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {triggers.map((t) => (
                      <span
                        key={t}
                        className="inline-flex items-center gap-1 rounded bg-muted/60 px-2 py-0.5 text-[11px]"
                      >
                        {t}
                        <button
                          type="button"
                          onClick={() => removeTrigger(t)}
                          className="ml-0.5 text-muted-foreground hover:text-foreground"
                        >
                          <Icon name="x" className="h-2.5 w-2.5" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-muted-foreground">指令</span>
                <Textarea
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="执行步骤..."
                  className="min-h-[120px]"
                />
              </label>

              <label className="flex flex-col gap-1">
                <span className="text-[12px] font-medium text-muted-foreground">示例</span>
                <Textarea
                  value={examples}
                  onChange={(e) => setExamples(e.target.value)}
                  placeholder="示例对话..."
                  className="min-h-[80px]"
                />
              </label>
            </>
          )}

          {/* ── Tab 2: AI Generate ── */}
          {activeTab === 'ai' && (
            <>
              {!generated ? (
                <>
                  <label className="flex flex-col gap-1">
                    <span className="text-[12px] font-medium text-muted-foreground">
                      用自然语言描述你想创建的 skill
                    </span>
                    <Textarea
                      value={aiPrompt}
                      onChange={(e) => setAiPrompt(e.target.value)}
                      placeholder="例如：创建一个帮我写小红书爆款标题的 skill，需要分析爆款规律并生成 5 个候选标题..."
                      className="min-h-[140px]"
                    />
                  </label>

                  <Button
                    variant="brand"
                    size="sm"
                    onClick={handleGenerate}
                    disabled={generating || !aiPrompt.trim()}
                    className="self-start"
                  >
                    {generating ? (
                      <>
                        <Spinner />
                        生成中…
                      </>
                    ) : (
                      <>
                        <Icon name="sparkle" className="h-3.5 w-3.5" />
                        生成
                      </>
                    )}
                  </Button>
                </>
              ) : (
                <>
                  <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-700">
                    AI 已生成以下内容，你可以编辑后保存
                  </div>

                  <label className="flex flex-col gap-1">
                    <span className="text-[12px] font-medium text-muted-foreground">名称</span>
                    <Input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="my-skill"
                    />
                  </label>

                  <label className="flex flex-col gap-1">
                    <span className="text-[12px] font-medium text-muted-foreground">描述</span>
                    <Textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="一句话描述 skill 功能"
                      className="min-h-[60px]"
                    />
                  </label>

                  <label className="flex flex-col gap-1">
                    <span className="text-[12px] font-medium text-muted-foreground">触发词</span>
                    <div className="flex items-center gap-1">
                      <Input
                        value={triggerInput}
                        onChange={(e) => setTriggerInput(e.target.value)}
                        onKeyDown={handleTriggerKeyDown}
                        placeholder="输入触发词后按 Enter 添加"
                      />
                      <Button variant="outline" size="sm" onClick={addTrigger} type="button">
                        <Icon name="plus" className="h-3 w-3" />
                      </Button>
                    </div>
                    {triggers.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {triggers.map((t) => (
                          <span
                            key={t}
                            className="inline-flex items-center gap-1 rounded bg-muted/60 px-2 py-0.5 text-[11px]"
                          >
                            {t}
                            <button
                              type="button"
                              onClick={() => removeTrigger(t)}
                              className="ml-0.5 text-muted-foreground hover:text-foreground"
                            >
                              <Icon name="x" className="h-2.5 w-2.5" />
                            </button>
                          </span>
                        ))}
                      </div>
                    )}
                  </label>

                  <label className="flex flex-col gap-1">
                    <span className="text-[12px] font-medium text-muted-foreground">指令</span>
                    <Textarea
                      value={instructions}
                      onChange={(e) => setInstructions(e.target.value)}
                      placeholder="执行步骤..."
                      className="min-h-[120px]"
                    />
                  </label>
                </>
              )}
            </>
          )}

          {/* ── Tab 3: Guided by AI ── */}
          {activeTab === 'guided' && (
            <div className="flex flex-col gap-4">
              <div className="rounded-lg border border-border/60 p-4 space-y-3">
                <div className="flex items-start gap-3">
                  <div className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full bg-brand/10 text-brand">
                    <Icon name="brain" className="h-4 w-4" />
                  </div>
                  <div>
                    <h4 className="text-[13px] font-medium">AI 助手引导创建</h4>
                    <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                      选择一个 Skill 设计师 Agent，通过对话来描述你的需求。
                      AI 助手会逐步引导你完成 Skill 的创建过程，
                      包括确定触发词、编写指令和示例。
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3">
                  <div className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-full bg-sage/10 text-sage">
                    <Icon name="listCheck" className="h-4 w-4" />
                  </div>
                  <div>
                    <h4 className="text-[13px] font-medium">对话式工作流</h4>
                    <ul className="mt-1 space-y-1 text-[12px] text-muted-foreground">
                      <li>1. 描述你想创建的 Skill 类型和用途</li>
                      <li>2. AI 帮你完善触发词和指令</li>
                      <li>3. 实时预览并调整生成的 Skill 内容</li>
                      <li>4. 确认后一键保存到本地 Skill 库</li>
                    </ul>
                  </div>
                </div>
              </div>

              <Button
                variant="brand"
                size="sm"
                onClick={handleGuidedStart}
                className="self-center"
              >
                <Icon name="rocket" className="h-3.5 w-3.5" />
                开始对话创建
              </Button>
            </div>
          )}
        </div>

        {/* Footer */}
        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={handleClose}>
            取消
          </Button>
          {(activeTab === 'quick' || (activeTab === 'ai' && generated)) && (
            <Button variant="brand" size="sm" onClick={handleCreate} disabled={saving}>
              {saving ? (
                <>
                  <Spinner />
                  保存中…
                </>
              ) : (
                <>
                  <Icon name="check" className="h-3.5 w-3.5" />
                  保存
                </>
              )}
            </Button>
          )}
          {activeTab === 'ai' && !generated && (
            <Button
              variant="brand"
              size="sm"
              onClick={handleGenerate}
              disabled={generating || !aiPrompt.trim()}
            >
              {generating ? (
                <>
                  <Spinner />
                  生成中…
                </>
              ) : (
                <>
                  <Icon name="sparkle" className="h-3.5 w-3.5" />
                  生成
                </>
              )}
            </Button>
          )}
        </footer>
      </DialogContent>
    </Dialog>
  )
}
