import { useState } from 'react'
import { cn } from '../../lib/cn'
import { agents, channels, conversations, nav, org, user } from '../../data/mock'
import { useUIStore, type Section } from '../../stores/uiStore'
import { Avatar, Button, Icon, Kbd } from '../ui'
import type { IconName } from '../../types'

function NavRow({
  icon,
  label,
  count,
  active,
  dotted,
  badge,
  onClick,
}: {
  icon?: IconName
  label: string
  count?: number
  active?: boolean
  dotted?: boolean
  badge?: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      data-active={active ? 'true' : undefined}
      className={cn(
        'group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
        'data-[active=true]:bg-accent data-[active=true]:font-medium data-[active=true]:text-foreground',
      )}
    >
      {icon && <Icon name={icon} className="h-4 w-4" />}
      {dotted && (
        <span className="w-4 text-center font-mono text-[13px] text-muted-foreground/70">#</span>
      )}
      <span className="flex-1 truncate text-left">{label}</span>
      {count !== undefined && count > 0 && (
        <span className="font-mono text-[10.5px] tabular-nums text-muted-foreground">{count}</span>
      )}
      {badge && <span className="h-1.5 w-1.5 rounded-full bg-brand" />}
    </button>
  )
}

function SectionHeader({
  label,
  collapsed,
  onToggle,
}: {
  label: string
  collapsed: boolean
  onToggle: () => void
}) {
  return (
    <button
      onClick={onToggle}
      className="mb-1 mt-3 flex items-center gap-1 px-2 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
    >
      <Icon
        name="chevronDown"
        className={cn('h-2.5 w-2.5 transition-transform', collapsed && '-rotate-90')}
      />
      <span>{label}</span>
    </button>
  )
}

export function LeftPanel() {
  const {
    section,
    activeAgentId,
    activeConversationId,
    activeGroupId,
    setSection,
    openConversation,
    openGroup,
    toggleSidebar,
  } = useUIStore()
  const [openCh, setOpenCh] = useState(true)
  const [openAI, setOpenAI] = useState(true)
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ editor: true })

  return (
    <aside className="glass-panel flex h-full w-full flex-col overflow-hidden rounded-2xl border shadow-sm">
      <header className="flex items-center gap-2 px-3 pb-2 pt-3">
        <div className="grid h-7 w-7 place-items-center rounded-md bg-gradient-to-br from-brand to-brand-deep text-sm font-semibold text-brand-foreground shadow-sm">
          {org.initial}
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[14px] font-medium">{org.name}</div>
          <div className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            workspace
          </div>
        </div>
        <Button variant="ghost" size="iconSm" onClick={toggleSidebar} title="收起侧边栏">
          <Icon name="panelLeft" className="h-3.5 w-3.5" />
        </Button>
      </header>

      <div className="px-3 pb-2">
        <div className="flex h-[30px] items-center gap-2 rounded-md border glass-soft px-2.5 text-muted-foreground transition-colors focus-within:border-brand/40">
          <Icon name="search" className="h-3.5 w-3.5" />
          <input
            placeholder="跳转到…"
            className="min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:text-muted-foreground/70"
          />
          <Kbd>⌘K</Kbd>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-2">
        <div className="space-y-px">
          {nav.map((n) => (
            <NavRow
              key={n.id}
              icon={n.icon}
              label={n.label}
              count={n.count}
              active={section === n.id}
              onClick={() => setSection(n.id as Section)}
            />
          ))}
        </div>

        <SectionHeader label="频道" collapsed={!openCh} onToggle={() => setOpenCh((v) => !v)} />
        {openCh && (
          <div className="space-y-px">
            {channels.map((c) => (
              <NavRow
                key={c.id}
                label={c.name}
                dotted
                badge={c.unread}
                active={section === 'group' && activeGroupId === c.id}
                onClick={() => openGroup(c.id)}
              />
            ))}
          </div>
        )}

        <SectionHeader label="AI 队友" collapsed={!openAI} onToggle={() => setOpenAI((v) => !v)} />
        {openAI && (
          <div className="space-y-px">
            {agents.map((a) => {
              const convs = conversations[a.id] ?? []
              const isActive = section === 'chat' && activeAgentId === a.id
              const isOpen = expanded[a.id] ?? false
              return (
                <div key={a.id}>
                  <div
                    role="button"
                    tabIndex={0}
                    data-active={isActive ? 'true' : undefined}
                    onClick={() => convs[0] && openConversation(a.id, convs[0].id)}
                    onKeyDown={(e) => {
                      if ((e.key === 'Enter' || e.key === ' ') && convs[0]) {
                        e.preventDefault()
                        openConversation(a.id, convs[0].id)
                      }
                    }}
                    className={cn(
                      'group/agent flex w-full cursor-pointer items-center gap-2 rounded-md py-1.5 pl-2 pr-1 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                      'data-[active=true]:bg-accent data-[active=true]:font-medium data-[active=true]:text-foreground',
                    )}
                  >
                    <Avatar
                      initial={a.name[0] ?? '?'}
                      color={a.color}
                      size={20}
                      online={a.online}
                    />
                    <span className="flex-1 truncate text-left">{a.name}</span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        setExpanded((m) => ({ ...m, [a.id]: !isOpen }))
                      }}
                      title={isOpen ? '收起历史会话' : '展开历史会话'}
                      className="inline-flex items-center gap-1 rounded border border-transparent bg-brand/10 px-1.5 font-mono text-[9px] uppercase tracking-wider text-brand transition-colors hover:border-brand/30"
                    >
                      <span>AI</span>
                      <Icon
                        name="chevronDown"
                        className={cn('h-2 w-2 transition-transform', !isOpen && '-rotate-90')}
                      />
                    </button>
                  </div>
                  {isOpen && (
                    <div className="mb-1 ml-5 mt-0.5 space-y-px border-l border-border/60 pl-1">
                      {convs.map((c) => {
                        const on = isActive && activeConversationId === c.id
                        return (
                          <button
                            key={c.id}
                            onClick={() => openConversation(a.id, c.id)}
                            data-active={on ? 'true' : undefined}
                            className={cn(
                              'flex w-full items-start gap-2 rounded-md px-2 py-1 text-left text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                              'data-[active=true]:bg-brand/10 data-[active=true]:text-foreground',
                            )}
                          >
                            <span
                              className={cn(
                                'mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full',
                                on ? 'bg-brand' : 'bg-muted-foreground/40',
                              )}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="truncate text-[12.5px]">{c.name}</div>
                              <div className="truncate font-mono text-[10px] text-muted-foreground/80">
                                {c.subtitle}
                              </div>
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </nav>

      <footer className="border-t border-border/70 p-2">
        <div className="flex items-center gap-2 rounded-md border border-border/50 p-2 glass-soft">
          <Avatar initial={user.initial} color="neutral" size={28} online />
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-medium">{user.handle}</div>
            <div className="flex items-center gap-1 font-mono text-[10.5px] text-muted-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              <span>在线</span>
            </div>
          </div>
          <Button variant="ghost" size="iconSm" className="text-muted-foreground">
            <Icon name="moreHorizontal" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </footer>
    </aside>
  )
}
