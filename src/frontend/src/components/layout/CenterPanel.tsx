import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { centerTabs } from '../../data/mock'
import { useAgentStore } from '../../stores/agentStore'
import { useUIStore } from '../../stores/uiStore'
import { ActivityFeed } from '../activity/ActivityFeed'
import { AgentDetailPage } from '../agent/AgentDetailPage'
import { CalendarView } from '../calendar/CalendarView'
import { ChatView } from '../chat/ChatView'
import { GroupChatView } from '../group/GroupChatView'
import { InboxView } from '../inbox/InboxView'
import { TasksTabView } from '../tasks/TasksTabView'
import { ApiKeyManager } from '../settings/ApiKeyManager'
import { SkillMarketplacePage } from '../skills/SkillMarketplacePage'
import { MemoryView, SettingsView, SkillsView } from '../views/TabViews'
import { Avatar, Badge, Button, Icon } from '../ui'
import type { Agent } from '../../types'

/** 中心区 chat tab 内各子视图 */
function TabContent({
  tab,
  agent,
  conversationId,
}: {
  tab: string
  agent: Agent
  conversationId: string | null
}) {
  switch (tab) {
    case 'chat':
      return <ChatView agent={agent} key={conversationId ?? agent.id} />
    case 'tasks':
      return <TasksTabView />
    case 'activity':
      return <ActivityFeed />
    case 'calendar':
      return <CalendarView />
    case 'skills':
      return <SkillsView />
    case 'memory':
      return <MemoryView />
    case 'settings':
      return <SettingsView />
    default:
      return (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
          「{centerTabs.find((t) => t.id === tab)?.label ?? tab}」视图将在后续 Phase 实现。
        </div>
      )
  }
}

function Panel({ children }: { children: ReactNode }) {
  return (
    <div className="glass-panel h-full overflow-hidden rounded-2xl border shadow-sm">
      {children}
    </div>
  )
}

export function CenterPanel() {
  const { section, activeTab, activeAgentId, activeConversationId, theme, setActiveTab, toggleTheme, toggleRight } =
    useUIStore()
  const agents = useAgentStore((s) => s.agents)

  if (section === 'group') return <GroupChatView />
  if (section === 'agent-detail') return <AgentDetailPage />
  if (section === 'skills-market') return <SkillMarketplacePage />
  if (section === 'api-keys') return <ApiKeyManager />
  if (section === 'tasks')
    return (
      <Panel>
        <TasksTabView />
      </Panel>
    )
  if (section === 'inbox')
    return (
      <Panel>
        <InboxView />
      </Panel>
    )
  if (section === 'calendar')
    return (
      <Panel>
        <CalendarView />
      </Panel>
    )

  const agent = agents.find((a) => a.id === activeAgentId) ?? agents[0]
  if (!agent)
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center text-muted-foreground">
          <div className="mb-2 text-4xl">🤖</div>
          <div className="text-sm">还没有 Agent</div>
          <div className="mt-1 text-xs">在左侧面板点击 AI 队友旁的 + 创建第一个</div>
        </div>
      </div>
    )

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
        <TabContent tab={activeTab} agent={agent} conversationId={activeConversationId} />
      </div>
    </div>
  )
}
