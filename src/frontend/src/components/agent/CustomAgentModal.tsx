import { useEffect, useState } from 'react'
import { useUIStore } from '../../stores/uiStore'
import { Button, Dialog, DialogContent, Icon, Input, Textarea } from '../ui'

interface SkillItem {
  name: string
  path: string
  source: string
}

function Label({ children }: { children: string }) {
  return <span className="text-[12px] font-medium text-muted-foreground">{children}</span>
}

let customDraft: { name: string; prompt: string; skills: string[] } | null = null

export function CustomAgentModal({
  open,
  onClose,
  onConfirm,
}: {
  open: boolean
  onClose: () => void
  onConfirm: (data: { name: string; systemPrompt: string; skills: string[] }) => void
}) {
  const [name, setName] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const setSection = useUIStore((s) => s.setSection)
  const [selectedSkills, setSelectedSkills] = useState<Set<string>>(new Set())
  const [skills, setSkills] = useState<SkillItem[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    // setState 推迟到 microtask 避开 react-hooks/set-state-in-effect
    queueMicrotask(() => {
      setLoading(true)
      fetch('/api/skills/library?_=' + Date.now())
        .then((r) => r.json())
        .then(setSkills)
        .catch(() => setSkills([]))
        .finally(() => setLoading(false))
      if (customDraft) {
        setName(customDraft.name)
        setSystemPrompt(customDraft.prompt)
        setSelectedSkills(new Set(customDraft.skills))
        customDraft = null
      }
    })
  }, [open])

  const toggleSkill = (name: string) => {
    setSelectedSkills((prev) => {
      const next = new Set(prev)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const handleConfirm = () => {
    if (!name.trim()) return
    onConfirm({
      name: name.trim(),
      systemPrompt: systemPrompt.trim(),
      skills: [...selectedSkills],
    })
    setName('')
    setSystemPrompt('')
    setSelectedSkills(new Set())
    onClose()
  }

  const handleClose = () => {
    setName('')
    setSystemPrompt('')
    setSelectedSkills(new Set())
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent>
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-[15px] font-medium">创建自定义 AI 队友</h3>
          <Button variant="ghost" size="iconSm" onClick={handleClose}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        <div className="flex flex-col gap-3 overflow-y-auto p-4" style={{ maxHeight: '60vh' }}>
          <label className="flex flex-col gap-1">
            <Label>队友名称 *</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="如 代码审查员"
              autoFocus
            />
          </label>

          <label className="flex flex-col gap-1">
            <Label>职责描述（System Prompt）</Label>
            <Textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="描述这个队友的职责与边界…"
              className="min-h-[72px]"
            />
          </label>

          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <Label>Skill</Label>
              <button
                type="button"
                onClick={() => {
                  customDraft = { name, prompt: systemPrompt, skills: [...selectedSkills] }
                  onClose()
                  setTimeout(() => setSection('skills-market'), 0)
                }}
                className="text-[11px] text-brand hover:underline"
              >
                浏览技能市场 →
              </button>
            </div>
            {loading ? (
              <span className="text-[12px] text-muted-foreground">加载中…</span>
            ) : skills.length === 0 ? (
              <span className="text-[12px] text-muted-foreground">暂无可用 Skill</span>
            ) : (
              <div className="flex flex-col gap-1 rounded-md border p-2">
                {skills.map((s) => (
                  <label
                    key={s.name}
                    className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-[13px] hover:bg-accent"
                  >
                    <input
                      type="checkbox"
                      checked={selectedSkills.has(s.name)}
                      onChange={() => toggleSkill(s.name)}
                      className="h-3.5 w-3.5 accent-brand"
                    />
                    <span>{s.name.replace('.md', '')}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        </div>

        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={handleClose}>
            取消
          </Button>
          <Button variant="brand" size="sm" onClick={handleConfirm} disabled={!name.trim()}>
            确认
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}
