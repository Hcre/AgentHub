import { useState } from 'react'
import { useAgentStore } from '../../stores/agentStore'
import { useUIStore } from '../../stores/uiStore'
import { MemoryPanel } from '../memory/MemoryPanel'
import { Avatar, Badge, Button, Icon, Tabs, TabsList, TabsTrigger } from '../ui'

const TABS = [
  { id: 'overview', label: '概览' },
  { id: 'capabilities', label: '能力' },
  { id: 'memory', label: '记忆' },
  { id: 'settings', label: '设置' },
]

function Field({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between border-b py-2 last:border-b-0">
      <span className="text-[12.5px] text-muted-foreground">{label}</span>
      <span className="font-mono text-[12.5px]">{value}</span>
    </div>
  )
}

export function AgentDetailPage() {
  const activeAgentId = useUIStore((s) => s.activeAgentId)
  const setSection = useUIStore((s) => s.setSection)
  const { agents, profiles, updateConfig, removeAgent } = useAgentStore()
  const [tab, setTab] = useState('overview')
  const [confirmDelete, setConfirmDelete] = useState(false)

  const agent = agents.find((a) => a.id === activeAgentId)
  const profile = activeAgentId ? profiles[activeAgentId] : undefined
  if (!agent || !profile) {
    return (
      <div className="glass-panel flex h-full items-center justify-center rounded-2xl border text-sm text-muted-foreground shadow-sm">
        未找到该助手
      </div>
    )
  }

  return (
    <div className="glass-panel flex h-full flex-col overflow-hidden rounded-2xl border shadow-sm">
      <header className="flex items-center gap-3 border-b border-border/70 px-5 py-4">
        <Button variant="ghost" size="iconSm" onClick={() => setSection('chat')} title="返回">
          <Icon name="chevronLeft" className="h-4 w-4" />
        </Button>
        <Avatar
          initial={agent.name[0] ?? '?'}
          color={agent.color}
          size={32}
          online={agent.online}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h1 className="text-[18px] font-medium">{agent.name}</h1>
          </div>
          <div className="text-[12.5px] text-muted-foreground">{agent.role}</div>
        </div>
        <div className="text-right">
          <div className="font-mono text-[11px] text-muted-foreground">负载</div>
          <div className="text-[15px] font-semibold text-brand">
            {Math.round(profile.load * 100)}%
          </div>
        </div>
      </header>

      <nav className="border-b border-border/70 px-4 py-2">
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="h-8">
            {TABS.map((t) => (
              <TabsTrigger key={t.id} value={t.id} className="h-6 px-3 text-[12px]">
                {t.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </nav>

      <div className="min-h-0 flex-1 overflow-y-auto p-5">
        {tab === 'overview' && (
          <div className="mx-auto max-w-2xl space-y-4">
            <p className="text-[13.5px] leading-relaxed text-foreground/90 [text-wrap:pretty]">
              {profile.bio}
            </p>
            <div className="rounded-xl border bg-card p-4">
              <div className="mb-2 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                所属群组
              </div>
              <div className="flex flex-wrap gap-1.5">
                {profile.groups.map((g) => (
                  <Badge key={g} variant="outline">
                    # {g}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        )}

        {tab === 'capabilities' && (
          <div className="mx-auto flex max-w-2xl flex-wrap gap-2">
            {profile.capabilities.map((c) => (
              <Badge key={c} variant="brand">
                {c}
              </Badge>
            ))}
          </div>
        )}

        {tab === 'memory' && (
          <div className="-m-5 h-[calc(100%+2.5rem)]">
            <MemoryPanel agentId={agent.id} agentName={agent.name} />
          </div>
        )}

        {tab === 'settings' && (
          <div className="mx-auto max-w-md space-y-4">
            <div className="rounded-xl border bg-card p-4">
              <Field label="Provider" value={profile.config.provider} />
              <Field label="Model" value={profile.config.model} />
              <Field label="API Key" value="••••••••••••" />
              <div className="flex items-center justify-between border-b py-2">
                <span className="text-[12.5px] text-muted-foreground">Max tokens</span>
                <input
                  type="number"
                  value={profile.config.maxTokens}
                  onChange={(e) => updateConfig(agent.id, { maxTokens: Number(e.target.value) })}
                  className="h-7 w-24 rounded border border-input bg-transparent px-2 text-right font-mono text-[12.5px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>
              <div className="flex items-center justify-between border-b py-2">
                <span className="text-[12.5px] text-muted-foreground">并发数</span>
                <input
                  type="number"
                  value={profile.config.concurrency}
                  onChange={(e) => updateConfig(agent.id, { concurrency: Number(e.target.value) })}
                  className="h-7 w-24 rounded border border-input bg-transparent px-2 text-right font-mono text-[12.5px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-[12.5px] text-muted-foreground">Temperature</span>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  value={profile.config.temperature}
                  onChange={(e) => updateConfig(agent.id, { temperature: Number(e.target.value) })}
                  className="h-7 w-24 rounded border border-input bg-transparent px-2 text-right font-mono text-[12.5px] outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </div>
            </div>

            <div className="rounded-xl border border-destructive/40 p-4">
              <div className="text-[12.5px] font-medium text-destructive">危险区</div>
              <p className="mt-1 text-[12px] text-muted-foreground">
                删除后该助手的会话与配置不可恢复。
              </p>
              {confirmDelete ? (
                <div className="mt-3 flex items-center gap-2">
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => {
                      removeAgent(agent.id)
                      setSection('chat')
                    }}
                  >
                    确认删除
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => setConfirmDelete(false)}>
                    取消
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3 text-destructive"
                  onClick={() => setConfirmDelete(true)}
                >
                  <Icon name="x" className="h-3.5 w-3.5" />
                  删除助手
                </Button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
