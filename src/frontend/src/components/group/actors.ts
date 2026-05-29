import { useAgentStore } from '../../stores/agentStore'
import { user as mockUser } from '../../data/mock'
import type { AgentColor, Group } from '../../types'

export interface Actor {
  name: string
  color: AgentColor
  initial: string
  online?: boolean
}

const PALETTE: AgentColor[] = ['brand', 'sage', 'clay', 'rose', 'blue']

/** 给一个未知 UUID 一个稳定但不会撞 'neutral' 的颜色。 */
function fallbackColor(id: string): AgentColor {
  let sum = 0
  for (let i = 0; i < id.length; i += 1) sum = (sum + id.charCodeAt(i)) >>> 0
  return PALETTE[sum % PALETTE.length] ?? 'neutral'
}

/**
 * who（agentId | 'user' | 'unknown'）→ 展示用 Actor。
 *
 * 协调者通常是 is_system=true，被 agentStore.loadAgents() 过滤掉；
 * 通过传入 `group` 让本函数走 Group.coordinatorName 等冗余字段兜底。
 */
export function lookupActor(who: string, group?: Group): Actor {
  if (who === 'user') {
    return { name: mockUser.handle, color: 'neutral', initial: mockUser.initial }
  }

  // 1. 普通成员 — 查 agentStore（包含 loadAgents 过滤后的 Agent）
  const { agents } = useAgentStore.getState()
  const hit = agents.find((a) => a.id === who)
  if (hit) {
    return {
      name: hit.name,
      color: hit.color,
      initial: hit.name[0] ?? '?',
      online: hit.online,
    }
  }

  // 2. 协调者 — 不在 agentStore（is_system），走 group 上的冗余字段
  if (group && group.coordinatorId === who) {
    const name = group.coordinatorName ?? '协调者'
    return {
      name,
      color: 'brand',
      initial: name[0] ?? '协',
      online: true,
    }
  }

  // 3. 未知 UUID 兜底 — 取前 8 位 + 哈希色
  const short = who.slice(0, 8)
  return {
    name: short || '未知',
    color: fallbackColor(who),
    initial: (short[0] ?? '?').toUpperCase(),
  }
}
