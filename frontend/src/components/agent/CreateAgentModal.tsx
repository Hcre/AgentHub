import { useState } from 'react'
import { providers } from '../../data/extra'
import { useAgentStore } from '../../stores/agentStore'
import { useUIStore } from '../../stores/uiStore'
import { Button, Dialog, DialogContent, Icon, Input, Textarea } from '../ui'

const SELECT_CLS =
  'h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring'

function Label({ children }: { children: string }) {
  return <span className="text-[12px] font-medium text-muted-foreground">{children}</span>
}

export function CreateAgentModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const createAgent = useAgentStore((s) => s.createAgent)
  const openConversation = useUIStore((s) => s.openConversation)
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [providerId, setProviderId] = useState(providers[0]?.id ?? 'anthropic')
  const [model, setModel] = useState(providers[0]?.models[0] ?? '')
  const [apiKey, setApiKey] = useState('')
  const [skills, setSkills] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')

  const provider = providers.find((p) => p.id === providerId) ?? providers[0]

  const reset = () => {
    setName('')
    setRole('')
    setProviderId(providers[0]?.id ?? 'anthropic')
    setModel(providers[0]?.models[0] ?? '')
    setApiKey('')
    setSkills('')
    setSystemPrompt('')
  }

  const submit = () => {
    if (!name.trim() || !role.trim()) return
    const id = createAgent({
      name: name.trim(),
      role: role.trim(),
      provider: providerId,
      model,
      apiKey,
      skills: skills
        .split(/[,，\s]+/)
        .map((s) => s.trim())
        .filter(Boolean),
      systemPrompt,
    })
    reset()
    onClose()
    openConversation(id, 'c1')
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-[15px] font-medium">创建助手</h3>
          <Button variant="ghost" size="iconSm" onClick={onClose}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        <div className="flex flex-col gap-3 overflow-y-auto p-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <Label>名称 *</Label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="如 译者"
                autoFocus
              />
            </label>
            <label className="flex flex-col gap-1">
              <Label>角色 *</Label>
              <Input
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="如 Translator"
              />
            </label>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <Label>Provider</Label>
              <select
                className={SELECT_CLS}
                value={providerId}
                onChange={(e) => {
                  setProviderId(e.target.value)
                  const p = providers.find((x) => x.id === e.target.value)
                  setModel(p?.models[0] ?? '')
                }}
              >
                {providers.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <Label>Model</Label>
              <select
                className={SELECT_CLS}
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                {provider?.models.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <label className="flex flex-col gap-1">
            <Label>API Key</Label>
            <Input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-…（加密传输，不留存明文）"
            />
          </label>

          <label className="flex flex-col gap-1">
            <Label>技能（逗号分隔，可选）</Label>
            <Input
              value={skills}
              onChange={(e) => setSkills(e.target.value)}
              placeholder="如 translation, glossary"
            />
          </label>

          <label className="flex flex-col gap-1">
            <Label>System prompt（可选）</Label>
            <Textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="描述这个助手的职责与边界…"
              className="min-h-[72px]"
            />
          </label>
        </div>

        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button
            variant="brand"
            size="sm"
            onClick={submit}
            disabled={!name.trim() || !role.trim()}
          >
            创建
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}
