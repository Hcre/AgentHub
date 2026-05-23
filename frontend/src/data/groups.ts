// 群组 / 协调者 mock 数据（结构对照 prototype/src/data-extra.js）。
// 接真实后端后，这些应来自 GET /api/groups 等，见 components/group/HANDOFF.md。

import type { Coordinator, Group, GroupMessage } from '../types'

export const coordinator: Coordinator = {
  id: 'coordinator',
  name: '协调者',
  role: 'Coordinator',
  color: 'brand',
  online: true,
  bio: '我读懂团队需要什么，把它拆成合适形状的子任务，分给合适的助手。在频道里 @协调者 并告诉我你想要的结果。',
}

export const groups: Group[] = [
  {
    id: 'content',
    name: 'content',
    description: 'Long-form drafts, launch posts, narrative work.',
    members: ['editor', 'copywriter', 'researcher'],
    pinnedTask: 'Q4 launch post draft v3',
  },
  {
    id: 'design',
    name: 'design',
    description: 'Pricing page redesign · shared between editor and PM.',
    members: ['editor', 'copywriter'],
    pinnedTask: 'Pricing page restructure',
  },
  {
    id: 'growth',
    name: 'growth',
    description: 'Ads, lifecycle copy, retention experiments.',
    members: ['copywriter', 'researcher'],
    pinnedTask: 'Lifecycle email sequence',
  },
]

/** 群聊种子消息（仅 design 频道有示例，含协调者分发方案卡）。 */
export const groupMessages: Record<string, GroupMessage[]> = {
  design: [
    {
      id: 'g1',
      from: 'user',
      who: 'user',
      time: '10月22日 14:02',
      text: '@协调者 帮我把定价页改稿这件事拆一下。需要：三个套餐开头重写、价格表挪到下面、对比表脚注收紧。周五前要发评审。',
    },
    {
      id: 'g2',
      from: 'agent',
      who: 'coordinator',
      time: '10月22日 14:02',
      kind: 'plan',
      plan: {
        summary: '我把这个拆成 3 个并行子任务，全部目标周四晚结，周五一起进评审。',
        steps: [
          { id: 's1', who: 'editor', label: '三套餐开头一句话 + 证据点', eta: 25, depends: [] },
          { id: 's2', who: 'editor', label: '价格表下移到价值主张下方', eta: 15, depends: ['s1'] },
          {
            id: 's3',
            who: 'researcher',
            label: '拉取三家竞品最新定价页 (来源)',
            eta: 30,
            depends: [],
          },
          { id: 's4', who: 'editor', label: '依据来源收紧对比表脚注', eta: 20, depends: ['s3'] },
        ],
        watchouts: ['Starter / Team / Business 三档名称已锁，不改。'],
      },
    },
    {
      id: 'g3',
      from: 'agent',
      who: 'editor',
      time: '10月22日 14:04',
      text: '收到 s1 + s2 + s4。开头三句正在写，半小时内回。',
    },
    {
      id: 'g4',
      from: 'agent',
      who: 'researcher',
      time: '10月22日 14:05',
      text: '抓 s3。已经在拉 Linear / Notion / Coda 的当前定价页，30 分钟内出对照表 + 引用链接。',
    },
  ],
}
