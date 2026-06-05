import { useEffect, useState } from 'react'
import { cn } from '../../lib/cn'
import { useAgentStore } from '../../stores/agentStore'
import { useChatStore } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { StartChatModal } from '../chat/StartChatModal'
import { Avatar, Badge, Button, Icon } from '../ui'

function Field({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between px-3 py-2">
      <span className="text-[12px] text-muted-foreground">{label}</span>
      <span className="font-mono text-[12px]">{value}</span>
    </div>
  )
}

/**
 * AI 队友「详细」侧抽屉：从右侧划入，宽 420px。
 * - 显示 bio / 能力 / 配置 / 删除
 * - 底部两个动作：发起私聊（直接跳到 chat）、删除
 * - ESC 或点击遮罩关闭
 */
export function AgentDetailDrawer() {
  const { agentDrawerAgentId, closeAgentDrawer, openConversation } = useUIStore()
  const open = agentDrawerAgentId !== null
  const { agents, profiles, removeAgent } = useAgentStore()
  const conversations = useChatStore((s) => s.conversations)
  const addConversation = useChatStore((s) => s.addConversation)
  const [showStartChat, setShowStartChat] = useState(false)

  const agent = agents.find((a) => a.id === agentDrawerAgentId)
  const profile = agent ? profiles[agent.id] : undefined

  // ESC 关闭
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeAgentDrawer()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, closeAgentDrawer])

  if (!open || !agent) return null

  const handleStartChat = () => {
    // 每次点都弹窗：让用户决定"随便聊聊"还是"看看我的项目"，并指定会话名 / 目录
    setShowStartChat(true)
  }

  const handleStartChatConfirm = (name: string, workdir?: string) => {
    const convId = addConversation(agent.id, { name, workdir })
    openConversation(agent.id, convId)
    setShowStartChat(false)
    closeAgentDrawer()
  }

  const handleDelete = () => {
    if (window.confirm(`确定删除队友「${agent.name}」？该操作不可恢复。`)) {
      removeAgent(agent.id)
      closeAgentDrawer()
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end" role="dialog" aria-modal="true">
      {/* 遮罩 */}
      <button
        type="button"
        aria-label="关闭"
        onClick={closeAgentDrawer}
        className="animate-[var(--animate-fade-in)] absolute inset-0 cursor-default bg-black/30 backdrop-blur-sm"
      />

      {/* 抽屉主体 */}
      <aside
        className={cn(
          'animate-[var(--animate-slide-in-right)] relative z-10 flex h-full w-[420px] max-w-[calc(100vw-3rem)] flex-col',
          'border-l border-border bg-card shadow-2xl',
        )}
      >
        <header className="flex items-center gap-3 border-b border-border/70 px-4 py-3">
          <Avatar
            initial={agent.name[0] ?? '?'}
            color={agent.color}
            size={32}
            online={agent.online}
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="truncate text-[15px] font-semibold">{agent.name}</h2>
            </div>
            <div className="truncate text-[12px] text-muted-foreground">{agent.role}</div>
          </div>
          <Button variant="ghost" size="iconSm" onClick={closeAgentDrawer} title="关闭">
            <Icon name="x" className="h-3.5 w-3.5" />
          </Button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {/* 简介 */}
          <section>
            <div className="mb-1.5 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
              简介
            </div>
            <p className="rounded-lg border bg-muted/30 px-3 py-2.5 text-[13px] leading-relaxed text-foreground/90 [text-wrap:pretty]">
              {profile?.bio ?? '暂无简介'}
            </p>
          </section>

          {/* 能力 */}
          {profile?.capabilities && profile.capabilities.length > 0 && (
            <section>
              <div className="mb-1.5 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                能力
              </div>
              <div className="flex flex-wrap gap-1.5">
                {profile.capabilities.map((c) => (
                  <Badge key={c} variant="brand">
                    {c}
                  </Badge>
                ))}
              </div>
            </section>
          )}

          {/* 配置 */}
          {profile?.config && (
            <section>
              <div className="mb-1.5 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                配置
              </div>
              <div className="divide-y divide-border/70 rounded-lg border bg-muted/30">
                <Field label="Provider" value={profile.config.provider} />
                <Field label="模型" value={profile.config.model} />
                <Field label="并发数" value={profile.config.concurrency} />
                <Field label="Temperature" value={profile.config.temperature} />
                <Field label="Max tokens" value={profile.config.maxTokens} />
              </div>
            </section>
          )}

          {/* 所属群组 */}
          {profile?.groups && profile.groups.length > 0 && (
            <section>
              <div className="mb-1.5 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
                所属群组
              </div>
              <div className="flex flex-wrap gap-1.5">
                {profile.groups.map((g) => (
                  <Badge key={g} variant="outline">
                    # {g}
                  </Badge>
                ))}
              </div>
            </section>
          )}
        </div>

        <footer className="flex gap-2 border-t border-border/70 p-3">
          <Button variant="brand" size="sm" className="flex-1" onClick={handleStartChat}>
            <Icon name="chat" className="h-3.5 w-3.5" />
            发起私聊
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDelete}
            className="text-destructive hover:bg-destructive/10"
            title="删除队友"
          >
            <Icon name="trash2" className="h-3.5 w-3.5" />
          </Button>
        </footer>
      </aside>

      {showStartChat && (
        <StartChatModal
          open
          onOpenChange={setShowStartChat}
          agentName={agent.name}
          existingCount={(conversations[agent.id] ?? []).length}
          onConfirm={handleStartChatConfirm}
        />
      )}
    </div>
  )
}
