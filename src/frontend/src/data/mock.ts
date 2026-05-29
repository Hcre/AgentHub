// Phase 1 布局所需的 mock 数据（结构对照 prototype/src/data.js）。
// 正式 mock 层与 API 桥接见 Phase 7。

import type {
  Agent,
  CenterTab,
  Channel,
  ChatMessage,
  Conversation,
  NavItem,
  OrgInfo,
  OutputFile,
  StageTask,
  Task,
  UserInfo,
} from '../types'

export const org: OrgInfo = { name: 'Acme', initial: 'A' }

export const user: UserInfo = { handle: 'xiangbianpangde', name: '旁边胖的', initial: 'T' }

export const nav: NavItem[] = [
  { id: 'inbox', icon: 'inbox', label: '收件箱', count: 3 },
  { id: 'tasks', icon: 'listCheck', label: '任务', count: 7 },
  { id: 'calendar', icon: 'calendar', label: '日历' },
]

export const channels: Channel[] = [
  { id: 'content', name: 'content', unread: false },
  { id: 'design', name: 'design', unread: true },
  { id: 'growth', name: 'growth', unread: false },
]

export const agents: Agent[] = [
  {
    id: 'editor',
    name: '编辑',
    role: 'Content editor',
    color: 'brand',
    online: true,
    skillCount: 4,
  },
  {
    id: 'copywriter',
    name: '文案',
    role: 'Copywriter',
    color: 'sage',
    online: true,
    skillCount: 6,
  },
  {
    id: 'researcher',
    name: '研究员',
    role: 'Researcher',
    color: 'clay',
    online: false,
    skillCount: 3,
  },
]

export const conversations: Record<string, Conversation[]> = {
  editor: [
    { id: 'c1', name: '对话 1', subtitle: 'Q4 launch post' },
    { id: 'c2', name: '对话 2', subtitle: 'Pricing page draft' },
    { id: 'c3', name: '对话 3', subtitle: 'Investor memo' },
  ],
  copywriter: [{ id: 'c1', name: '对话 1', subtitle: 'Hero copy v3' }],
  researcher: [{ id: 'c1', name: '对话 1', subtitle: 'Agent market scan' }],
}

export const centerTabs: CenterTab[] = [
  { id: 'chat', icon: 'chat', label: '聊天' },
  { id: 'tasks', icon: 'listCheck', label: '任务' },
  { id: 'activity', icon: 'activity', label: '活动' },
  { id: 'calendar', icon: 'calendar', label: '日历' },
  { id: 'channels', icon: 'channels', label: '频道' },
  { id: 'files', icon: 'files', label: '文件' },
  { id: 'skills', icon: 'sparkle', label: '技能' },
  { id: 'memory', icon: 'brain', label: '记忆' },
  { id: 'settings', icon: 'settings', label: '设置' },
]

/** messages[agentId][conversationId] */
export const messages: Record<string, Record<string, ChatMessage[]>> = {
  editor: {
    c2: [
      {
        id: 'm1',
        from: 'agent',
        time: '19:48',
        text: "Hi — I'm your content editor. I work on drafts you already have: tightening structure, sharpening claims, fixing pacing and tone, cutting throat-clearing without sanding off your voice.\n\nSend me anything you want a closer read on — a post, an email, a doc, a headline — and tell me who it's for and what kind of pass you want.",
      },
      {
        id: 'm2',
        from: 'user',
        time: '19:51',
        text: 'Pricing page draft attached. Audience is mid-market PMs evaluating us against three named competitors. Want a structural pass — the three plans bleed together right now.',
        attachment: { name: 'pricing-v3.mdx', size: '8.4 KB' },
      },
      {
        id: 'm3',
        from: 'agent',
        time: '19:52',
        text: 'Read it. The plans bleed because every tier opens with capacity instead of the job each tier is for. I’ll rewrite each opener as a one-sentence "who this is for" + the proof point, then move pricing below. Drafting now — should land in 阶段 as task 1.',
        actions: ['Open diff', 'View outline'],
      },
    ],
  },
  copywriter: {
    c1: [
      {
        id: 'm1',
        from: 'agent',
        time: '14:02',
        text: "Hi — I'm your copywriter. Give me the audience, the offer, and the one thing they should walk away with, and I'll come back with 3 directions plus the one I'd ship.",
      },
    ],
  },
  researcher: {
    c1: [
      {
        id: 'm1',
        from: 'agent',
        time: '10:14',
        text: "Hi — I'm your researcher. Give me a question and a deadline; I'll come back with a synthesis, sources, and the open questions worth a second pass.",
      },
    ],
  },
}

export const stage: StageTask[] = [
  { id: 't1', label: 'Rewrite three plan openers', state: 'doing', eta: 8 },
  { id: 't2', label: 'Move pricing table below value props', state: 'todo', eta: 5 },
  { id: 't3', label: 'Tighten comparison footnotes', state: 'todo', eta: 3 },
]

export const outputs: OutputFile[] = [
  { id: 'f1', name: 'pricing-v3.mdx', kind: 'doc', size: '8.4 KB', status: 'input' },
  { id: 'f2', name: 'pricing-v3-edited.diff', kind: 'diff', size: '—', status: 'pending' },
]

export const tasks: Task[] = [
  {
    id: 'MO-1',
    title: 'Rewrite three plan openers',
    status: 'todo',
    priority: 'high',
    assignee: 'editor',
    due: 'Today',
  },
  {
    id: 'MO-2',
    title: 'Move pricing table below value props',
    status: 'todo',
    priority: 'normal',
    assignee: 'editor',
    due: 'Wed',
  },
  {
    id: 'MO-3',
    title: 'Tighten comparison footnotes',
    status: 'todo',
    priority: 'low',
    assignee: 'editor',
    due: 'Fri',
  },
  {
    id: 'MO-4',
    title: 'Draft 3 hero directions',
    status: 'doing',
    priority: 'high',
    assignee: 'copywriter',
    due: 'Today',
  },
  {
    id: 'MO-5',
    title: 'Source competitor pricing pages',
    status: 'doing',
    priority: 'normal',
    assignee: 'researcher',
    due: 'Mon',
  },
  {
    id: 'MO-6',
    title: 'Audit footnote citations vs source',
    status: 'blocked',
    priority: 'normal',
    assignee: 'editor',
    due: '—',
  },
  {
    id: 'MO-7',
    title: 'Reconcile copy ↔ design tokens',
    status: 'done',
    priority: 'normal',
    assignee: 'editor',
    due: 'Mon',
  },
]
