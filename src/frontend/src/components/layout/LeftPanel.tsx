import { type MouseEvent, useMemo, useState } from 'react'
import { cn } from '../../lib/cn'
import { useAgentStore } from '../../stores/agentStore'
import { useChatStore } from '../../stores/chatStore'
import { useGroupStore } from '../../stores/groupStore'
import { useUIStore } from '../../stores/uiStore'
import { CreateGroupModal } from '../group/CreateGroupModal'
import { Avatar, ContextMenu, Icon } from '../ui'
import type { ContextMenuItem } from '../ui'

function SectionHeader({
  label,
  collapsed,
  onToggle,
  onAdd,
  addTitle,
}: {
  label: string
  collapsed: boolean
  onToggle: () => void
  onAdd?: () => void
  addTitle?: string
}) {
  return (
    <div className="group mb-1 mt-3 flex items-center justify-between px-2">
      <button
        onClick={onToggle}
        className="flex items-center gap-1 font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
      >
        <Icon
          name="chevronDown"
          className={cn('h-2.5 w-2.5 transition-transform', collapsed && '-rotate-90')}
        />
        <span>{label}</span>
      </button>
      {onAdd && (
        <button
          onClick={onAdd}
          title={addTitle}
          className="grid h-4 w-4 place-items-center rounded opacity-40 transition-all hover:opacity-100 hover:bg-accent"
        >
          <Icon name="plus" className="h-3 w-3" />
        </button>
      )}
    </div>
  )
}

/**
 * 左侧「会话入口」面板：
 *   - 顶部 ⌘K 搜索
 *   - 群组 section（带「+」创建群组）
 *   - 私聊 section（扁平列表：所有 Agent 的会话平铺，按最近倒序；带 Agent 名前缀）
 *
 * 已被外迁的元素：
 *   - 收件箱/任务/日历导航 → 由最左侧 NavRail 替代
 *   - 顶部 workspace 标题 + 折叠按钮 → 用户头像已迁到 NavRail
 *   - 底部用户组件（设置/在线状态） → 由 NavRail 底部 + TweaksPanel 替代
 *   - AI 队友折叠列表 + 创建队友按钮 → 迁到 AI 队友主页（NavRail → 队友图标）
 */
