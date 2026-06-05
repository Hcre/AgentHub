import { useEffect, useState } from 'react'
import { providers } from '../../data/extra'
import { resolveProviderConfig } from '../../data/cliProviderMatrix'
import { useAgentStore } from '../../stores/agentStore'
import { useChatStore } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { Button, Dialog, DialogContent, Icon, Input, Textarea } from '../ui'
import { useApiKeyStore } from '../../stores/apiKeyStore'

const SELECT_CLS =
  'h-9 w-full rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring'

interface ProviderInfo {
  name: string
  display_name: string
  binary: string
  executable_path: string
  version: string | null
  adapter: string
  description: string
  available: boolean
}

// --- Step 1 模板 ---
interface Template {
  name: string
  systemPrompt: string
  skills: string[]
}

const TEMPLATES: Template[] = [
  {
    name: '技术负责人',
    systemPrompt: '拆任务、排顺序、盯风险，协调工程师、评审和测试交付结果。',
    skills: [],
  },
  {
    name: '工程师',
    systemPrompt: '接需求、写代码、上线。修 bug 比写代码还熟。',
    skills: [],
  },
  {
    name: '代码评审',
    systemPrompt: '审 diff、提风险、走查测试、把合并前最后一道关。',
    skills: [],
  },
  {
    name: '测试',
    systemPrompt: '复现问题、跑验收、做回归，把用户路径测到真的能用。',
    skills: [],
  },
  {
    name: '产品经理',
    systemPrompt: '定方向、拆需求、写 PRD、推进交付。',
    skills: [],
  },
  {
    name: '文案',
    systemPrompt: '写公众号、邮件、品牌稿。卖点和故事都能写。',
    skills: [],
  },
  {
    name: '编辑',
    systemPrompt: '调语气、改结构、控篇幅，把稿子打磨到能发。',
    skills: [],
  },
  {
    name: '外联文案',
    systemPrompt: '陌拜信、跟进序列、销售话术都他写。盯回复率反复优化。',
    skills: [],
  },
]

function Label({ children }: { children: string }) {
  return <span className="text-[12px] font-medium text-muted-foreground">{children}</span>
}

/** 跳转技能市场时暂存草稿，回来后恢复 */
let wizardDraft: { name: string; prompt: string; skills: string[] } | null = null

/** CLI provider 扫描缓存（模块级，页面不刷新则保留） */
let providerCache: ProviderInfo[] | null = null
let providerScanned = false

const DEFAULT_RUNTIMES = [
  { id: 'claude_code', label: 'Claude CLI · 代理接入第三方' },
  { id: 'pi_agent', label: 'Pi Agent · 多Provider CLI' },
  { id: 'mock', label: 'Mock · 演示假数据' },
]

function buildRuntimes(scanned: ProviderInfo[] | null, scanning: boolean): {id:string;label:string}[] {
  // 还没扫描过 → 显示硬编码兜底
  if (!scanned || scanning) return DEFAULT_RUNTIMES
  // 扫描完成 → 只显示实际检测到的 CLI + mock 兜底
  const list = scanned
    .filter(p => p.available)
    .map(p => ({ id: p.name, label: p.display_name + (p.version ? ` · ${p.version}` : '') }))
  // 始终保留 mock 作为兜底
  if (!list.find(r => r.id === 'mock')) {
    list.push({ id: 'mock', label: 'Mock · 演示假数据' })
  }
  return list.length > 0 ? list : DEFAULT_RUNTIMES
}

