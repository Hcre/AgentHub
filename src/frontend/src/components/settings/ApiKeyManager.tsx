import { useState } from 'react'
import { useApiKeyStore, PROVIDER_LABELS } from '../../stores/apiKeyStore'
import { useUIStore } from '../../stores/uiStore'
import { Button, Dialog, DialogContent, Icon, Input } from '../ui'

const SELECT_CLS =
  'h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring'

const PROVIDERS = [
  { id: 'deepseek', label: 'DeepSeek' },
  { id: 'openai', label: 'OpenAI' },
  { id: 'anthropic', label: 'Anthropic' },
  { id: 'siliconflow', label: '硅基流动' },
  { id: 'other', label: '其他' },
]

function ApiKeyDialog({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const addKey = useApiKeyStore((s) => s.addKey)
  const [name, setName] = useState('')
  const [provider, setProvider] = useState('deepseek')
  const [apiKey, setApiKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [model, setModel] = useState('')

  const save = () => {
    if (!name.trim() || !apiKey.trim()) return
    addKey({ name, provider, apiKey, baseUrl, model })
    setName(''); setProvider('deepseek'); setApiKey('')
    setBaseUrl(''); setModel('')
    onClose()
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-[15px] font-medium">添加 Provider 配置</h3>
          <Button variant="ghost" size="iconSm" onClick={onClose}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>
        <div className="flex flex-col gap-3 overflow-y-auto p-4" style={{ maxHeight: '60vh' }}>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">配置名称 *</span>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="如 我的 DeepSeek V3" autoFocus />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">提供商 *</span>
            <select value={provider} onChange={(e) => setProvider(e.target.value)} className={SELECT_CLS}>
              {PROVIDERS.map((p) => (<option key={p.id} value={p.id}>{p.label}</option>))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">API Key *</span>
            <Input value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="sk-..." type="password" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">请求地址（Base URL）</span>
            <Input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="如 https://api.deepseek.com/anthropic" />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">首选模型</span>
            <Input value={model} onChange={(e) => setModel(e.target.value)} placeholder="如 deepseek-chat" />
          </label>
        </div>
        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={onClose}>取消</Button>
          <Button variant="brand" size="sm" onClick={save} disabled={!name.trim() || !apiKey.trim()}>
            保存
          </Button>
        </footer>
      </DialogContent>
    </Dialog>
  )
}

export function ApiKeyManager() {
  const setSection = useUIStore((s) => s.setSection)
  const keys = useApiKeyStore((s) => s.keys)
  const removeKey = useApiKeyStore((s) => s.removeKey)
  const [dialogOpen, setDialogOpen] = useState(false)

  return (
    <div className="flex h-full flex-col bg-background">
      <header className="flex items-center gap-3 border-b px-4 py-3">
        <Button variant="ghost" size="iconSm" onClick={() => setSection('chat')}>
          <Icon name="chevronLeft" className="h-4 w-4" />
        </Button>
        <div className="flex-1">
          <h2 className="text-[15px] font-medium">Provider 配置</h2>
          <p className="text-[11px] text-muted-foreground">配置仅存储在本浏览器，不会上传到服务器</p>
        </div>
        <Button variant="brand" size="sm" onClick={() => setDialogOpen(true)}>
          <Icon name="plus" className="h-3 w-3" />
          <span className="ml-1 text-[12px]">添加配置</span>
        </Button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {keys.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Icon name="shieldCheck" className="mb-2 h-8 w-8 text-muted-foreground/30" />
            <p className="text-[13px] text-muted-foreground">还没有保存的 Provider 配置</p>
            <p className="mt-1 text-[11px] text-muted-foreground/60">
              添加后创建 Agent 时可直接选择，无需重复填写
            </p>
          </div>
        ) : (
          <div className="mx-auto max-w-xl space-y-2">
            {keys.map((k) => (
              <div key={k.id} className="flex items-start gap-3 rounded-lg border-2 border-border bg-card p-3.5 shadow-sm">
                <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md bg-muted text-[13px]">🔑</div>
                <div className="min-w-0 flex-1">
                  <div className="text-[13px] font-medium">{k.name}</div>
                  <div className="mt-0.5 text-[11px] text-muted-foreground space-y-0.5">
                    <div>{PROVIDER_LABELS[k.provider] ?? k.provider}{' · '}{k.keyPrefix}****</div>
                    {k.model && <div>模型: {k.model}</div>}
                    {k.baseUrl && <div className="truncate">地址: {k.baseUrl}</div>}
                  </div>
                </div>
                <Button variant="ghost" size="iconSm" onClick={() => removeKey(k.id)} className="text-muted-foreground hover:text-red-500 flex-shrink-0">
                  <Icon name="x" className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      <ApiKeyDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
    </div>
  )
}
