// 领域类型统一定义（前端实施计划 §1.1）。Phase 1 覆盖布局所需，
// Task/Group/Inbox 等业务类型随对应 Phase 落地时使用。

export type AgentColor = 'brand' | 'sage' | 'clay' | 'rose' | 'blue' | 'neutral'

export type TaskStatus = 'todo' | 'doing' | 'blocked' | 'done'
/** 右侧「阶段」用的精简状态（无 blocked） */
export type StageStatus = 'todo' | 'doing' | 'done'
export type Priority = 'low' | 'normal' | 'high' | 'critical'

export interface OrgInfo {
  name: string
  initial: string
}

export interface UserInfo {
  handle: string
  name: string
  initial: string
}

export interface NavItem {
  id: string
  icon: IconName
  label: string
  count?: number
}

export interface Channel {
  id: string
  name: string
  unread: boolean
}

export interface Agent {
  id: string
  name: string
  role: string
  color: AgentColor
  online: boolean
  skillCount?: number
}

export interface Conversation {
  id: string
  name: string
  subtitle: string
}

export interface CenterTab {
  id: string
  icon: IconName
  label: string
}

export interface Attachment {
  name: string
  size: string
}

export interface ChatMessage {
  id: string
  from: 'agent' | 'user'
  time: string
  text: string
  /** 流式增量渲染中（done 后置 false / 移除哨兵） */
  streaming?: boolean
  attachment?: Attachment
  actions?: string[]
}

export interface StageTask {
  id: string
  label: string
  state: StageStatus
  eta: number
}

export type OutputKind = 'doc' | 'diff'
export type OutputStatus = 'input' | 'pending' | 'done'

export interface OutputFile {
  id: string
  name: string
  kind: OutputKind
  size: string
  status: OutputStatus
}

export interface Task {
  id: string
  title: string
  status: TaskStatus
  priority: Priority
  assignee?: string
  due?: string
}

// ── 群组 / 协调者（Phase 4） ──

export interface Group {
  id: string
  name: string
  description: string
  members: string[] // agentId[]
  /** 协调者 Agent id（后端 is_system=true，不在 agentStore.agents 列表）。 */
  coordinatorId?: string
  /** 协调者展示名，来自 ApiGroup.coordinator.name（actors.ts 用）。 */
  coordinatorName?: string
  /** 协调者角色描述。 */
  coordinatorRole?: string
  pinnedTask?: string
}

/** 协调者分发方案中的单个子任务步骤。 */
export interface PlanStep {
  id: string
  who: string // agentId
  label: string
  eta: number // 分钟
  depends: string[] // 依赖的 step id
}

export interface CoordinatorPlan {
  summary: string
  steps: PlanStep[]
  watchouts: string[]
}

/**
 * 群聊消息。`who` 取值：agentId（含协调者 UUID）| 'user' | 'unknown'。
 * `kind === 'plan'` 时带结构化分发方案 `plan`。
 */
export interface GroupMessage {
  id: string
  from: 'user' | 'agent'
  who: string
  time: string
  text?: string
  kind?: 'plan'
  plan?: CoordinatorPlan
  requiresApproval?: boolean
  /** 流式增量渲染中（done 后置 false / 移除哨兵） */
  streaming?: boolean
  /** 用户消息的 @mention 名单（解析自正文，发送时透传给后端）。 */
  mentions?: string[]
}

// ── 次要视图（Phase 5） ──

export interface Activity {
  id: string
  when: string
  count: number
  tools: string[]
  text: string
  latest?: boolean
  running?: boolean
}

export type DiffKind = 'add' | 'del' | 'neutral'
export interface DiffLine {
  kind: DiffKind
  text: string
}

export type InboxType = 'approval' | 'task' | 'system'
export interface InboxItem {
  id: string
  type: InboxType
  title: string
  summary: string
  actor?: string
  actorName?: string
  when: string
  diff?: DiffLine[]
  impact?: string
  unread: boolean
}

export interface Skill {
  id: string
  name: string
  desc: string
  locked: boolean
}

export type MemoryStatus = 'accepted' | 'pending' | 'archived'
export interface MemoryItem {
  id: string
  title: string
  body: string
  tags: string[]
  status: MemoryStatus
  when: string
}

