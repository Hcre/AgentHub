import { memory, skills } from '../../data/extra'
import { useAgentStore } from '../../stores/agentStore'
import { useUIStore } from '../../stores/uiStore'
import { Badge, Icon } from '../ui'
import type { MemoryStatus } from '../../types'

export function SkillsView() {
  const setSection = useUIStore((s) => s.setSection)
  return (
    <div className="mx-auto max-w-2xl space-y-2 px-6 py-5">
      <div className="flex items-center justify-between">
        <span className="text-[12px] text-muted-foreground">已安装 {skills.length} 个技能</span>
        <button
          type="button"
          onClick={() => setSection('skills-market')}
          className="text-[12px] text-brand hover:underline"
        >
          浏览技能市场 →
        </button>
      </div>
      {skills.map((s) => (
        <div key={s.id} className="flex items-start gap-3 rounded-xl border bg-card p-4">
          <div className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-md border bg-muted/30 text-brand">
            <Icon name="sparkle" className="h-4 w-4" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[13px] font-medium">{s.name}</span>
              {s.locked && <Badge variant="outline">已锁定</Badge>}
            </div>
            <p className="mt-0.5 text-[12.5px] text-muted-foreground">{s.desc}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

const STATUS_LABEL: Record<MemoryStatus, string> = {
  accepted: '已采纳',
  pending: '待确认',
  archived: '已归档',
}
const statusVariant = (s: MemoryStatus) =>
  s === 'accepted' ? 'success' : s === 'pending' ? 'warning' : 'outline'

export function MemoryView() {
  return (
    <div className="mx-auto max-w-2xl space-y-2 px-6 py-5">
      {memory.map((m) => (
        <div key={m.id} className="rounded-xl border bg-card p-4">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium">{m.title}</span>
            <Badge variant={statusVariant(m.status)}>{STATUS_LABEL[m.status]}</Badge>
            <div className="flex-1" />
            <span className="font-mono text-[11px] text-muted-foreground">{m.when}</span>
          </div>
          <p className="mt-1 text-[12.5px] text-muted-foreground">{m.body}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {m.tags.map((t) => (
              <Badge key={t} variant="outline">
                {t}
              </Badge>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

export function SettingsView() {
  const activeAgentId = useUIStore((s) => s.activeAgentId)
  const setSection = useUIStore((s) => s.setSection)
  const profiles = useAgentStore((s) => s.profiles)
  const cfg = activeAgentId ? profiles[activeAgentId]?.config : undefined
  if (!cfg) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
        无配置
        <button
          type="button"
          onClick={() => setSection('api-keys')}
          className="text-[13px] text-brand hover:underline"
        >
          API 密钥管理 →
        </button>
      </div>
    )
  }
  const rows: [string, string | number][] = [
    ['Provider', cfg.provider],
    ['Model', cfg.model],
    ['API Key', '••••••••••••'],
    ['Max tokens', cfg.maxTokens],
    ['并发数', cfg.concurrency],
    ['Temperature', cfg.temperature],
  ]
  return (
    <div className="mx-auto max-w-md space-y-3 px-6 py-5">
      <div className="rounded-xl border bg-card p-4">
        {rows.map(([label, value]) => (
          <div
            key={label}
            className="flex items-center justify-between border-b py-2 last:border-b-0"
          >
            <span className="text-[12.5px] text-muted-foreground">{label}</span>
            <span className="font-mono text-[12.5px]">{value}</span>
          </div>
        ))}
      </div>
      <button
        type="button"
        onClick={() => setSection('api-keys')}
        className="text-[13px] text-brand hover:underline"
      >
        API 密钥管理 →
      </button>
    </div>
  )
}
