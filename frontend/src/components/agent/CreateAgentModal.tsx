import { useState } from 'react'
import { providers } from '../../data/extra'
import { useAgentStore } from '../../stores/agentStore'
import { useChatStore } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { Button, Dialog, DialogContent, Icon, Input, Textarea } from '../ui'
import { agentsApi } from '../../api/agents'
import { sessionsApi } from '../../api/sessions'

const SELECT_CLS =
  'h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring'

const RUNTIMES = [
  { id: 'claude_code', label: 'Claude CLI · 代理接入第三方' },
  { id: 'mock', label: 'Mock · 演示假数据' },
]

// --- Step 1 模板 ---
interface Template {
  name: string
  systemPrompt: string
}

const TEMPLATES: Template[] = [
  {
    name: '技术负责人',
    systemPrompt: '拆任务、排顺序、盯风险，协调工程师、评审和测试交付结果。',
  },
  {
    name: '工程师',
    systemPrompt: '接需求、写代码、上线。修 bug 比写代码还熟。',
  },
  {
    name: '代码评审',
    systemPrompt: '审 diff、提风险、走查测试、把合并前最后一道关。',
  },
  {
    name: '测试',
    systemPrompt: '复现问题、跑验收、做回归，把用户路径测到真的能用。',
  },
  {
    name: '产品经理',
    systemPrompt: '定方向、拆需求、写 PRD、推进交付。',
  },
  {
    name: '文案',
    systemPrompt: '写公众号、邮件、品牌稿。卖点和故事都能写。',
  },
  {
    name: '编辑',
    systemPrompt: '调语气、改结构、控篇幅，把稿子打磨到能发。',
  },
  {
    name: '外联文案',
    systemPrompt: '陌拜信、跟进序列、销售话术都他写。盯回复率反复优化。',
  },
]

function Label({ children }: { children: string }) {
  return <span className="text-[12px] font-medium text-muted-foreground">{children}</span>
}

