import { useState } from 'react'
import { cn } from '../../lib/cn'
import { user } from '../../data/mock'
import { useUIStore, type Section } from '../../stores/uiStore'
import { Avatar, Icon } from '../ui'
import type { IconName } from '../../types'
import { HelpModal } from '../settings/HelpModal'

/** 4 个主功能 + 1 个设置入口。help 不映射到 section，弹模态。 */
interface RailItem {
  key: string
  icon: IconName
  label: string
  /** 命中后高亮的 uiStore.section；undefined = 弹模态而非路由 */
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
  const [helpOpen, setHelpOpen] = useState(false)

  return (
    <>
      <aside
        aria-label="主导航"
        className="glass-panel flex h-full w-[60px] flex-col items-center rounded-2xl border shadow-sm"
      >
        {/* ── 顶部：用户头像 ── */}
        <div className="pt-3">
          <Avatar initial={user.initial} color="neutral" size={32} online />
        </div>

        {/* ── 中部：4 个主功能 ── */}
        <nav className="mt-4 flex flex-1 flex-col items-center gap-1">
          {RAIL_ITEMS.map((item) => {
            const active = !!item.section && section === item.section
            return (
              <button
                key={item.key}
                onClick={() => item.section && setSection(item.section)}
                title={item.label}
                aria-label={item.label}
                aria-current={active ? 'page' : undefined}
                data-active={active ? 'true' : undefined}
                className={cn(
                  'group relative grid h-10 w-10 place-items-center rounded-lg text-muted-foreground transition-colors',
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
                  className="h-[18px] w-[18px]"
                  strokeWidth={active ? 2.25 : 1.75}
                />
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
            className="grid h-10 w-10 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
          >
            <Icon
              name={theme === 'dark' ? 'sun' : 'moon'}
              className="h-[18px] w-[18px]"
            />
          </button>
          <button
            onClick={() => setHelpOpen(true)}
            title="帮助与反馈"
            aria-label="帮助与反馈"
            className="grid h-10 w-10 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background"
          >
            <Icon name="info" className="h-[18px] w-[18px]" />
          </button>
          <button
            onClick={() => setSection('api-keys')}
            title="设置"
            aria-label="设置"
            aria-current={section === 'api-keys' ? 'page' : undefined}
            data-active={section === 'api-keys' ? 'true' : undefined}
            className={cn(
              'group relative grid h-10 w-10 place-items-center rounded-lg text-muted-foreground transition-colors',
              'hover:bg-accent hover:text-foreground',
              'data-[active=true]:bg-brand/15 data-[active=true]:text-brand',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
            )}
          >
            {section === 'api-keys' && (
              <span
                aria-hidden
                className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-brand"
              />
            )}
            <Icon name="settings" className="h-[18px] w-[18px]" strokeWidth={section === 'api-keys' ? 2.25 : 1.75} />
          </button>
        </div>
      </aside>

      <HelpModal open={helpOpen} onOpenChange={setHelpOpen} />
    </>
  )
}
