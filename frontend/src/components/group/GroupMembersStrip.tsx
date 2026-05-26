import { Avatar } from '../ui'
import { lookupActor } from './actors'
import type { Group } from '../../types'

export function GroupMembersStrip({
  group,
  onPick,
}: {
  group: Group
  onPick: (id: string) => void
}) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex -space-x-1.5">
        {group.members.map((id) => {
          const a = lookupActor(id, group)
          return (
            <button
              key={id}
              onClick={() => onPick(id)}
              title={a.name}
              className="rounded-full ring-2 ring-background transition-transform hover:-translate-y-0.5"
            >
              <Avatar initial={a.initial} color={a.color} size={26} online={a.online} />
            </button>
          )
        })}
      </div>
      <span className="ml-1 font-mono text-[10.5px] text-muted-foreground">
        {group.members.length} 个成员
      </span>
    </div>
  )
}
