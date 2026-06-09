import { useEffect, useMemo, useState } from 'react'
import { useAgentStore } from '../../stores/agentStore'
import { useChatStore } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { Button, Dialog, DialogContent, Icon, Input, Textarea } from '../ui'
import { providersApi, type ProviderInfo } from '../../api/providers'
import { type TemplateDetail } from '../../api/templates'
import { useTemplateStore } from '../../stores/templateStore'
import { CliIcon } from '../icons/cli/CliIcon'
import { StartChatModal } from '../chat/StartChatModal'

// =================================================================
// B-4-P2-AG01：createAgent() 错误三段式分类（详见 docs/specs/04-commands §6.4.6）
//
// 触发场景（来自用户截图）：后端 502 时老逻辑只剥了 "API 502: " 前缀就显示，
//   结果用户看到 nginx 默认错误页的 HTML 片段。新逻辑直接给
//   「后端服务未启动或网络不通」+ 排查命令；4xx 保留 detail；其他给「网络连接失败」。
//
// 抽离成可测试的纯函数 export 出去，测试在 __tests__/CreateAgentModal.test.tsx。
// =================================================================
const FIVE_HUNDRED_MSG =
  '后端服务未启动或网络不通 — 请检查 AgentHub 后端进程（docker compose ps backend 或 uvicorn :8000）'
const NETWORK_MSG = '网络连接失败 — 请检查网络'
const GENERIC_MSG = '创建失败，请检查配置'

/** 暴露给单测；不要在 UI 直接调用 — 用 classifyCreateAgentError() 即可。 */
// eslint-disable-next-line react-refresh/only-export-components
export function classifyCreateAgentError(e: unknown): string {
  let raw: string
  if (e instanceof Error) {
    raw = e.message || '创建失败'
  } else if (typeof e === 'string') {
    raw = e
  } else if (e == null) {
    return FIVE_HUNDRED_MSG
  } else {
    raw = String(e)
  }
  const m = raw.match(/^API (\d{3}):/)
  if (m) {
    const code = parseInt(m[1] ?? '', 10)
    if (Number.isFinite(code) && code >= 500) {
      return FIVE_HUNDRED_MSG
    }
    if (Number.isFinite(code) && code >= 400) {
      const detail = raw.replace(/^API \d+:\s*/, '').trim()
      if (detail.length === 0) return GENERIC_MSG
      return detail.length < 200 ? detail : GENERIC_MSG
    }
  }
  return NETWORK_MSG
}

// --- Step 1 模板（旧版硬编码兜底，API 不可用时显示） ---
interface LegacyTemplate {
  name: string
  systemPrompt: string
  skills: string[]
}
/**
 * 预填模板 prop：外部调用 CreateAgentModal 时可不经过 Step 1，
 * 直接把给定模板数据预选好并从 Step 2 开始。
 */
export interface PreSelectedTemplate {
  name: string
  systemPrompt: string
  skills: string[]
  capabilityTags: string[]
  /** 推荐模型层级（opus / sonnet / haiku） */
  model?: string
  /** 模板 ID，用于将 Agent 关联回创建它的模板 */
  templateId?: string
}