export function CreateAgentModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const createAgent = useAgentStore((s) => s.createAgent)
  const addConversation = useChatStore((s) => s.addConversation)
  const openConversation = useUIStore((s) => s.openConversation)
  const setSection = useUIStore((s) => s.setSection)
  const savedKeys = useApiKeyStore((s) => s.keys)

  // Wizard state
  const [scannedProviders, setScannedProviders] = useState<ProviderInfo[] | null>(null)
  const [scanning, setScanning] = useState(false)
  const runtimes = buildRuntimes(scannedProviders, scanning)
  const [step, setStep] = useState(1)
  // Step 1
  const [pickedIndex, setPickedIndex] = useState<number | null>(null)
  const [customName, setCustomName] = useState('')
  const [customPrompt, setCustomPrompt] = useState('')
  const [customSkills, setCustomSkills] = useState<string[]>([])
  const [skillList, setSkillList] = useState<{name:string}[]>([])
  const [skillLoading, setSkillLoading] = useState(false)
  // Step 2
  const [agentSystem, setAgentSystem] = useState('claude_code')
  const [providerId, setProviderId] = useState('deepseek')
  const [model, setModel] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [selectedKeyId, setSelectedKeyId] = useState('')
  // 连通性预检
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle')
  const [testError, setTestError] = useState('')
  // Step 3
  const [status, setStatus] = useState<'idle' | 'creating' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  // CLI + Provider → 自动推导 base_url / 协议 / 模型
  const derivedConfig = resolveProviderConfig(agentSystem, providerId)
  const derivedBaseUrl = derivedConfig?.baseUrl ?? ''
  const derivedModels = derivedConfig?.models ?? []
  const derivedProtocol = derivedConfig?.protocol ?? ''

  // 选 CLI 或 Provider 变化时自动填默认值
  useEffect(() => {
    if (!derivedConfig) return
    if (!baseUrl) setBaseUrl(derivedConfig.baseUrl)
    if (!model || !derivedConfig.models.includes(model)) {
      setModel(derivedConfig.models[0] ?? '')
    }
  }, [agentSystem, providerId])

  const isCustom = pickedIndex === TEMPLATES.length
  const selectedTemplate = pickedIndex !== null && pickedIndex < TEMPLATES.length ? TEMPLATES[pickedIndex] : null
  const agentName = isCustom ? customName : (selectedTemplate?.name ?? '')
  const agentSystemPrompt = isCustom ? customPrompt : (selectedTemplate?.systemPrompt ?? '')
  const selectedSkills = isCustom ? customSkills : (selectedTemplate?.skills ?? [])

  // 自定义时加载 skill 列表 + 恢复草稿
  useEffect(() => {
    if (!isCustom) return
    setSkillLoading(true)
    fetch('/api/skills/library?_=' + Date.now())
      .then((r) => r.json())
      .then(setSkillList)
      .catch(() => setSkillList([]))
      .finally(() => setSkillLoading(false))
    // 恢复跳转市场前的草稿
    if (wizardDraft) {
      setCustomName(wizardDraft.name)
      setCustomPrompt(wizardDraft.prompt)
      setCustomSkills(wizardDraft.skills)
      wizardDraft = null
    }
  }, [isCustom])

  const toggleSkill = (name: string) => {
    setCustomSkills((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name],
    )
  }

  // CLI subprocess 类型的 provider 需要显示配置区（key/model/base_url）
  const showProviderSection = agentSystem !== 'mock'

  const reset = () => {
    setStep(1)
    setPickedIndex(null)
    setCustomName('')
    setCustomPrompt('')
    setCustomSkills([])
    setSkillList([])
    setAgentSystem('claude_code')
    setProviderId('deepseek')
    setModel('')
    setBaseUrl('')
    setApiKey('')
    setTestStatus('idle')
    setTestError('')
    setSelectedKeyId('')
    setStatus('idle')
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
    setAgentSystem('claude_code')
    setProviderId('deepseek')
    setModel(providers.find(p => p.id === 'deepseek')?.models[0] ?? '')
    setBaseUrl('')
    setApiKey('')
    setStep(2)

    // 后台异步扫描 CLI，只显示实际检测到的
    if (providerScanned && providerCache) {
      setScannedProviders(providerCache)
      const firstCli = providerCache.find(p => p.adapter !== 'mock')
      if (firstCli) setAgentSystem(firstCli.name)
    } else {
      setScanning(true)
      fetch('/api/providers')
        .then(r => r.json())
        .then((list: ProviderInfo[]) => {
          providerCache = list
          providerScanned = true
          setScannedProviders(list)
          const firstCli = list.find((p: ProviderInfo) => p.adapter !== 'mock')
          if (firstCli) setAgentSystem(firstCli.name)
        })
        .catch(() => setScannedProviders(null))
        .finally(() => setScanning(false))
    }
  }

  const goBack = () => setStep(1)

  // 连通性预检（创建前执行，失败不损失任何东西）
  const doConnectivityTest = async () => {
    if (agentSystem === 'mock') return
    setTestStatus('testing')
    setTestError('')
    try {
      const resp = await fetch('/api/providers/ping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent_system: agentSystem,
          provider: providerId,
          model: model.trim(),
          api_key: apiKey,
          base_url: baseUrl.trim() || undefined,
        }),
      })
      const data = await resp.json()
      if (data.ok) {
        setTestStatus('ok')
      } else {
        setTestStatus('fail')
        setTestError(data.error || '连通失败')
      }
    } catch (e) {
      setTestStatus('fail')
      setTestError(e instanceof Error ? e.message : '网络错误')
    }
  }

  // Step 3: 创建（先连通测试，通过后再创建）
  const doCreate = async () => {
    if (!agentName.trim()) return
    setStep(3)
    setStatus('creating')
    setErrorMsg('')

    // 1. 连通性预检（非 mock 时自动执行）
    if (agentSystem !== 'mock' && apiKey) {
      try {
        const resp = await fetch('/api/providers/ping', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            agent_system: agentSystem,
            provider: providerId,
            model: model.trim(),
            api_key: apiKey,
            base_url: baseUrl.trim() || undefined,
          }),
        })
        const data = await resp.json()
        if (!data.ok) {
          setStatus('error')
          setErrorMsg(`连通失败: ${data.error || '未知错误'}，请返回修改配置`)
          return
        }
      } catch (e) {
        setStatus('error')
        setErrorMsg('连通测试网络错误，请检查后端是否运行')
        return
      }
    }

    // 2. 创建 Agent
    try {
      const id = await createAgent({
        name: agentName.trim(),
        role: agentName.trim(),
        agentSystem,
        provider: providerId,
        model: showProviderSection ? model.trim() : '',
        baseUrl: showProviderSection ? baseUrl.trim() || undefined : undefined,
        apiKey,
        skills: selectedSkills,
        systemPrompt: agentSystemPrompt,
        // 工作目录不在创建时选择（走后端默认）；具体项目上下文在「发起私聊」时按需指定
        settings: undefined,
      })

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
                <div className="flex flex-col gap-3">
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
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <Label>Skill</Label>
                      <button
                        type="button"
                        onClick={() => {
                          wizardDraft = {
                            name: customName,
                            prompt: customPrompt,
                            skills: customSkills,
                          }
                          onClose()
                          setTimeout(() => setSection('skills-market'), 0)
                        }}
                        className="text-[11px] text-brand hover:underline"
                      >
                        浏览技能市场 →
                      </button>
                    </div>
                    {skillLoading ? (
                      <span className="text-[12px] text-muted-foreground">加载中…</span>
                    ) : skillList.length === 0 ? (
                      <span className="text-[12px] text-muted-foreground">暂无可用 Skill</span>
                    ) : (
                      <div className="flex flex-col gap-1 rounded-md border p-2">
                        {skillList.map((s) => (
                          <label
                            key={s.name}
                            className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-[13px] hover:bg-accent"
                          >
                            <input
                              type="checkbox"
                              checked={customSkills.includes(s.name)}
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
                <span className="text-[11px] text-muted-foreground ml-1">2/3</span>
              </div>
              <Button variant="ghost" size="iconSm" onClick={() => { reset(); onClose() }}>
                <Icon name="x" className="h-3.5 w-3.5" />
              </Button>
            </header>

            <div className="flex flex-col gap-3 overflow-y-auto p-4" style={{ maxHeight: '55vh' }}>

              <div className="flex flex-col gap-1">
                <div className="flex items-center justify-between">
                  <Label>运行依赖</Label>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setScanning(true)
                      providerScanned = false
                      fetch('/api/providers')
                        .then(r => r.json())
                        .then((list: ProviderInfo[]) => {
                          providerCache = list
                          providerScanned = true
                          setScannedProviders(list)
                        })
                        .catch(() => setScannedProviders(null))
                        .finally(() => setScanning(false))
                    }}
                    disabled={scanning}
                  >
                    {scanning ? (
                      <span className="flex items-center gap-1">
                        <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        扫描中
                      </span>
                    ) : (
                      '重新扫描'
                    )}
                  </Button>
                </div>
                <select
                  className={SELECT_CLS}
                  value={agentSystem}
                  onChange={(e) => setAgentSystem(e.target.value)}
                >
                  {runtimes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label}
                    </option>
                  ))}
                </select>
                <span className="text-[11px] text-muted-foreground">
                  {scanning
                    ? '扫描中…'
                    : providerScanned
                      ? `扫描完成，${runtimes.filter(r => r.id !== 'mock').length} 个可用`
                      : ''}
                </span>
              </div>

              {showProviderSection && (
                <>
                  <label className="flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <Label>选择配置</Label>
                      <button
                        type="button"
                        onClick={() => setSection('api-keys')}
                        className="text-[11px] text-brand hover:underline"
                      >
                        管理配置 →
                      </button>
                    </div>
                    {savedKeys.length > 0 ? (
                      <select
                        className={SELECT_CLS}
                        value={selectedKeyId}
                        onChange={(e) => {
                          const id = e.target.value
                          setSelectedKeyId(id)
                          setTestStatus('idle')
                          const found = savedKeys.find((k) => k.id === id)
                          if (found) {
                            setApiKey(found.apiKey)
                            setProviderId(found.provider)
                            // base_url 和 model 由 CLI×Provider 矩阵自动推导
                            const derived = resolveProviderConfig(agentSystem, found.provider)
                            if (derived) {
                              setBaseUrl(derived.baseUrl)
                              setModel(found.model && derived.models.includes(found.model) ? found.model : (derived.models[0] ?? ''))
                            } else {
                              setBaseUrl(found.baseUrl)
                              setModel(found.model ?? '')
                            }
                          }
                        }}
                      >
                        <option value="">选择已保存的配置…</option>
                        {savedKeys.map((k) => (
                          <option key={k.id} value={k.id}>
                            {k.name} · {k.keyPrefix}****
                          </option>
                        ))}
                      </select>
                    ) : (
                      <div className="rounded-md border border-dashed p-3 text-center text-[12px] text-muted-foreground">
                        还没有保存的配置，请先
                        <button type="button" onClick={() => setSection('api-keys')} className="mx-0.5 text-brand underline">添加 Provider 配置</button>
                        或下方手动填写
                      </div>
                    )}
                  </label>

                  {/* 自动推导 + 可编辑的连接配置 */}
                  {selectedKeyId && derivedConfig && (
                    <div className="rounded-md border bg-muted/50 p-2.5 text-[12px] text-muted-foreground space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-foreground">连接配置</span>
                        <span className="text-[10px]">{agentSystem} × {providerId} · {derivedProtocol}{derivedConfig.needsProxy ? ' (Proxy)' : ''}</span>
                      </div>
                      <label className="flex flex-col gap-0.5">
                        <span>端点地址</span>
                        <input
                          className="h-7 w-full rounded border border-input bg-background px-2 text-[12px]"
                          value={baseUrl}
                          onChange={(e) => { setBaseUrl(e.target.value); setTestStatus('idle') }}
                          placeholder={derivedBaseUrl}
                        />
                      </label>
                      <label className="flex flex-col gap-0.5">
                        <span>模型</span>
                        <div className="flex gap-1">
                          <select
                            className="h-7 flex-1 rounded border border-input bg-background px-2 text-[12px]"
                            value={derivedModels.includes(model) ? model : '__custom__'}
                            onChange={(e) => { if (e.target.value !== '__custom__') setModel(e.target.value); setTestStatus('idle') }}
                          >
                            {derivedModels.map(m => <option key={m} value={m}>{m}</option>)}
                            <option value="__custom__">自定义…</option>
                          </select>
                          {!derivedModels.includes(model) && (
                            <input
                              className="h-7 w-40 rounded border border-input bg-background px-2 text-[12px]"
                              value={model}
                              onChange={(e) => { setModel(e.target.value); setTestStatus('idle') }}
                              placeholder="手填模型名"
                            />
                          )}
                        </div>
                      </label>
                      {derivedConfig.note && (
                        <div className="text-[11px] text-amber-600">⚠ {derivedConfig.note}</div>
                      )}
                    </div>
                  )}

                  {/* 工作目录已外迁到「发起私聊」弹窗 */}
                </>
              )}
            </div>

            <footer className="flex items-center justify-between border-t px-4 py-3">
              <div className="flex items-center gap-2">
                <Button variant="outline" size="sm" onClick={goBack}>
                  上一步
                </Button>
                {showProviderSection && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={doConnectivityTest}
                      disabled={testStatus === 'testing' || !apiKey}
                    >
                      {testStatus === 'testing' ? '测试中…' : testStatus === 'ok' ? '✅ 连通成功' : testStatus === 'fail' ? '❌ 重试' : '🔄 连通测试'}
                    </Button>
                    {testStatus === 'fail' && (
                      <span className="text-[11px] text-red-500 max-w-[200px] truncate">{testError}</span>
                    )}
                  </>
                )}
              </div>
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
