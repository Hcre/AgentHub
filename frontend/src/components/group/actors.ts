import { agents, user } from '../../data/mock'
import { coordinator } from '../../data/groups'
import type { AgentColor } from '../../types'

export interface Actor {
  name: string
  color: AgentColor
  initial: string
  online?: boolean
}

/** who（agentId | 'coordinator' | 'user'）→ 展示用的 Actor。 */
export function lookupActor(who: string): Actor {
  if (who === 'user') return { name: user.handle, color: 'neutral', initial: user.initial }
  if (who === coordinator.id) {
    return {
      name: coordinator.name,
      color: coordinator.color,
      initial: coordinator.name[0] ?? '协',
      online: coordinator.online,
    }
  }
  const a = agents.find((x) => x.id === who)
  if (a) return { name: a.name, color: a.color, initial: a.name[0] ?? '?', online: a.online }
  return { name: who, color: 'neutral', initial: who[0] ?? '?' }
}
