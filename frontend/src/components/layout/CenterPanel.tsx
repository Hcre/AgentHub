import { cn } from '../../lib/cn'
import { agents, centerTabs, messages } from '../../data/mock'
import { useUIStore } from '../../stores/uiStore'
import { Avatar, Badge, Button, Icon } from '../ui'
import type { ChatMessage } from '../../types'

const SECTION_TITLE: Record<string, string> = {
  inbox: '收件箱',
  tasks: '任务',
  calendar: '日历',
  group: '群组频道',
  'agent-detail': '助手详情',
}

function MessageBubble({
  msg,
  agentName,
  agentColor,
}: {
  msg: ChatMessage
  agentName: string
  agentColor: 'brand' | 'sage' | 'clay' | 'rose' | 'blue' | 'neutral'
}) {
  const isUser = msg.from === 'user'
  return (
    <div className={cn('flex gap-3', isUser && 'flex-row-reverse')}>
      <Avatar
        initial={isUser ? '我' : (agentName[0] ?? '?')}
        color={isUser ? 'neutral' : agentColor}
        size={28}
      />
      <div className={cn('max-w-[75%] space-y-1', isUser && 'items-end text-right')}>
        <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <span className="font-medium text-foreground">{isUser ? '我' : agentName}</span>
          {!isUser && <Badge variant="brand">AI</Badge>}
          <span className="font-mono">{msg.time}</span>
        </div>
        <div
          className={cn(
            'rounded-xl border px-3 py-2 text-sm leading-relaxed',
            isUser ? 'bg-brand text-brand-foreground' : 'bg-card',
          )}
        >
          {msg.text.split('\n\n').map((p, i) => (
            <p key={i} className={i > 0 ? 'mt-2' : undefined}>
              {p}
            </p>
          ))}
        </div>
        {msg.attachment && (
          <div className="inline-flex items-center gap-2 rounded-md border border-border/60 px-2.5 py-1.5 text-[12px] glass-soft">
            <Icon name="doc" className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="font-mono">{msg.attachment.name}</span>
            <span className="text-muted-foreground">{msg.attachment.size}</span>
          </div>
        )}
        {msg.actions && (
          <div className="flex gap-2 pt-0.5">
            {msg.actions.map((a) => (
              <Button key={a} variant="outline" size="sm">
                {a}
              </Button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function CenterPanel() {
  const {
    section,
    activeTab,
    activeAgentId,
    activeConversationId,
    theme,
    setActiveTab,
    toggleTheme,
    toggleRight,
  } = useUIStore()

  if (section !== 'chat') {
    return (
      <div className="glass-panel flex h-full flex-col items-center justify-center rounded-2xl border text-muted-foreground shadow-sm">
        <h2 className="text-lg font-medium text-foreground">{SECTION_TITLE[section] ?? section}</h2>
        <p className="mt-1 text-sm">该视图将在后续 Phase 实现。</p>
      </div>
    )
  }

  const agent = agents.find((a) => a.id === activeAgentId) ?? agents[0]
  if (!agent) return null
  const list = (activeConversationId && messages[agent.id]?.[activeConversationId]) || []

  return (
    <div className="glass-panel flex h-full flex-col overflow-hidden rounded-2xl border shadow-sm">
      <header className="flex items-center gap-3 border-b border-border/70 px-4 py-3">
        <Avatar
          initial={agent.name[0] ?? '?'}
          color={agent.color}
          size={32}
          online={agent.online}
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h2 className="truncate text-[15px] font-medium">{agent.name}</h2>
            <Badge variant="brand">AI</Badge>
          </div>
          <div className="truncate text-[11.5px] text-muted-foreground">
            {agent.role} · 私密 · 仅你可见
          </div>
        </div>
        <Button variant="ghost" size="iconSm" onClick={toggleTheme} title="切换主题">
          <Icon name={theme === 'light' ? 'moon' : 'sun'} className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="iconSm" onClick={toggleRight} title="收起右侧面板">
          <Icon name="panelRight" className="h-3.5 w-3.5" />
        </Button>
      </header>

      <div className="flex gap-1 overflow-x-auto border-b border-border/70 px-2 py-1.5 [scrollbar-width:none]">
        {centerTabs.map((t) => {
          const on = activeTab === t.id
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              data-active={on ? 'true' : undefined}
              className={cn(
                'flex flex-shrink-0 items-center gap-1.5 rounded-md px-2.5 py-1 text-[13px] text-muted-foreground transition-colors hover:text-foreground',
                'data-[active=true]:bg-accent data-[active=true]:font-medium data-[active=true]:text-foreground',
              )}
            >
              <Icon name={t.icon} className="h-3.5 w-3.5" />
              {t.label}
            </button>
          )
        })}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {activeTab === 'chat' ? (
          <div className="mx-auto flex max-w-3xl flex-col gap-5">
            {list.map((m) => (
              <MessageBubble key={m.id} msg={m} agentName={agent.name} agentColor={agent.color} />
            ))}
          </div>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            「{centerTabs.find((t) => t.id === activeTab)?.label ?? activeTab}」视图将在后续 Phase
            实现。
          </div>
        )}
      </div>
    </div>
  )
}
