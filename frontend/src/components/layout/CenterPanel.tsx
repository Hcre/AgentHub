import { cn } from '../../lib/cn'
import { agents, centerTabs } from '../../data/mock'
import { useUIStore } from '../../stores/uiStore'
import { ChatView } from '../chat/ChatView'
import { Avatar, Badge, Button, Icon } from '../ui'

const SECTION_TITLE: Record<string, string> = {
  inbox: '收件箱',
  tasks: '任务',
  calendar: '日历',
  group: '群组频道',
  'agent-detail': '助手详情',
}

export function CenterPanel() {
  const { section, activeTab, activeAgentId, theme, setActiveTab, toggleTheme, toggleRight } =
    useUIStore()

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

      <div className="min-h-0 flex-1">
        {activeTab === 'chat' ? (
          <ChatView agent={agent} />
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
