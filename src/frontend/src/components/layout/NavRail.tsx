import { useState } from 'react'
import { cn } from '../../lib/cn'
import { user } from '../../data/mock'
import { useUIStore, type Section } from '../../stores/uiStore'
import { useChatStore } from '../../stores/chatStore'
import { Avatar, Icon } from '../ui'
import type { IconName } from '../../types'
import { HelpModal } from '../settings/HelpModal'

/** 4 个主功能 + 设置入口 */
interface RailItem {
  key: string
  icon: IconName
  label: string
  section?: Section
}

const RAIL_ITEMS: RailItem[] = [
  { key: 'chat', icon: 'chat', label: '会话', section: 'chat' },
  { key: 'agent', icon: 'users', label: 'AI 队友', section: 'agent-detail' },
  { key: 'group', icon: 'channels', label: '群组', section: 'groups' },
  { key: 'skill', icon: 'lock', label: 'Skill', section: 'skills-market' },
]

export function NavRail() {
  const { section, setSection, theme, toggleTheme } = useUIStore()
  const unreadByConv = useChatStore((s) => s.unreadByConv)
  const [helpOpen, setHelpOpen] = useState(false)
  // 总未读（任意会话有新消息）—— 给 chat 入口加红点
  const totalUnread = Object.values(unreadByConv).reduce((a, b) => a + b, 0)

  return (
    <>
      <aside
        aria-label="主导航"
        className="glass-panel flex h-full w-[clamp(56px,4.5vw,88px)] flex-col items-center rounded-2xl border shadow-sm"
      >
        {/* ── 顶部：用户头像 ── */}
        <div className="pt-3">
          <Avatar initial={user.initial} color="neutral" size={32} online />
        </div>

        {/* ── 中部：主功能 + 用量入口 ── */}
        <nav className="mt-4 flex flex-1 flex-col items-center gap-1">
          {RAIL_ITEMS.map((item) => {
            const active = !!item.section && section === item.section
            const showUnread = item.key === 'chat' && totalUnread > 0
            const onClick = item.section
              ? () => setSection(item.section!)
              : undefined
            return (
              <button
                key={item.key}
                onClick={onClick}
                title={item.label}
                aria-label={item.label}
                aria-current={active ? 'page' : undefined}
                data-active={active ? 'true' : undefined}
                className={cn(
                  'group relative grid h-[clamp(36px,2.6vw,44px)] w-[clamp(36px,2.6vw,44px)] place-items-center rounded-lg text-muted-foreground transition-colors',
                  'hover:bg-accent hover:text-foreground',
                  'data-[active=true]:bg-brand/15 data-[active=true]:text-brand',
                  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
                )}
              >
                {active && (
                  <span
                    aria-hidden
                    className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-brand"
                  />
                )}
                <Icon
                  name={item.icon}
                  className="h-[clamp(14px,1.1vw,18px)] w-[clamp(14px,1.1vw,18px)]"
                  strokeWidth={active ? 2.25 : 1.75}
                />
                {showUnread && (
                  <span
                    aria-label={`${totalUnread} 条未读`}
                    className="absolute -right-0.5 -top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-destructive px-1 font-mono text-[9.5px] font-bold leading-none text-destructive-foreground shadow-sm ring-2 ring-background"
                  >
                    {totalUnread > 99 ? '99+' : totalUnread}
                  </span>
                )}
              </button>
            )
          })}
        </nav>

        {/* ── 底部：主题切换 / 帮助 / 设置 ── */}
        <div className="mb-3 flex flex-col items-center gap-1">
          <button
            onClick={toggleTheme}
            title={theme === 'dark' ? '切换到浅色' : '切换到暗色'}
            aria-label="切换主题"
            className="grid h-[clamp(36px,2.6vw,44px)] w-[clamp(36px,2.6vw,44px)] place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
          >
            <Icon
              name={theme === 'dark' ? 'sun' : 'moon'}
              className="h-[clamp(14px,1.1vw,18px)] w-[clamp(14px,1.1vw,18px)]"
            />
          </button>
          <button
            onClick={() => setHelpOpen(true)}
            title="帮助与反馈"
            aria-label="帮助与反馈"
            className="grid h-[clamp(36px,2.6vw,44px)] w-[clamp(36px,2.6vw,44px)] place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
          >
            <Icon name="info" className="h-[clamp(14px,1.1vw,18px)] w-[clamp(14px,1.1vw,18px)]" />
          </button>
          <button
            onClick={() => setSection('settings')}
            title="设置"
            aria-label="设置"
            aria-current={section === 'settings' ? 'page' : undefined}
            data-active={section === 'settings' ? 'true' : undefined}
            className={cn(
              'group relative grid h-[clamp(36px,2.6vw,44px)] w-[clamp(36px,2.6vw,44px)] place-items-center rounded-lg text-muted-foreground transition-colors',
              'hover:bg-accent hover:text-foreground',
              'data-[active=true]:bg-brand/15 data-[active=true]:text-brand',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
            )}
          >
            {section === 'settings' && (
              <span
                aria-hidden
                className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-brand"
              />
            )}
            <Icon name="settings" className="h-[clamp(14px,1.1vw,18px)] w-[clamp(14px,1.1vw,18px)]" strokeWidth={section === 'settings' ? 2.25 : 1.75} />
          </button>
        </div>
      </aside>

      <HelpModal open={helpOpen} onOpenChange={setHelpOpen} />
    </>
  )
}