export function CreateAgentModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const createAgent = useAgentStore((s) => s.createAgent)
  const removeAgent = useAgentStore((s) => s.removeAgent)
  const addConversation = useChatStore((s) => s.addConversation)
  const openConversation = useUIStore((s) => s.openConversation)

  // Wizard state
  const [step, setStep] = useState(1)
  // Step 1
  const [pickedIndex, setPickedIndex] = useState<number | null>(null)
  const [customName, setCustomName] = useState('')
  const [customPrompt, setCustomPrompt] = useState('')
  // Step 2
  const [agentSystem, setAgentSystem] = useState('claude_code')
  const [providerId, setProviderId] = useState('deepseek')
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  // Step 3
  const [status, setStatus] = useState<'creating' | 'success' | 'error'>('creating')
  const [errorMsg, setErrorMsg] = useState('')

  const isCustom = pickedIndex === TEMPLATES.length
  const selectedTemplate = pickedIndex !== null && pickedIndex < TEMPLATES.length ? TEMPLATES[pickedIndex] : null
  const agentName = isCustom ? customName : (selectedTemplate?.name ?? '')
  const agentSystemPrompt = isCustom ? customPrompt : (selectedTemplate?.systemPrompt ?? '')

  const showProviderSection = agentSystem === 'claude_code'

  const reset = () => {
    setStep(1)
    setPickedIndex(null)
    setCustomName('')
    setCustomPrompt('')
    setAgentSystem('claude_code')
    setProviderId('deepseek')
    setModel('')
    setBaseUrl('')
    setApiKey('')
    setStatus('creating')
    setErrorMsg('')
  }

  const handleClose = () => {
    if (status === 'creating') return
    reset()
    onClose()
  }

  // Step 1 → Step 2
  const canNext = (() => {
    if (pickedIndex === null) return false
    if (isCustom && (!customName.trim() || !customPrompt.trim())) return false
    return true
  })()

  const goNext = () => {
    if (!canNext) return
    // 模板套用 deepseek / claude_code / deepseek-chat 作为默认
    setAgentSystem('claude_code')
    setProviderId('deepseek')
    setModel('deepseek-chat')
    setBaseUrl('')
    setApiKey('')
    setStep(2)
  }

  const goBack = () => setStep(1)

  // Step 3: create + connectivity test
  const doCreate = async () => {
    if (!agentName.trim()) return
    setStep(3)
    setStatus('creating')
    setErrorMsg('')
    try {
      // 1. 创建 Agent
      const id = await createAgent({
        name: agentName.trim(),
        role: agentName.trim(),
        agentSystem,
        provider: providerId,
        model: showProviderSection ? model.trim() : '',
        baseUrl: showProviderSection ? baseUrl.trim() || undefined : undefined,
        apiKey,
        skills: [],
        systemPrompt: agentSystemPrompt,
      })

      // 2. 连通性测试：创建临时 Session 发一条测试消息
      if (agentSystem === 'claude_code' && apiKey) {
        try {
          const session = await sessionsApi.createPrivate(id)
          await new Promise<void>((resolve, reject) => {
            const timeout = setTimeout(() => reject(new Error('连通性测试超时（30s）')), 30000)
            const ws = new WebSocket(`ws://${window.location.host}/ws/sessions/${session.id}`)
            ws.onopen = () => {
              ws.send(JSON.stringify({ type: 'message', content: 'ping' }))
            }
            let testBuffer = ''
            ws.onmessage = (evt) => {
              const d = JSON.parse(evt.data)
              if (d.type === 'text') {
                testBuffer += (d.content ?? '')
              }
              if (d.type === 'done') {
                clearTimeout(timeout)
                ws.close()
                const meta = d.metadata ?? {}
                if (meta.is_error) {
                  const errs = meta.errors ?? []
                  reject(new Error(errs[0] ?? testBuffer.trim() ?? '连通性测试失败'))
                } else {
                  resolve()
                }
              }
              if (d.type === 'error') {
                clearTimeout(timeout)
                ws.close()
                reject(new Error(d.content ?? '连通性测试失败'))
              }
            }
            ws.onerror = () => {
              clearTimeout(timeout)
              ws.close()
              reject(new Error('WebSocket 连接失败'))
            }
          })
        } catch (pingErr) {
          // 连通性失败 → 回滚：后端删除（仅 UUID）+ 前端移除
          if (/^[0-9a-f]{8}-/.test(id)) {
            try { await agentsApi.remove(id) } catch { /* ignore */ }
          }
          await removeAgent(id)
          setStatus('error')
          setErrorMsg(pingErr instanceof Error ? pingErr.message : '连通性验证失败，已回滚')
          return
        }
      }

      // 3. 成功：创建本地对话并打开
      const convId = addConversation(id)
      setStatus('success')
      setTimeout(() => {
        reset()
        onClose()
        openConversation(id, convId)
      }, 1000)
    } catch (e) {
      setStatus('error')
      const msg = e instanceof Error ? e.message : '创建失败'
      // 提取 API 错误详情
      const detail = msg.replace(/^API \d+: /, '')
      setErrorMsg(detail.length < 200 ? detail : '创建失败，请检查配置')
    }
  }

  const doRetry = () => {
    setStatus('creating')
    doCreate()
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && handleClose()}>
      <DialogContent>
        {/* === Step 1: 选模板 === */}
        {step === 1 && (
          <>
            <header className="flex items-center justify-between border-b px-4 py-3">
              <h3 className="text-[15px] font-medium">创建你的新 AI 队友</h3>
              <Button variant="ghost" size="iconSm" onClick={handleClose}>
                <Icon name="x" className="h-3.5 w-3.5" />
              </Button>
            </header>

            <div className="flex flex-col gap-3 overflow-y-auto p-4" style={{ maxHeight: '60vh' }}>
              <p className="text-[13px] text-muted-foreground">第一步：选择队友模板</p>

              <div className="grid grid-cols-2 gap-2">
                {TEMPLATES.map((t, i) => {
                  const picked = pickedIndex === i
                  return (
                    <button
                      key={t.name}
                      onClick={() => setPickedIndex(i)}
                      data-picked={picked ? 'true' : undefined}
                      className="flex flex-col gap-1 rounded-lg border p-3 text-left transition-colors hover:border-brand/40 data-[picked=true]:border-brand data-[picked=true]:bg-brand/5"
                    >
                      <span className="text-[13px] font-medium">{t.name}</span>
                      <span className="line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                        {t.systemPrompt}
                      </span>
                    </button>
                  )
                })}
                <button
                  onClick={() => setPickedIndex(TEMPLATES.length)}
                  data-picked={isCustom ? 'true' : undefined}
                  className="flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed p-3 text-muted-foreground transition-colors hover:border-brand/40 hover:text-brand data-[picked=true]:border-brand data-[picked=true]:bg-brand/5 data-[picked=true]:text-brand"
                >
                  <Icon name="plus" className="h-5 w-5" />
                  <span className="text-[12px]">自定义</span>
                </button>
              </div>

              {isCustom && (
                <div className="flex flex-col gap-3 rounded-lg border p-3">
                  <Input
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    placeholder="队友名称"
                    autoFocus
                  />
                  <Textarea
                    value={customPrompt}
                    onChange={(e) => setCustomPrompt(e.target.value)}
                    placeholder="描述这个队友的职责与边界（system prompt）…"
                    className="min-h-[60px]"
                  />
                </div>
              )}
            </div>

            <footer className="flex justify-end gap-2 border-t px-4 py-3">
              <Button variant="outline" size="sm" onClick={handleClose}>
                取消
              </Button>
              <Button variant="brand" size="sm" onClick={goNext} disabled={!canNext}>
                下一步
              </Button>
            </footer>
          </>
        )}

        {/* === Step 2: 配置 === */}
        {step === 2 && (
          <>
            <header className="flex items-center justify-between border-b px-4 py-3">
              <div className="flex items-center gap-2">
                <Button variant="ghost" size="iconSm" onClick={goBack} title="返回">
                  <Icon name="chevronLeft" className="h-3.5 w-3.5" />
                </Button>
                <h3 className="text-[15px] font-medium">配置 "{agentName}"</h3>
              </div>
              <Button variant="ghost" size="iconSm" onClick={handleClose}>
                <Icon name="x" className="h-3.5 w-3.5" />
              </Button>
            </header>

            <div className="flex flex-col gap-3 overflow-y-auto p-4" style={{ maxHeight: '60vh' }}>
              <p className="text-[13px] text-muted-foreground">第二步：填写配置信息</p>

              <label className="flex flex-col gap-1">
                <Label>运行依赖</Label>
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

              {showProviderSection && (
                <>
                  <label className="flex flex-col gap-1">
                    <Label>提供商</Label>
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
                    <Input
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                      placeholder="例如 deepseek-chat"
                    />
                  </label>

                  <label className="flex flex-col gap-1">
                    <Label>请求地址（Base URL，须为 Anthropic 兼容端点）</Label>
                    <Input
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder="例如 https://api.deepseek.com/anthropic"
                    />
                  </label>

                  <label className="flex flex-col gap-1">
                    <Label>API Key</Label>
                    <Input
                      type="password"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      placeholder="sk-…（加密传输）"
                    />
                  </label>
                </>
              )}
            </div>

            <footer className="flex justify-end gap-2 border-t px-4 py-3">
              <Button variant="outline" size="sm" onClick={goBack}>
                上一步
              </Button>
              <Button variant="brand" size="sm" onClick={doCreate}>
                创建队友
              </Button>
            </footer>
          </>
        )}

        {/* === Step 3: 上线中 === */}
        {step === 3 && (
          <div className="flex flex-col items-center justify-center gap-4 px-6 py-12">
            {status === 'creating' && (
              <>
                <div className="grid h-12 w-12 place-items-center">
                  <svg
                    className="animate-spin h-8 w-8 text-brand"
                    viewBox="0 0 24 24"
                    fill="none"
                  >
                    <circle
                      className="opacity-25"
                      cx="12"
                      cy="12"
                      r="10"
                      stroke="currentColor"
                      strokeWidth="4"
                    />
                    <path
                      className="opacity-75"
                      fill="currentColor"
                      d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                    />
                  </svg>
                </div>
                <div className="text-center">
                  <p className="text-[15px] font-medium">你的队友 "{agentName}" 上线中…</p>
                  <p className="mt-1 text-[12px] text-muted-foreground">正在配置并验证连通性，请稍候</p>
                </div>
              </>
            )}

            {status === 'success' && (
              <>
                <div className="grid h-12 w-12 place-items-center rounded-full bg-emerald-100 text-emerald-600">
                  <Icon name="check" className="h-6 w-6" />
                </div>
                <p className="text-[15px] font-medium">"{agentName}" 已上线！</p>
              </>
            )}

            {status === 'error' && (
              <>
                <div className="grid h-12 w-12 place-items-center rounded-full bg-red-100 text-red-500">
                  <Icon name="x" className="h-6 w-6" />
                </div>
                <div className="text-center">
                  <p className="text-[15px] font-medium">配置失败</p>
                  <p className="mt-1 text-[12px] text-muted-foreground">{errorMsg || '未知错误'}</p>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handleClose}>
                    关闭
                  </Button>
                  <Button variant="brand" size="sm" onClick={doRetry}>
                    重试
                  </Button>
                </div>
              </>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
