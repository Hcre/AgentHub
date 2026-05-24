import { useState } from 'react'
import { PROVIDER_BASE_URL, providers } from '../../data/extra'
import { useAgentStore } from '../../stores/agentStore'
import { useUIStore } from '../../stores/uiStore'
import { Button, Dialog, DialogContent, Icon, Input, Textarea } from '../ui'

const SELECT_CLS =
  'h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring'

/** 运行时选项。openai_api 未实现（后端落 mock），暂不暴露。 */
const RUNTIMES: { id: string; label: string }[] = [
  { id: 'anthropic_api', label: 'Anthropic API · 直连（首选）' },
  { id: 'claude_code', label: 'Claude Code · CLI 代理（接入第三方）' },
  { id: 'mock', label: 'Mock · 演示假数据' },
]

const DEFAULT_PROVIDER = providers[0]?.id ?? 'anthropic'

function Label({ children }: { children: string }) {
  return <span className="text-[12px] font-medium text-muted-foreground">{children}</span>
}

export function CreateAgentModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const createAgent = useAgentStore((s) => s.createAgent)
  const openConversation = useUIStore((s) => s.openConversation)
  const [name, setName] = useState('')
  const [role, setRole] = useState('')
  const [agentSystem, setAgentSystem] = useState('anthropic_api')
  const [providerId, setProviderId] = useState(DEFAULT_PROVIDER)
  const [model, setModel] = useState(providers[0]?.models[0] ?? '')
  const [baseUrl, setBaseUrl] = useState(PROVIDER_BASE_URL[DEFAULT_PROVIDER] ?? '')
  const [apiKey, setApiKey] = useState('')
  const [skills, setSkills] = useState('')
  const [systemPrompt, setSystemPrompt] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const provider = providers.find((p) => p.id === providerId) ?? providers[0]
  const showBaseUrl = agentSystem === 'claude_code'

  const reset = () => {
    setName('')
    setRole('')
    setAgentSystem('anthropic_api')
    setProviderId(DEFAULT_PROVIDER)
    setModel(providers[0]?.models[0] ?? '')
    setBaseUrl(PROVIDER_BASE_URL[DEFAULT_PROVIDER] ?? '')
    setApiKey('')
    setSkills('')
    setSystemPrompt('')
  }

  const onProviderChange = (id: string) => {
    setProviderId(id)
    const p = providers.find((x) => x.id === id)
    setModel(p?.models[0] ?? '')
    setBaseUrl(PROVIDER_BASE_URL[id] ?? '')
  }

  const submit = async () => {
    if (!name.trim() || !role.trim() || submitting) return
    setSubmitting(true)
    try {
      const id = await createAgent({
        name: name.trim(),
        role: role.trim(),
        agentSystem,
        provider: providerId,
        model,
        baseUrl: showBaseUrl ? baseUrl.trim() : undefined,
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
    } finally {
      setSubmitting(false)
    }
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

          <label className="flex flex-col gap-1">
            <Label>运行时</Label>
            <select
              className={SELECT_CLS}
              value={agentSystem}
              onChange={(e) => setAgentSystem(e.target.value)}
            >
              {RUNTIMES.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <Label>Provider</Label>
              <select
                className={SELECT_CLS}
                value={providerId}
                onChange={(e) => onProviderChange(e.target.value)}
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

          {showBaseUrl && (
            <label className="flex flex-col gap-1">
              <Label>Base URL（须为 Anthropic 兼容端点）</Label>
              <Input
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder="https://api.deepseek.com/anthropic"
              />
            </label>
          )}

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
            disabled={!name.trim() || !role.trim() || submitting}
          >
            创建
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}
