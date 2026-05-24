// Phase 5 次要视图 mock 数据（结构对照 prototype/src/data.js + data-extra.js）。
// 正式接入见各视图与 PRD §6。

import type {
  Activity,
  AgentProfile,
  CalendarEvent,
  InboxItem,
  MemoryItem,
  Provider,
  Skill,
} from '../types'

export const providers: Provider[] = [
  {
    id: 'anthropic',
    label: 'Anthropic',
    models: ['claude-sonnet-4-5', 'claude-opus-4-5', 'claude-haiku-4-5'],
  },
  {
    id: 'deepseek',
    label: 'DeepSeek',
    models: ['deepseek-chat', 'deepseek-reasoner'],
  },
  {
    id: 'minimax',
    label: 'MiniMax',
    models: ['abab6.5s-chat', 'abab7-chat'],
  },
  {
    id: 'mimo',
    label: 'Xiaomi MiMo',
    models: ['mimo-7b', 'mimo-14b'],
  },
  { id: 'openai', label: 'OpenAI', models: ['gpt-4o', 'gpt-4o-mini', 'o3'] },
  { id: 'azure', label: 'Azure', models: ['gpt-4o-azure', 'gpt-4o-mini-azure'] },
]

/**
 * provider → claude_code 经 proxy 透传的目标端点预设（须为 Anthropic 兼容）。
 * proxy 纯透传只换 auth header，不转协议，故仅支持 Anthropic 兼容端点。
 */
export const PROVIDER_BASE_URL: Record<string, string> = {
  anthropic: 'https://api.anthropic.com',
  deepseek: 'https://api.deepseek.com/anthropic',
}

export const activity: Activity[] = [
  {
    id: 'e1',
    when: '23:26',
    count: 2,
    latest: true,
    running: true,
    tools: ['pricing-v3.mdx 读取', '结构分析', '生成草稿'],
    text: 'Read it. The plans bleed because every tier opens with capacity. Drafting the three openers now — should land in 阶段 as task 1.',
  },
  {
    id: 'e2',
    when: '19:48',
    count: 7,
    tools: ['channel.subscribe', 'memory.recall', 'ack.send'],
    text: "Hi — I'm your content editor. I tighten structure, sharpen claims, fix pacing and tone without sanding off your voice.",
  },
]

export const skills: Skill[] = [
  {
    id: 'heliox',
    name: 'heliox',
    desc: 'Core CLI commands the assistant uses to coordinate work.',
    locked: true,
  },
  {
    id: 'productivity',
    name: 'productivity',
    desc: 'Productivity toolkit — knowledge-work flows.',
    locked: true,
  },
  {
    id: 'document-skills',
    name: 'document-skills',
    desc: 'Work with PDFs, docs, and spreadsheets.',
    locked: true,
  },
  {
    id: 'marketing',
    name: 'marketing',
    desc: 'Positioning, message-mapping, channel-aware drafting.',
    locked: true,
  },
]

export const memory: MemoryItem[] = [
  {
    id: 'm1',
    title: 'Audience for pricing page',
    body: 'Mid-market PMs evaluating against three named competitors.',
    tags: ['audience', 'pricing'],
    status: 'accepted',
    when: '2 天前',
  },
  {
    id: 'm2',
    title: 'Pass type defaults to structural',
    body: 'User skips line edits unless they ask.',
    tags: ['voice'],
    status: 'pending',
    when: '3 天前',
  },
  {
    id: 'm3',
    title: 'Plan-tier naming locked',
    body: "Don't suggest renaming Starter/Team/Business.",
    tags: ['copy'],
    status: 'archived',
    when: '1 周前',
  },
]

export const inbox: InboxItem[] = [
  {
    id: 'in1',
    type: 'approval',
    title: '编辑 想覆盖 pricing-v3.mdx 第 17-43 行',
    summary: 'Three plan openers rewrite — 把每档「unlimited X」替换为一句「这档是给谁」+ 证据点。',
    actor: 'editor',
    actorName: '编辑',
    when: '刚刚',
    diff: [
      { kind: 'del', text: '## Starter — Unlimited drafts' },
      { kind: 'add', text: '## Starter — For solo PMs shipping their first revenue page' },
      { kind: 'neutral', text: 'Used by 1,200 indie PMs since launch.' },
      { kind: 'del', text: '## Team — Unlimited seats' },
      { kind: 'add', text: '## Team — For 3–12 person PM teams sharing one source of truth' },
    ],
    impact: '影响 pricing-v3.mdx (1 个文件) · 27 行',
    unread: true,
  },
  {
    id: 'in2',
    type: 'approval',
    title: '研究员 想把 3 个竞品引用加进 pricing-v3.mdx',
    summary: '在脚注引用 Linear / Notion / Coda 的官方定价页，作为对比表来源。',
    actor: 'researcher',
    actorName: '研究员',
    when: '12 分钟前',
    diff: [
      { kind: 'add', text: '[^1]: Linear pricing — linear.app/pricing · 2026-05-22' },
      { kind: 'add', text: '[^2]: Notion pricing — notion.so/pricing · 2026-05-22' },
      { kind: 'add', text: '[^3]: Coda pricing — coda.io/pricing · 2026-05-22' },
    ],
    impact: '新增 3 个脚注 · 0 个删除',
    unread: true,
  },
  {
    id: 'in3',
    type: 'task',
    title: '你被指派为 MO-6 的复核人',
    summary: 'Audit footnote citations vs source — 协调者把核对脚注的复核环节路给了你。',
    actor: 'coordinator',
    actorName: '协调者',
    when: '30 分钟前',
    unread: true,
  },
  {
    id: 'in4',
    type: 'system',
    title: '文案 已升级到 claude-sonnet-4-5',
    summary: '周一升级后保留全部 system prompt 与已订阅频道。',
    when: '昨天 18:20',
    unread: false,
  },
  {
    id: 'in5',
    type: 'task',
    title: 'MO-4 完成 · Draft 3 hero directions',
    summary: '文案 提交了 3 个 hero 方向 + 推荐一个上线版本。等你过一眼。',
    actor: 'copywriter',
    actorName: '文案',
    when: '昨天 16:42',
    unread: false,
  },
]