const LEGACY_TEMPLATES: LegacyTemplate[] = [
  {
    name: '产品经理',
    systemPrompt: `You are an expert business analyst specializing in data-driven decision making through advanced analytics, modern BI tools, and strategic business intelligence.

Expert business analyst focused on transforming complex business data into actionable insights and strategic recommendations. Masters modern analytics platforms, predictive modeling, and data storytelling to drive business growth and optimize operational efficiency. Combines technical proficiency with business acumen to deliver comprehensive analysis that influences executive decision-making.`,
    skills: [],
  },
  {
    name: '后端工程师',
    systemPrompt: `You are a backend system architect specializing in scalable, resilient, and maintainable backend systems and APIs.

Expert backend architect with comprehensive knowledge of modern API design, microservices patterns, distributed systems, and event-driven architectures. Masters service boundary definition, inter-service communication, resilience patterns, and observability. Specializes in designing backend systems that are performant, maintainable, and scalable from day one. Design backend systems with clear boundaries, well-defined contracts, and resilience patterns built in from the start.`,
    skills: [],
  },
  {
    name: '代码评审',
    systemPrompt: `You are an elite code review expert specializing in modern code analysis techniques, AI-powered review tools, and production-grade quality assurance.

Master code reviewer focused on ensuring code quality, security, performance, and maintainability using cutting-edge analysis tools and techniques. Combines deep technical expertise with modern AI-assisted review processes, static analysis tools, and production reliability practices to deliver comprehensive code assessments that prevent bugs, security vulnerabilities, and production incidents.`,
    skills: [],
  },
  {
    name: '测试工程师',
    systemPrompt: `You are an expert test automation engineer specializing in AI-powered testing, modern frameworks, and comprehensive quality engineering strategies.

Expert test automation engineer focused on building robust, maintainable, and intelligent testing ecosystems. Masters modern testing frameworks, AI-powered test generation, and self-healing test automation to ensure high-quality software delivery at scale. Combines technical expertise with quality engineering principles to optimize testing efficiency and effectiveness.`,
    skills: [],
  },
  {
    name: '技术负责人',
    systemPrompt: `You are a master software architect specializing in modern software architecture patterns, clean architecture principles, and distributed systems design.

Elite software architect focused on ensuring architectural integrity, scalability, and maintainability across complex distributed systems. Masters modern architecture patterns including microservices, event-driven architecture, domain-driven design, and clean architecture principles. Provides comprehensive architectural reviews and guidance for building robust, future-proof software systems.`,
    skills: [],
  },
  {
    name: '运维工程师',
    systemPrompt: `You are a DevOps troubleshooter specializing in rapid incident response, advanced debugging, and modern observability practices.

Expert DevOps troubleshooter with comprehensive knowledge of modern observability tools, debugging methodologies, and incident response practices. Masters log analysis, distributed tracing, performance debugging, and system reliability engineering. Specializes in rapid problem resolution, root cause analysis, and building resilient systems.`,
    skills: [],
  },
  {
    name: '数据工程师',
    systemPrompt: `You are a data engineer specializing in scalable data pipelines, modern data architecture, and analytics infrastructure.

Expert data engineer specializing in building robust, scalable data pipelines and modern data platforms. Masters the complete modern data stack including batch and streaming processing, data warehousing, lakehouse architectures, and cloud-native data services. Focuses on reliable, performant, and cost-effective data solutions.`,
    skills: [],
  },
  {
    name: '安全审计',
    systemPrompt: `You are a security auditor specializing in DevSecOps, application security, and comprehensive cybersecurity practices.

Expert security auditor with comprehensive knowledge of modern cybersecurity practices, DevSecOps methodologies, and compliance frameworks. Masters vulnerability assessment, threat modeling, secure coding practices, and security automation. Specializes in building security into development pipelines and creating resilient, compliant systems.`,
    skills: [],
  },
]

// --- Step 1 动态模板（从 API 加载，含 compatibility + modelTier） ---
/** 用于 derived 的统一模板形状：legacy / API / preSelected 三种来源归一化 */
interface UnifiedTemplate {
  name: string
  systemPrompt: string
  skills: string[]
  capabilityTags: string[]
  compatibleAgentSystems: string[] | null
  compatibleProviders: string[] | null
  model: string | null
}

/** 把 API TemplateDetail 归一化为 UnifiedTemplate */
function apiDetailToUnified(d: TemplateDetail): UnifiedTemplate {
  return {
    name: d.display_name_zh || d.name,
    systemPrompt: d.system_prompt,
    skills: d.recommended_skills ?? [],
    capabilityTags: [],
    compatibleAgentSystems: d.compatible_agent_systems?.length ? d.compatible_agent_systems : null,
    compatibleProviders: d.compatible_providers?.length ? d.compatible_providers : null,
    model: d.model_tier !== 'inherit' ? d.model_tier : null,
  }
}

function Label({ children }: { children: string }) {
  return <span className="text-[12px] font-medium text-muted-foreground">{children}</span>
}

/** 跳转技能市场时暂存草稿，回来后恢复 */
let wizardDraft: { name: string; prompt: string; skills: string[] } | null = null