export type CalendarTone = 'brand' | 'sage'
export interface CalendarEvent {
  id: string
  date: string // YYYY-MM-DD
  startHour: number
  endHour: number
  title: string
  tone: CalendarTone
}

export interface MemoryLevel {
  level: string
  name: string
  count: number
  hint: string
}

export interface AgentConfig {
  provider: string
  model: string
  maxTokens: number
  concurrency: number
  temperature: number
}

export interface AgentProfile {
  bio: string
  load: number
  groups: string[]
  capabilities: string[]
  memoryByLevel: MemoryLevel[]
  config: AgentConfig
}

export interface Provider {
  id: string
  label: string
  models: string[]
}

/** Icon 组件支持的图标名（映射到 lucide-react），见 components/ui/Icon.tsx */
export type IconName =
  | 'inbox'
  | 'listCheck'
  | 'calendar'
  | 'chat'
  | 'activity'
  | 'channels'
  | 'files'
  | 'sparkle'
  | 'brain'
  | 'settings'
  | 'search'
  | 'plus'
  | 'chevronDown'
  | 'panelLeft'
  | 'panelRight'
  | 'info'
  | 'moreHorizontal'
  | 'check'
  | 'diff'
  | 'doc'
  | 'sun'
  | 'moon'
  | 'send'
  | 'paperclip'
  | 'bold'
  | 'smile'
  | 'atSign'
  | 'chevronUp'
  | 'list'
  | 'grid'
  | 'x'
  | 'network'
  | 'zap'
  | 'clock'
  | 'shieldCheck'
  | 'pin'
  | 'chevronLeft'
  | 'chevronRight'
  | 'sliders'
  | 'pencil'
  | 'trash2'

// ── 后端 API DTO（与 backend schema 对齐，字段为 snake_case）──

/** 对应 backend `AgentOut`（schemas/agent.py）。注意与 UI 的 `Agent` 区分。 */
export interface ApiAgent {
  id: string
  name: string
  avatar: string
  role: string
  agent_system: string
  provider: string
  model: string
  status: string
  skills: string[]
  capability_tags: string[]
  is_system: boolean
  created_at: string
}

/** 对应 backend `GroupMemberOut`。 */
export interface ApiGroupMember {
  id: string
  name: string
  role: string
}

/** 对应 backend 协调者摘要（GroupOut.coordinator）。 */
export interface ApiGroupCoordinator {
  id: string
  name: string
  role: string
  agent_system: string
  is_system: boolean
}

/** 对应 backend `GroupOut`（schemas/group.py）。注意与 UI 的 `Group` 区分。 */
export interface ApiGroup {
  id: string
  name: string
  description: string
  coordinator: ApiGroupCoordinator
  members: ApiGroupMember[]
  created_at: string
}

/** 对应 backend `SessionOut`（schemas/session.py）。 */
export interface Session {
  id: string
  type: string
  title: string
  group_id: string | null
  agent_id: string | null
  workspace_path: string
  created_at: string
}

/** 对应 backend `StreamEventType`（domain/llm/protocol.py）。 */
export type StreamEventType =
  | 'text'
  | 'thinking'
  | 'tool_call'
  | 'tool_result'
  | 'request_approval'
  | 'task_plan'
  | 'error'
  | 'done'

/** 对应 backend `StreamEvent`（WS 服务端→客户端逐事件推送）。 */
export interface StreamEvent {
  type: StreamEventType
  seq: number
  content?: string | null
  metadata?: Record<string, unknown>
  /** 群聊场景下标识发言人；私聊为 null。前端按此分色气泡 / 路由到 messagesByGroup。 */
  sender_agent_id?: string | null
}

// ─── 记忆系统 V3 ──────────────────────────────────────────────────────────────

export type MemoryType = 'facts' | 'preferences' | 'procedures' | 'context'

/** 对应 backend `MemoryOut`（schemas/memory.py）。 */
export interface ApiMemory {
  id: string
  agent_id: string
  group_id: string | null
  user_id: string
  scope: 'agent' | 'group'
  name: string
  description: string
  memory_type: MemoryType
  content: string
  source: 'manual' | 'chat' | 'system'
  pinned: boolean
  hits: number
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

/** 对应 backend `MemoryStatsOut`。 */
export interface ApiMemoryStats {
  total: number
  by_type: Record<string, number>
  oldest: string | null
  newest: string | null
}
