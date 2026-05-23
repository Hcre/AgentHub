import { create } from 'zustand'
import { agents } from '../data/mock'
import { coordinator, groupMessages, groups } from '../data/groups'
import { nowStamp, uid } from '../lib/id'
import type { Group, GroupMessage } from '../types'

export interface SendGroupOptions {
  requiresApproval?: boolean
}

// ════════════════════════════════════════════════════════════════════
// MOCK SEAM — 假群聊的全部"智能"都在这里。
// 真实接入时：删掉 simulateGroupReply，sendGroup 改为 POST /api/groups/{id}/messages
// （或 WS 发送），协调者/成员的回复由后端推送，前端只负责把推来的 GroupMessage
//  append 到 messagesByGroup。详见 src/components/group/HANDOFF.md。
// ════════════════════════════════════════════════════════════════════

/** 解析 @mention，返回被点名的名字列表（去掉 @）。 */
function parseMentions(text: string): string[] {
  return (text.match(/@(\S+)/g) ?? []).map((m) => m.slice(1))
}

/**
 * 假协调者/成员回复。根据 @mention 决定谁回：
 * - @协调者 → 返回一份结构化分发方案（kind: 'plan'）
 * - @某成员 → 该成员 ack
 * - 无 @     → 协调者兜底 ack
 * 真实后端会用 LLM 编排替换这段；签名 (group, text) → GroupMessage 保持稳定即可平滑替换。
 */
export function simulateGroupReply(group: Group, text: string): GroupMessage {
  const mentioned = parseMentions(text)

  if (mentioned.includes(coordinator.name) || mentioned.includes('协调者')) {
    const members = group.members
    return {
      id: uid('gr'),
      from: 'agent',
      who: 'coordinator',
      time: nowStamp(),
      kind: 'plan',
      plan: {
        summary: '我把它拆成几个子任务并分给合适的成员，下面是分发方案（mock 数据）。',
        steps: members.map((who, i) => ({
          id: `s${i + 1}`,
          who,
          label: `${agents.find((a) => a.id === who)?.name ?? who} 负责的子任务 ${i + 1}`,
          eta: 20 + i * 5,
          depends: i === 0 ? [] : [`s${i}`],
        })),
        watchouts: ['这是占位方案，真实拆解由协调者 LLM 生成。'],
      },
    }
  }

  const targetName = mentioned[0]
  const target = targetName
    ? agents.find((a) => a.name === targetName && group.members.includes(a.id))
    : undefined
  if (target) {
    return {
      id: uid('gr'),
      from: 'agent',
      who: target.id,
      time: nowStamp(),
      text: `收到，我走一下，有结果同步到频道。`,
    }
  }

  return {
    id: uid('gr'),
    from: 'agent',
    who: 'coordinator',
    time: nowStamp(),
    text: '收到。我看一下上下文，20 秒后给一份拆分方案。',
  }
}
// ════════════════════════════════════════════════════════════════════
// END MOCK SEAM
// ════════════════════════════════════════════════════════════════════

interface GroupState {
  groups: Group[]
  messagesByGroup: Record<string, GroupMessage[]>

  sendGroup: (groupId: string, text: string, opts?: SendGroupOptions) => void
}

export const useGroupStore = create<GroupState>((set, get) => ({
  groups,
  messagesByGroup: { ...groupMessages },

  sendGroup: (groupId, text, opts) => {
    const userMsg: GroupMessage = {
      id: uid('gu'),
      from: 'user',
      who: 'user',
      time: nowStamp(),
      text,
      requiresApproval: opts?.requiresApproval,
    }
    set((s) => ({
      messagesByGroup: {
        ...s.messagesByGroup,
        [groupId]: [...(s.messagesByGroup[groupId] ?? []), userMsg],
      },
    }))

    const group = get().groups.find((g) => g.id === groupId)
    if (!group) return
    window.setTimeout(() => {
      const reply = simulateGroupReply(group, text)
      set((s) => ({
        messagesByGroup: {
          ...s.messagesByGroup,
          [groupId]: [...(s.messagesByGroup[groupId] ?? []), reply],
        },
      }))
    }, 1200)
  },
}))