/** CLI provider 扫描缓存（模块级，页面不刷新则保留） */
let providerCache: ProviderInfo[] | null = null
let providerScanned = false

/** 卡片用的 CLI 摘要 */
interface CliCardData {
  id: string
  label: string
  version: string | null
  available: boolean
}

function buildCards(
  scanned: ProviderInfo[] | null,
  scanning: boolean,
): CliCardData[] {
  if (scanning) return []
  if (scanned) {
    return scanned
      .filter((p) => p.available && p.name !== 'mock')
      .map((p) => ({
        id: p.name,
        label: p.display_name,
        version: p.version,
        available: true,
      }))
  }
  return []
}

export function CreateAgentModal({
  open,
  onClose,
  preSelectedTemplate,
}: {
  open: boolean
  onClose: () => void
  preSelectedTemplate?: PreSelectedTemplate
}) {
  const createAgent = useAgentStore((s) => s.createAgent)
  const agents = useAgentStore((s) => s.agents)
  const addConversation = useChatStore((s) => s.addConversation)
  const conversations = useChatStore((s) => s.conversations)
  const openConversation = useUIStore((s) => s.openConversation)
  const setSection = useUIStore((s) => s.setSection)

  // 创建成功后的 StartChatModal 状态
  const [showStartChat, setShowStartChat] = useState(false)
  const [newAgentId, setNewAgentId] = useState<string | null>(null)
  const [newAgentName, setNewAgentName] = useState('')

  // -- Template store --
  const {
    templates,
    loading: tplLoading,
    error: tplError,
    loadTemplates,
    loadTemplateDetail,
    syncSource,
    getCachedDetail,
  } = useTemplateStore()

  // Wizard state
  const [scannedProviders, setScannedProviders] = useState<ProviderInfo[] | null>(null)
  const [scanning, setScanning] = useState(false)
  const cards = buildCards(scannedProviders, scanning)
  const [step, setStep] = useState(1)
  const [agentName, setAgentName] = useState('')
  const [nameError, setNameError] = useState('')

  // Step 1: dynamic template selection
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [selectedTemplateData, setSelectedTemplateData] = useState<TemplateDetail | null>(null)

  // Step 1 legacy fallback
  const [pickedIndex, setPickedIndex] = useState<number | null>(null)
  const [customPrompt, setCustomPrompt] = useState('')
  const [customRoleName, setCustomRoleName] = useState('')
  const [customSkills, setCustomSkills] = useState<string[]>([])
  const [skillList, setSkillList] = useState<{name:string}[]>([])
  const [skillLoading, setSkillLoading] = useState(false)
  // Step 2
  const [agentSystem, setAgentSystem] = useState<string>('')
  // Step 3
  const [status, setStatus] = useState<'idle' | 'creating' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  // -- Favorite dialog state --
  const [favDialogOpen, setFavDialogOpen] = useState(false)
  const [favTargetId] = useState<string | null>(null)
  const [favName, setFavName] = useState('')
  const [favDescription, setFavDescription] = useState('')
  const [favSaving, setFavSaving] = useState(false)
  const [favError, setFavError] = useState('')
  const [toast, setToast] = useState<string | null>(null)
  const [favManageOpen, setFavManageOpen] = useState(false)
  const [favCheckedIds, setFavCheckedIds] = useState<Set<string>>(new Set())

  // -- Template store favorites --
  const favorites = useTemplateStore((s) => s.favorites)
  const favoritesLoading = useTemplateStore((s) => s.favoritesLoading)
  const loadFavorites = useTemplateStore((s) => s.loadFavorites)
  const setFavorite = useTemplateStore((s) => s.setFavorite)

  // -- Load templates + favorites when entering Step 1 --
  useEffect(() => {
    if (step === 1 && open) {
      loadTemplates()
      loadFavorites()
    }
  }, [step, open, loadTemplates, loadFavorites])

  // preSelectedTemplate: 外部传入模板数据时跳过 Step 1，直接从 Step 2 开始
  useEffect(() => {
    if (!open || !preSelectedTemplate) return
    queueMicrotask(() => {
      setStep(2)
      setAgentSystem('')
      // 后台扫描 CLI
      if (providerScanned && providerCache) {
        setScannedProviders(providerCache)
      } else {
        setScanning(true)
        providersApi
          .list()
          .then((list) => {
            providerCache = list
            providerScanned = true
            setScannedProviders(list)
          })
          .catch((err) => {
            console.error('CLI 扫描失败 (preSelected):', err)
            setScannedProviders(null)
          })
          .finally(() => setScanning(false))
      }
    })
    // 仅在 open 和 preSelectedTemplate 变化时触发
  }, [open, preSelectedTemplate])

  // -- Determine mode: dynamic (API) vs legacy (fallback) --
  const hasDynamicTemplates = !tplLoading && !tplError && templates.length > 0

  // -- Save favorite --
  const handleSaveFavorite = async () => {
    if (!favTargetId || !favName.trim()) return
    setFavSaving(true)
    setFavError('')
    try {
      await setFavorite(favTargetId, {
        is_favorite: true,
        favorite_name: favName.trim(),
        favorite_description: favDescription.trim(),
      })
      setFavDialogOpen(false)
      setToast('已添加到常用模板')
      setTimeout(() => setToast(null), 2000)
    } catch (e) {
      setFavError(e instanceof Error ? e.message : '添加失败')
    } finally {
      setFavSaving(false)
    }
  }

  // -- Custom button click handler --
  const handleCustomClick = () => {
    setSelectedTemplateId('__custom__')
    setSelectedTemplateData(null)
    setPickedIndex(LEGACY_TEMPLATES.length)
  }


  // -- Derived: is custom mode? --
  const isCustom = preSelectedTemplate
    ? false
    : selectedTemplateId === '__custom__' || pickedIndex === LEGACY_TEMPLATES.length

  // -- Unified selectedTemplate --
  const selectedTemplate: UnifiedTemplate | null = useMemo(() => {
    if (preSelectedTemplate) {
      return {
        name: preSelectedTemplate.name,
        systemPrompt: preSelectedTemplate.systemPrompt,
        skills: preSelectedTemplate.skills,
        capabilityTags: preSelectedTemplate.capabilityTags,
        compatibleAgentSystems: null,
        compatibleProviders: null,
        model: null,
      }
    }
    if (selectedTemplateData && selectedTemplateId !== '__custom__') {
      return apiDetailToUnified(selectedTemplateData)
    }
    if (pickedIndex !== null && pickedIndex < LEGACY_TEMPLATES.length) {
      const t = LEGACY_TEMPLATES[pickedIndex]
      return {
        name: t.name,
        systemPrompt: t.systemPrompt,
        skills: t.skills,
        capabilityTags: [],
        compatibleAgentSystems: null,
        compatibleProviders: null,
        model: null,
      }
    }
    return null
  }, [preSelectedTemplate, hasDynamicTemplates, selectedTemplateData, selectedTemplateId, pickedIndex])

  const agentSystemPrompt = isCustom ? customPrompt : (selectedTemplate?.systemPrompt ?? '')
  const selectedSkills = isCustom ? customSkills : (selectedTemplate?.skills ?? [])
  const selectedCapabilityTags = selectedTemplate?.capabilityTags ?? []

  // 兼容的 CLI 集合（用于 Step 2 灰显不兼容卡片）
  const compatibleCliSet = useMemo(() => {
    const list = selectedTemplate?.compatibleAgentSystems
    return list ? new Set(list) : null
  }, [selectedTemplate])

  // 自定义时加载 skill 列表 + 恢复草稿（setState 推迟到 microtask 避开 set-state-in-effect）
  useEffect(() => {
    if (!isCustom) return
    queueMicrotask(() => {
      setSkillLoading(true)
      fetch('/api/skills/library?_=' + Date.now())
        .then((r) => r.json())
        .then(setSkillList)
        .catch(() => setSkillList([]))
        .finally(() => setSkillLoading(false))
      if (wizardDraft) {
        setAgentName(wizardDraft.name)
        setCustomPrompt(wizardDraft.prompt)
        setCustomSkills(wizardDraft.skills)
        wizardDraft = null
      }
    })
  }, [isCustom])

  const toggleSkill = (name: string) => {
    setCustomSkills((prev) =>
      prev.includes(name) ? prev.filter((s) => s !== name) : [...prev, name],
    )
  }

  const reset = () => {
    setStep(1)
    setPickedIndex(null)
    setSelectedTemplateId(null)
    setSelectedTemplateData(null)
    setAgentName('')
    setCustomPrompt('')
    setCustomRoleName('')
    setCustomSkills([])
    setSkillList([])
    setAgentSystem('')
    setStatus('idle')
    setErrorMsg('')
  }

  const handleClose = () => {
    if (status === 'creating') return
    reset()
    onClose()
  }

  // Step 1 → Step 2
  const hasAnySelection = selectedTemplateId !== null || pickedIndex !== null

  const existingNames = agents.map((a) => a.name.toLowerCase())

  const canNext = (() => {
    if (preSelectedTemplate) return true
    if (!hasAnySelection) { setNameError('请选择一个模板'); return false }
    if (!agentName.trim()) { setNameError('请输入队友名称'); return false }
    if (existingNames.includes(agentName.trim().toLowerCase())) { setNameError('该名称已被使用，请换一个'); return false }
    if (isCustom && (!customPrompt.trim() || !customRoleName.trim())) return false
    setNameError('')
    return true
  })()

  const goNext = () => {
    if (!canNext) return
    setAgentSystem('')
    setStep(2)

    // 后台异步扫描 CLI
    if (providerScanned && providerCache) {
      setScannedProviders(providerCache)
    } else {
      setScanning(true)
      providersApi
        .list()
        .then((list) => {
          providerCache = list
          providerScanned = true
          setScannedProviders(list)
        })
        .catch((err) => {
          console.error('CLI 扫描失败 (初始):', err)
          setScannedProviders(null)
        })
        .finally(() => setScanning(false))
    }
  }

  const handlePickCli = (id: string) => {
    setAgentSystem(id)
  }

  const goBack = () => {
    if (preSelectedTemplate) {
      reset()
      onClose()
      return
    }
    setStep(1)
  }

  // Step 3: 创建
  const doCreate = async () => {
    if (!agentName.trim()) return
    setStep(3)
    setStatus('creating')
    setErrorMsg('')

    try {
      const id = await createAgent({
        name: agentName.trim(),
        role: isCustom ? (customRoleName || agentName.trim()) : (selectedTemplate?.name ?? agentName.trim()),
        agentSystem,
        skills: selectedSkills,
        capabilityTags: selectedCapabilityTags,
        systemPrompt: agentSystemPrompt,
        templateName: isCustom ? customRoleName : selectedTemplate?.name,
        settings: undefined,
      })

      setNewAgentId(id)
      setNewAgentName(agentName.trim())
      setStatus('success')
      setTimeout(() => {
        reset()
        onClose()
        setShowStartChat(true)
      }, 800)
    } catch (e) {
      setStatus('error')
      setErrorMsg(classifyCreateAgentError(e))
    }
  }

  const doRetry = () => {
    setStatus('creating')
    doCreate()
  }

  return (
    <>
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
              <p className="text-[13px] text-muted-foreground">给 AI 队友取个名字吧</p>

              <Input
                value={agentName}
                onChange={(e) => { setAgentName(e.target.value); setNameError('') }}
                placeholder="例如：我的代码助手"
                autoFocus
              />
              {nameError && (
                <p className="text-[11px] text-red-500 -mt-1">{nameError}</p>
              )}

              <div className="border-t border-border/60 my-1" />

              <p className="text-[13px] text-muted-foreground">选择身份模板</p>

              {/* -- Loading skeletons -- */}
              {tplLoading && !hasDynamicTemplates && (
                <div className="grid grid-cols-2 gap-2">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div
                      key={`skel-${i}`}
                      className="flex flex-col gap-1 rounded-lg border p-3 animate-pulse"
                    >
                      <div className="h-3 w-20 rounded bg-muted" />
                      <div className="h-2 w-full rounded bg-muted/60" />
                      <div className="h-2 w-3/4 rounded bg-muted/60" />
                    </div>
                  ))}
                </div>
              )}

              {/* -- Error banner -- */}
              {tplError && !tplLoading && !hasDynamicTemplates && (
                <div className="flex items-center justify-between rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
                  <span className="truncate mr-2">加载模板失败：{tplError}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => loadTemplates()}
                    className="shrink-0"
                  >
                    重试
                  </Button>
                </div>
              )}

              {/* -- Empty state (API succeeded but no templates) -- */}
              {!tplLoading && !tplError && templates.length === 0 && (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <Icon name="files" className="mb-2 h-8 w-8 text-muted-foreground/30" />
                  <p className="text-[13px] font-medium">暂无可用模板</p>
                  <p className="mt-1 text-[12px] text-muted-foreground">
                    模板仓库尚未同步，请先同步获取最新模板
                  </p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-3"
                    onClick={() => syncSource()}
                  >
                    <Icon name="zap" className="mr-1 h-3 w-3" />
                    同步模板
                  </Button>
                </div>
              )}

              {/* -- 8 个身份模板（始终显示） -- */}
              <div className="grid grid-cols-2 gap-2">
                {LEGACY_TEMPLATES.map((t, i) => {
                  const picked = pickedIndex === i && !isCustom
                  return (
                    <button
                      key={t.name}
                      type="button"
                      onClick={() => {
                        setPickedIndex(i)
                        setSelectedTemplateId(null)
                        setSelectedTemplateData(null)
                      }}
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
              </div>

              {/* -- 常用模板（favorites） -- */}
              {favorites.length > 0 && (
                <>
                  <div className="flex items-center justify-between border-t border-border/60 pt-3">
                    <span className="text-[13px] text-muted-foreground">常用模板</span>
                    <button
                      type="button"
                      onClick={() => setFavManageOpen(true)}
                      className="text-[11px] text-brand hover:underline"
                    >
                      管理常用模板 →
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    {favorites.map((fav) => {
                      const favPicked = selectedTemplateId === fav.id && !isCustom
                      return (
                        <button
                          key={fav.id}
                          type="button"
                          onClick={async () => {
                            setPickedIndex(null)
                            setSelectedTemplateId(fav.id)
                            const detail = await loadTemplateDetail(fav.id)
                            setSelectedTemplateData(detail)
                          }}
                          data-picked={favPicked ? 'true' : undefined}
                          className="flex flex-col gap-1 rounded-lg border p-3 text-left transition-colors hover:border-brand/40 data-[picked=true]:border-brand data-[picked=true]:bg-brand/5"
                        >
                          <span className="text-[13px] font-medium">
                            {fav.favorite_name || fav.display_name_zh || fav.name}
                          </span>
                          <span className="line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                            {fav.favorite_description || fav.description_zh || fav.description || '暂无描述'}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                </>
              )}

              {/* -- 自定义 -- */}
              <button
                onClick={handleCustomClick}
                data-picked={isCustom ? 'true' : undefined}
                className="flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed p-3 text-muted-foreground transition-colors hover:border-brand/40 hover:text-brand data-[picked=true]:border-brand data-[picked=true]:bg-brand/5 data-[picked=true]:text-brand"
              >
                <Icon name="plus" className="h-5 w-5" />
                <span className="text-[12px]">自定义（从零创建）</span>
              </button>

              {isCustom && (
                <div className="flex flex-col gap-3">
                  <label className="flex flex-col gap-1.5">
                    <span className="text-[12px] font-medium text-muted-foreground">身份（模板名）</span>
                    <Input
                      value={customRoleName}
                      onChange={(e) => setCustomRoleName(e.target.value)}
                      placeholder="例如：全栈工程师、DevOps 专家"
                    />
                  </label>
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
                            name: agentName,
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

              {/* -- Template compatibility info banner -- */}
              {hasDynamicTemplates && selectedTemplateData && compatibleCliSet && (
                <div className="rounded-md border border-brand/20 bg-brand/5 px-3 py-2 text-[12px] text-muted-foreground">
                  <span className="font-medium text-brand">
                    {selectedTemplateData.display_name_zh || selectedTemplateData.name}
                  </span>
                  <span className="mx-1">模板兼容：</span>
                  <span className="text-foreground">
                    {selectedTemplateData.compatible_agent_systems?.join(' / ') || '全部 CLI'}
                  </span>
                  {selectedTemplateData.model_tier !== 'inherit' && (
                    <span className="ml-1 rounded bg-muted px-1 py-px text-[10px]">
                      {selectedTemplateData.model_tier}
                    </span>
                  )}
                </div>
              )}

              <div className="flex flex-col gap-1.5">
                <div className="flex items-center justify-between">
                  <Label>运行依赖</Label>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      setScanning(true)
                      providerScanned = false
                      providersApi
                        .list()
                        .then((list) => {
                          providerCache = list
                          providerScanned = true
                          setScannedProviders(list)
                        })
                        .catch((err) => {
                          console.error('CLI 重新扫描失败:', err)
                          setScannedProviders(null)
                        })
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

                {/* CLI 卡片列表：兼容性过滤 */}
                <div className="grid grid-cols-2 gap-2">
                  {cards.map((c) => {
                    const picked = agentSystem === c.id
                    const isCompatible = !compatibleCliSet || compatibleCliSet.has(c.id) || c.id === 'mock'
                    return (
                      <button
                        key={c.id}
                        type="button"
                        onClick={() => isCompatible && handlePickCli(c.id)}
                        data-picked={picked ? 'true' : undefined}
                        data-compatible={isCompatible ? 'true' : 'false'}
                        disabled={!isCompatible}
                        title={isCompatible ? undefined : '此模板未针对该 CLI 优化'}
                        className={
                          'group flex items-start gap-2 rounded-lg border p-2.5 text-left transition-colors ' +
                          (isCompatible
                            ? 'hover:border-brand/40 data-[picked=true]:border-brand data-[picked=true]:bg-brand/5'
                            : 'opacity-40 cursor-not-allowed')
                        }
                      >
                        <div className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md bg-background">
                          <CliIcon agentSystem={c.id} size={18} />
                        </div>
                        <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                          <div className="flex items-center justify-between gap-1">
                            <span className="truncate text-[12px] font-medium">{c.label}</span>
                            {!isCompatible ? (
                              <span className="shrink-0 rounded bg-amber-100 px-1 py-px text-[9px] text-amber-600 dark:bg-amber-950 dark:text-amber-400">
                                不兼容
                              </span>
                            ) : c.version ? (
                              <span className="shrink-0 rounded bg-muted px-1 py-px text-[9px] text-muted-foreground">
                                {c.version}
                              </span>
                            ) : c.available ? null : (
                              <span className="shrink-0 text-[9px] text-muted-foreground">—</span>
                            )}
                          </div>
                          <span className="truncate text-[10px] text-muted-foreground">
                            {!isCompatible
                              ? '此模板未针对该 CLI 优化'
                              : picked
                                ? '已选中'
                                : '点击选择'}
                          </span>
                        </div>
                      </button>
                    )
                  })}
                </div>
                <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                  <span>
                    {scanning
                      ? '扫描中…'
                      : providerScanned
                        ? `扫描完成，${cards.filter((c) => c.id !== 'mock' && c.available).length} 个可用`
                        : '尚未扫描'}
                  </span>
                </div>
              </div>
            </div>

            <footer className="flex items-center justify-between border-t px-4 py-3">
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
                  <p className="mt-1 text-[12px] text-muted-foreground">正在创建 Agent，请稍候</p>
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

    {/* Favorite dialog */}
    <Dialog open={favDialogOpen} onOpenChange={(o) => !o && setFavDialogOpen(false)}>
      <DialogContent className="w-[420px]">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-[15px] font-medium">添加到常用</h3>
          <Button variant="ghost" size="iconSm" onClick={() => setFavDialogOpen(false)}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        <div className="flex flex-col gap-3 p-4">
          {favError && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-600">
              {favError}
            </div>
          )}

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">显示名</span>
            <Input
              value={favName}
              onChange={(e) => setFavName(e.target.value)}
              placeholder="模板显示名"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-[12px] font-medium text-muted-foreground">简介</span>
            <Textarea
              value={favDescription}
              onChange={(e) => setFavDescription(e.target.value)}
              placeholder="模板简介"
              className="min-h-[60px]"
            />
          </label>
        </div>

        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={() => setFavDialogOpen(false)}>
            取消
          </Button>
          <Button variant="brand" size="sm" onClick={handleSaveFavorite} disabled={favSaving || !favName.trim()}>
            {favSaving ? '保存中…' : '确认'}
          </Button>
        </footer>
      </DialogContent>
    </Dialog>

    {/* Favorite management dialog */}
    <Dialog open={favManageOpen} onOpenChange={(o) => { if (!o) { setFavManageOpen(false); setFavCheckedIds(new Set()) } }}>
      <DialogContent className="w-[420px]">
        <header className="flex items-center justify-between border-b px-4 py-3">
          <h3 className="text-[15px] font-medium">管理常用模板</h3>
          <Button variant="ghost" size="iconSm" onClick={() => { setFavManageOpen(false); setFavCheckedIds(new Set()) }}>
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        <div className="flex flex-col gap-2 overflow-y-auto p-4" style={{ maxHeight: '50vh' }}>
          {favorites.length === 0 ? (
            <p className="text-center text-[13px] text-muted-foreground py-4">暂无常用模板</p>
          ) : (
            favorites.map((fav) => {
              const checked = favCheckedIds.has(fav.id)
              return (
                <label
                  key={fav.id}
                  className="flex items-start gap-3 rounded-lg border p-3 cursor-pointer hover:bg-accent/50 transition-colors"
                >
                  <input
                    type="checkbox"
                    className="mt-0.5 h-4 w-4 accent-brand shrink-0"
                    checked={checked}
                    onChange={() => {
                      setFavCheckedIds((prev) => {
                        const next = new Set(prev)
                        if (next.has(fav.id)) {
                          next.delete(fav.id)
                        } else {
                          next.add(fav.id)
                        }
                        return next
                      })
                    }}
                  />
                  <div className="flex flex-col gap-0.5 min-w-0">
                    <span className="text-[13px] font-medium truncate">
                      {fav.favorite_name || fav.display_name_zh || fav.name}
                    </span>
                    <span className="text-[11px] text-muted-foreground line-clamp-2">
                      {fav.favorite_description || fav.description_zh || fav.description || '暂无描述'}
                    </span>
                  </div>
                </label>
              )
            })
          )}
        </div>

        <footer className="flex justify-between items-center border-t px-4 py-3">
          <span className="text-[11px] text-muted-foreground">
            {favCheckedIds.size > 0 ? `已选 ${favCheckedIds.size} 个` : '勾选要移出的模板'}
          </span>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => { setFavManageOpen(false); setFavCheckedIds(new Set()) }}>
              取消
            </Button>
            <Button
              variant="brand"
              size="sm"
              disabled={favCheckedIds.size === 0}
              onClick={async () => {
                const ids = Array.from(favCheckedIds)
                for (const id of ids) {
                  try {
                    await setFavorite(id, { is_favorite: false })
                  } catch {
                    // ignore individual failures
                  }
                }
                setFavCheckedIds(new Set())
              }}
            >
              确认移出
            </Button>
          </div>
        </footer>
      </DialogContent>
    </Dialog>

    {/* Toast notification */}
    {toast && (
      <div className="fixed bottom-6 right-6 z-50 animate-[var(--animate-slide-in)] rounded-lg border border-border/60 bg-background px-4 py-2.5 text-[13px] shadow-lg glass-soft">
        {toast}
      </div>
    )}

    {/* 创建成功后弹出「发起私聊」选择窗 */}
    {showStartChat && newAgentId && (
      <StartChatModal
        open={showStartChat}
        onOpenChange={setShowStartChat}
        agentName={newAgentName}
        existingCount={(conversations?.[newAgentId]?.length) ?? 0}
        onConfirm={(name, workdir) => {
          const convId = addConversation(newAgentId, { name, workdir })
          if (workdir?.trim()) setSection('files')
          openConversation(newAgentId, convId)
          setShowStartChat(false)
        }}
      />
    )}
  </>)
}