export function LeftPanel() {
  const {
    section,
    activeAgentId,
    activeConversationId,
    activeGroupId,
    openConversation,
    openGroup,
    toggleSidebar,
  } = useUIStore()
  const agents = useAgentStore((s) => s.agents)
  const groups = useGroupStore((s) => s.groups)
  const messagesByGroup = useGroupStore((s) => s.messagesByGroup)
  const conversations = useChatStore((s) => s.conversations)
  const [openGroup_, setOpenGroup] = useState(true)
  const [openDM, setOpenDM] = useState(true)
  const renameGroup = useGroupStore((s) => s.renameGroup)
  const deleteGroup = useGroupStore((s) => s.deleteGroup)
  const [groupCreateOpen, setGroupCreateOpen] = useState(false)
  const [menu, setMenu] = useState<{ groupId: string; x: number; y: number } | null>(null)

  // 扁平私聊列表：每 Agent 内会话倒序（最新在前），跨 Agent 保持 store 顺序
  const dmList = useMemo(() => {
    return agents.flatMap((a) =>
      (conversations[a.id] ?? [])
        .slice()
        .reverse()
        .map((c) => ({ agent: a, conv: c, key: `${a.id}:${c.id}` })),
    )
  }, [agents, conversations])

  return (
    <aside className="glass-panel flex h-full w-full flex-col overflow-hidden rounded-2xl border shadow-sm">
      {/* 顶部：搜索框 + 收起按钮 */}
      <div className="flex items-center gap-1 px-3 pb-2 pt-3">
        <div className="flex h-[clamp(28px,2.3vw,36px)] flex-1 items-center gap-2 rounded-md border glass-soft px-2.5 text-muted-foreground transition-colors focus-within:border-brand/40">
          <Icon name="search" className="h-3.5 w-3.5" />
          <input
            placeholder="跳转到…"
            className="min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:text-muted-foreground/70"
          />
        </div>
        <button
          type="button"
          onClick={toggleSidebar}
          title="收起会话列表"
          aria-label="收起会话列表"
          className="grid h-[30px] w-[clamp(28px,2.3vw,36px)] flex-shrink-0 place-items-center rounded-md text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Icon name="panelLeftClose" className="h-3.5 w-3.5" />
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-2 pb-2">
        {/* 群组 */}
        <SectionHeader
          label="群组"
          collapsed={!openGroup_}
          onToggle={() => setOpenGroup((v) => !v)}
          onAdd={() => setGroupCreateOpen(true)}
          addTitle="创建群组"
        />
        {openGroup_ && (
          <div className="space-y-px">
            {groups.map((g) => {
              // 该群最新一条消息（与私聊的 conv.subtitle 对位）
              const msgs = messagesByGroup[g.id] ?? []
              const lastMsg = msgs[msgs.length - 1]
              const lastText =
                lastMsg?.kind === 'plan'
                  ? '📋 分发方案'
                  : lastMsg?.text?.trim() || '暂无消息'
              return (
                <button
                  key={g.id}
                  onClick={() => openGroup(g.id)}
                  onContextMenu={(e: MouseEvent) => {
                    e.preventDefault()
                    setMenu({ groupId: g.id, x: e.clientX, y: e.clientY })
                  }}
                  data-active={section === 'group' && activeGroupId === g.id ? 'true' : undefined}
                  className={cn(
                    'flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                    'data-[active=true]:bg-accent data-[active=true]:font-medium data-[active=true]:text-foreground',
                  )}
                >
                  <Avatar initial={g.name[0] ?? '?'} color="brand" size={32} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[12.5px] font-medium leading-tight">{g.name}</div>
                    <div className="truncate text-[10.5px] leading-tight text-muted-foreground/80">
                      {lastText}
                    </div>
                  </div>
                </button>
              )
            })}
          </div>
        )}

        {/* 私聊（扁平） */}
        <SectionHeader
          label="私聊"
          collapsed={!openDM}
          onToggle={() => setOpenDM((v) => !v)}
        />
        {openDM && (
          <div className="space-y-px">
            {dmList.length === 0 ? (
              <p className="px-2 py-1.5 text-[12px] text-muted-foreground/70">
                还没有私聊 · 去 AI 队友里发起
              </p>
            ) : (
              dmList.map(({ agent, conv, key }) => {
                const isActive =
                  section === 'chat' && activeAgentId === agent.id && activeConversationId === conv.id
                return (
                  <button
                    key={key}
                    onClick={() => openConversation(agent.id, conv.id)}
                    data-active={isActive ? 'true' : undefined}
                    className={cn(
                      'flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                      'data-[active=true]:bg-brand/10 data-[active=true]:text-foreground',
                    )}
                  >
                    <Avatar
                      initial={agent.name[0] ?? '?'}
                      color={agent.color}
                      size={32}
                      online={agent.online}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate text-[12.5px] font-medium">{conv.name}</span>
                        <span className="flex-shrink-0 truncate font-mono text-[9.5px] uppercase tracking-wider text-muted-foreground/60">
                          {agent.name}
                        </span>
                      </div>
                      <div className="truncate text-[10.5px] text-muted-foreground/80">
                        {conv.subtitle}
                      </div>
                    </div>
                  </button>
                )
              })
            )}
          </div>
        )}
      </nav>

      <CreateGroupModal open={groupCreateOpen} onClose={() => setGroupCreateOpen(false)} />
      {menu && (
        <ContextMenu
          x={menu.x} y={menu.y}
          onClose={() => setMenu(null)}
          items={
            [
              {
                icon: 'pencil',
                label: '重命名',
                onClick: () => {
                  const name = window.prompt('新名称', groups.find((g) => g.id === menu.groupId)?.name ?? '')
                  if (name && name.trim()) renameGroup(menu.groupId, name.trim())
                },
              },
              {
                icon: 'trash2',
                label: '删除群组',
                danger: true,
                onClick: () => {
                  if (window.confirm('确定删除该群组？')) {
                    deleteGroup(menu.groupId)
                    if (activeGroupId === menu.groupId && activeAgentId && activeConversationId) {
                      openConversation(activeAgentId, activeConversationId)
                    }
                  }
                },
              },
            ] satisfies ContextMenuItem[]
          }
        />
      )}
    </aside>
  )
}
