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
  pinnedTask?: string
}

/** 协调者：编排群组工作的特殊 agent。 */
export interface Coordinator {
  id: 'coordinator'
  name: string
  role: string
  color: AgentColor
  online: boolean
  bio: string
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
 * 群聊消息。`who` 取值：agentId | 'coordinator' | 'user'。
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