/** profile by agentId */
export const agentProfiles: Record<string, AgentProfile> = {
  editor: {
    bio: 'Revises existing drafts for clarity, structure, voice, and trust while preserving the author intent.',
    load: 0.42,
    groups: ['content', 'design'],
    capabilities: [
      'Line edit',
      'Copy edit',
      'Structural',
      'Tone & voice',
      'Pacing',
      'Heading rewrite',
      'Footnote audit',
    ],
    memoryByLevel: [
      { level: 'L1', name: 'Session', count: 14, hint: '活跃对话即时上下文' },
      { level: 'L2', name: 'Project', count: 38, hint: 'Pricing redesign 项目状态' },
      { level: 'L3', name: 'Persona', count: 7, hint: '用户偏好与禁区' },
      { level: 'L4', name: 'World', count: 23, hint: 'Acme 风格与品牌锁定' },
    ],
    config: {
      provider: 'anthropic',
      model: 'claude-sonnet-4-5',
      maxTokens: 8192,
      concurrency: 2,
      temperature: 0.4,
    },
  },
  copywriter: {
    bio: 'Writes from a brief — landing copy, ads, launch announcements, push notifications.',
    load: 0.61,
    groups: ['design', 'growth'],
    capabilities: [
      'Landing pages',
      'Ad copy',
      'Email',
      'Notifications',
      'Headline tests',
      'Microcopy',
    ],
    memoryByLevel: [
      { level: 'L1', name: 'Session', count: 8, hint: '' },
      { level: 'L2', name: 'Project', count: 19, hint: '' },
      { level: 'L3', name: 'Persona', count: 5, hint: '' },
      { level: 'L4', name: 'World', count: 23, hint: '' },
    ],
    config: {
      provider: 'anthropic',
      model: 'claude-sonnet-4-5',
      maxTokens: 4096,
      concurrency: 3,
      temperature: 0.7,
    },
  },
  researcher: {
    bio: 'Digs through sources, synthesizes findings, and surfaces what is load-bearing.',
    load: 0.18,
    groups: ['content', 'growth'],
    capabilities: ['Lit review', 'Competitive scan', 'Synthesis', 'Citations'],
    memoryByLevel: [
      { level: 'L1', name: 'Session', count: 4, hint: '' },
      { level: 'L2', name: 'Project', count: 12, hint: '' },
      { level: 'L3', name: 'Persona', count: 3, hint: '' },
      { level: 'L4', name: 'World', count: 23, hint: '' },
    ],
    config: {
      provider: 'openai',
      model: 'gpt-4o',
      maxTokens: 8192,
      concurrency: 1,
      temperature: 0.2,
    },
  },
}

/** prototype "今天" 锚点 */
export const TODAY_STR = '2026-05-22'

export const calendarEvents: CalendarEvent[] = [
  {
    id: 'ce-may-5',
    date: '2026-05-18',
    startHour: 9,
    endHour: 10,
    title: 'Editor briefing',
    tone: 'brand',
  },
  {
    id: 'ce-may-6',
    date: '2026-05-19',
    startHour: 13,
    endHour: 14,
    title: 'Pricing pass v1',
    tone: 'brand',
  },
  {
    id: 'ce-may-7',
    date: '2026-05-20',
    startHour: 11,
    endHour: 12,
    title: 'Sources review',
    tone: 'sage',
  },
  {
    id: 'ce-may-8',
    date: '2026-05-21',
    startHour: 14,
    endHour: 15,
    title: 'Draft review',
    tone: 'sage',
  },
  {
    id: 'ce-may-9',
    date: '2026-05-22',
    startHour: 11,
    endHour: 12,
    title: 'Pricing pass · 阶段 1',
    tone: 'brand',
  },
  {
    id: 'ce-may-10',
    date: '2026-05-22',
    startHour: 16,
    endHour: 17,
    title: 'Stand-up',
    tone: 'sage',
  },
  {
    id: 'ce-may-11',
    date: '2026-05-26',
    startHour: 10,
    endHour: 11,
    title: 'Eval rubric',
    tone: 'brand',
  },
  {
    id: 'ce-may-12',
    date: '2026-05-28',
    startHour: 14,
    endHour: 16,
    title: 'Launch dry-run',
    tone: 'sage',
  },
]
