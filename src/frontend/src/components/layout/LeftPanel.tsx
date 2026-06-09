import { type MouseEvent, useEffect, useMemo, useState } from 'react'
import { cn } from '../../lib/cn'
import { sessionsApi } from '../../api/sessions'
import { useAgentStore } from '../../stores/agentStore'
import { useChatStore, convKey } from '../../stores/chatStore'
import { useGroupStore } from '../../stores/groupStore'
import { useUIStore } from '../../stores/uiStore'
import { CreateGroupModal } from '../group/CreateGroupModal'
import { Avatar, ConfirmDialog, ContextMenu, Icon } from '../ui'
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
  const messages = useChatStore((s) => s.messages)
  const [openGroup_, setOpenGroup] = useState(true)
  const [openDM, setOpenDM] = useState(true)
  const renameGroup = useGroupStore((s) => s.renameGroup)
  const deleteGroup = useGroupStore((s) => s.deleteGroup)
  // t7 拓展：群组置顶（复用 backing Session.pinned，复用私聊 trade-off 模式）
  const toggleGroupPin = useGroupStore((s) => s.toggleGroupPin)
  const [groupCreateOpen, setGroupCreateOpen] = useState(false)
  const [menu, setMenu] = useState<{ groupId: string; x: number; y: number } | null>(null)
  const [deleteConfirming, setDeleteConfirming] = useState<string | null>(null) // groupId to delete
  const [dmBatchMode, setDmBatchMode] = useState(false)
  const [dmSelected, setDmSelected] = useState<Set<string>>(() => new Set())
  const [dmBatchDeleteConfirm, setDmBatchDeleteConfirm] = useState(false)
  const removeConversations = useChatStore((s) => s.removeConversations)
  const setConversationPinned = useChatStore((s) => s.setConversationPinned)
  const setConversationArchived = useChatStore((s) => s.setConversationArchived)
  const sessionIds = useChatStore((s) => s.sessionIds)
  const setSessionId = useChatStore((s) => s.setSessionId)
  const addConversation = useChatStore((s) => s.addConversation)
  // M1#2：归档 in-flight 跟踪 + 错误提示（pin 同样的乐观+in-flight+inline 错误模式）
  const [inFlightArchive, setInFlightArchive] = useState<Set<string>>(() => new Set())
  const [archiveError, setArchiveError] = useState<string | null>(null)
  const [openArchived, setOpenArchived] = useState(false)
  // t7 B-4-P2-CL01：搜索（300ms debounce）+ 置顶
  const [searchQuery, setSearchQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQuery(searchQuery.trim().toLowerCase()), 300)
    return () => clearTimeout(t)
  }, [searchQuery])
  // in-flight pin requests（按 convKey 跟踪）— 请求中禁用按钮防 race
  const [inFlightPins, setInFlightPins] = useState<Set<string>>(() => new Set())
  // 最近一次 pin 错误（与 MessageBubble.copyStatus 同 pattern：inline 显示，不引 toast 库）
  const [pinError, setPinError] = useState<string | null>(null)

  // M1#2：归档切换（pin 同样的乐观 + createPrivate 兜底 + 1 retry + in-flight 禁用 + inline 错误）
  const handleToggleArchive = async (
    agentId: string,
    convId: string,
    nextArchived: boolean,
  ): Promise<void> => {
    const key = convKey(agentId, convId)
    if (inFlightArchive.has(key)) return
    setInFlightArchive((prev) => new Set(prev).add(key))
    setArchiveError(null)
    setConversationArchived(agentId, convId, nextArchived)
    try {
      let sid = sessionIds[key]
      if (!sid) {
        const sess = await sessionsApi.createPrivate(agentId)
        sid = sess.id
        setSessionId(key, sid)
      }
      const doPatch = () => sessionsApi.patch(sid!, { archived: nextArchived })
      try {
        await doPatch()
      } catch (err1) {
        console.warn('[archive] PATCH failed, retrying once', err1)
        await doPatch()
      }
    } catch (err) {
      console.warn('[archive] toggle failed', err)
      setArchiveError(`归档失败：${(err as Error).message ?? '网络错误'}`)
    } finally {
      setInFlightArchive((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    }
  }

  // 扁平私聊列表：每 Agent 内会话倒序（最新在前），跨 Agent 保持 store 顺序
  const dmList = useMemo(() => {
    const list = agents.flatMap((a) =>
      (conversations[a.id] ?? [])
        .slice()
        .reverse()
        .map((c) => ({ agent: a, conv: c, key: `${a.id}:${c.id}` })),
    )
    // 按最近消息时间排序（最新的在前）
    list.sort((a, b) => {
      const aMsgs = messages[convKey(a.agent.id, a.conv.id)] ?? []
      const bMsgs = messages[convKey(b.agent.id, b.conv.id)] ?? []
      const aTime = aMsgs[aMsgs.length - 1]?.time ?? a.conv.updatedAt ?? '0'
      const bTime = bMsgs[bMsgs.length - 1]?.time ?? b.conv.updatedAt ?? '0'
      return bTime.localeCompare(aTime)
    })
    return list
  }, [agents, conversations, messages])

  // M1#2：扁平私聊列表过滤 archived（默认不展示已归档的）
  const filteredDmList = useMemo(() => {
    let list = dmList.filter(({ conv }) => !conv.archived)
    if (debouncedQuery) {
      list = list.filter(
        ({ agent, conv }) =>
          conv.name.toLowerCase().includes(debouncedQuery) ||
          agent.name.toLowerCase().includes(debouncedQuery),
      )
    }
    // 置顶排前（同 pinned 内按最近消息时间）
    return [...list].sort((a, b) => (b.conv.pinned ? 1 : 0) - (a.conv.pinned ? 1 : 0))
  }, [dmList, debouncedQuery])

  // M1#2：已归档列表
  const archivedList = useMemo(() => dmList.filter(({ conv }) => conv.archived), [dmList])

  // M1#2：右键菜单增加「归档/取消归档」选项（替代方案：hover 显示 archive 图标，简化为右键菜单）
  const handleTogglePin = async (
    agentId: string,
    convId: string,
    nextPinned: boolean,
  ): Promise<void> => {
    const key = convKey(agentId, convId)
    if (inFlightPins.has(key)) return // in-flight 防 race
    setInFlightPins((prev) => new Set(prev).add(key))
    setPinError(null)
    // (1) 乐观更新：local 立即翻
    setConversationPinned(agentId, convId, nextPinned)
    try {
      // (2) 缺 sessionId → 先 createPrivate 拿 ID
      let sid = sessionIds[key]
      if (!sid) {
        const sess = await sessionsApi.createPrivate(agentId)
        sid = sess.id
        setSessionId(key, sid)
      }
      // (3) PATCH with 1 retry on failure
      const doPatch = () => sessionsApi.patch(sid!, { pinned: nextPinned })
      try {
        await doPatch()
      } catch (err1) {
        console.warn('[pin] PATCH failed, retrying once', err1)
        await doPatch()
      }
    } catch (err) {
      // (4) 错误：console.warn + inline 提示（不 rollback — user 决定）
      console.warn('[pin] toggle failed', err)
      setPinError(`置顶失败：${(err as Error).message ?? '网络错误'}`)
    } finally {
      setInFlightPins((prev) => {
        const next = new Set(prev)
        next.delete(key)
        return next
      })
    }
  }

  // t7 拓展：群组置顶（4 trade-off 同 handleTogglePin：乐观 + 兜底 + 失败 console.warn）
  // 实现委托给 groupStore.toggleGroupPin（它走 backing session PATCH）
  const handleToggleGroupPin = async (groupId: string, nextPinned: boolean): Promise<void> => {
    await toggleGroupPin(groupId, nextPinned)
  }

  const exitDmBatch = () => {
    setDmBatchMode(false)
    setDmSelected(new Set())
  }

  const toggleDmSelect = (convId: string) => {
    setDmSelected((prev) => {
      const next = new Set(prev)
      if (next.has(convId)) next.delete(convId)
      else next.add(convId)
      return next
    })
  }

  const confirmDmBatchDelete = () => {
    // Group by agent, then delete
    const byAgent: Record<string, string[]> = {}
    const deletedKeys = new Set(dmSelected)
    let currentWasDeleted = false
    if (activeAgentId && activeConversationId) {
      currentWasDeleted = deletedKeys.has(`${activeAgentId}:${activeConversationId}`)
    }
    for (const key of dmSelected) {
      const [agentId, convId] = key.split(':')
      if (!byAgent[agentId]) byAgent[agentId] = []
      byAgent[agentId].push(convId)
    }
    for (const [agentId, convIds] of Object.entries(byAgent)) {
      removeConversations(agentId, convIds)
    }
    // 如果删除的是当前会话，切换到下一个
    if (currentWasDeleted && activeAgentId) {
      const remaining =
        conversations[activeAgentId]?.filter((c) => !deletedKeys.has(`${activeAgentId}:${c.id}`)) ??
        []
      if (remaining.length > 0) {
        openConversation(activeAgentId, remaining[remaining.length - 1].id)
      }
    }
    setDmBatchDeleteConfirm(false)
    exitDmBatch()
  }

  return (
    <aside className="glass-panel flex h-full w-full flex-col overflow-hidden rounded-2xl border shadow-sm">
      {/* 顶部：搜索框 + 收起按钮 */}
      <div className="flex items-center gap-1 px-3 pb-2 pt-3">
        <div className="flex h-[clamp(28px,2.3vw,36px)] flex-1 items-center gap-2 rounded-md border glass-soft px-2.5 text-muted-foreground transition-colors focus-within:border-brand/40">
          <Icon name="search" className="h-3.5 w-3.5" />
          <input
            placeholder="跳转到…"
            data-testid="leftpanel-search"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
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
                lastMsg?.kind === 'plan' ? '📋 分发方案' : lastMsg?.text?.trim() || '暂无消息'
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
                    'group flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
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
                  {/* t7 拓展：群组置顶按钮（hover 显示 + 已 pin 时始终显示） */}
                  <span
                    role="button"
                    tabIndex={-1}
                    onClick={(e: MouseEvent) => {
                      e.stopPropagation()
                      handleToggleGroupPin(g.id, !g.pinned)
                    }}
                    data-testid={`pin-group-${g.id}`}
                    data-pinned={g.pinned ? 'true' : 'false'}
                    title={g.pinned ? '取消置顶群组' : '置顶群组'}
                    className={cn(
                      'flex-shrink-0 rounded p-0.5 transition-all',
                      g.pinned
                        ? 'text-brand opacity-100'
                        : 'text-muted-foreground/40 opacity-0 group-hover:opacity-100 hover:bg-accent/50 hover:text-muted-foreground',
                    )}
                  >
                    <Icon name="pin" className="h-3 w-3" />
                  </span>
                </button>
              )
            })}
          </div>
        )}

        {/* 私聊（扁平） */}
        <SectionHeader label="私聊" collapsed={!openDM} onToggle={() => setOpenDM((v) => !v)} />
        {openDM && (
          <div className="space-y-px">
            {dmList.length === 0 ? (
              // M1#1：空态加「发起私聊」CTA — 新用户进站后的第一个可点击入口
              <button
                type="button"
                onClick={() => {
                  const firstAgent = agents[0]
                  if (firstAgent) {
                    const cid = addConversation(firstAgent.id)
                    openConversation(firstAgent.id, cid)
                  }
                }}
                disabled={agents.length === 0}
                data-testid="leftpanel-dm-cta"
                className="flex w-full items-center justify-center gap-1.5 rounded-md border border-dashed border-brand/30 bg-brand/5 px-2 py-2 text-[12px] font-medium text-brand transition-colors hover:bg-brand/10 disabled:opacity-40"
              >
                <Icon name="plus" className="h-3 w-3" />
                发起私聊
              </button>
            ) : (
              filteredDmList.map(({ agent, conv, key }) => {
                const isActive =
                  section === 'chat' &&
                  activeAgentId === agent.id &&
                  activeConversationId === conv.id
                const selected = dmSelected.has(key)
                // 最近一条消息
                const msgKey = convKey(agent.id, conv.id)
                const msgs = messages[msgKey] ?? []
                const lastMsg = msgs[msgs.length - 1]
                const lastText = lastMsg?.text?.trim() || conv.subtitle
                return (
                  <button
                    key={key}
                    onClick={() => {
                      if (dmBatchMode) {
                        toggleDmSelect(key)
                      } else {
                        openConversation(agent.id, conv.id)
                      }
                    }}
                    data-active={isActive ? 'true' : undefined}
                    className={cn(
                      'group flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                      'data-[active=true]:bg-brand/10 data-[active=true]:text-foreground',
                    )}
                  >
                    {dmBatchMode && (
                      <div
                        className={cn(
                          'mt-1 grid h-4 w-4 flex-shrink-0 place-items-center rounded border-2 transition-colors',
                          selected
                            ? 'border-brand bg-brand text-brand-foreground'
                            : 'border-muted-foreground/30',
                        )}
                      >
                        {selected && <Icon name="check" className="h-2.5 w-2.5" />}
                      </div>
                    )}
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
                        {lastText}
                      </div>
                    </div>
                    {/* t7 B-4-P2-CL01：pin 图标（置顶/取消置顶 + in-flight 禁用 + 错误标记） */}
                    <span
                      role="button"
                      tabIndex={-1}
                      aria-busy={inFlightPins.has(convKey(agent.id, conv.id))}
                      onClick={(e: MouseEvent) => {
                        e.stopPropagation()
                        handleTogglePin(agent.id, conv.id, !conv.pinned)
                      }}
                      data-testid={`pin-conv-${conv.id}`}
                      data-pinned={conv.pinned ? 'true' : 'false'}
                      data-error={pinError ? 'true' : 'false'}
                      title={
                        inFlightPins.has(convKey(agent.id, conv.id))
                          ? '处理中…'
                          : conv.pinned
                            ? '取消置顶'
                            : '置顶会话'
                      }
                      className={cn(
                        'flex-shrink-0 rounded p-0.5 transition-all',
                        inFlightPins.has(convKey(agent.id, conv.id)) &&
                          'cursor-not-allowed opacity-50',
                        pinError && !conv.pinned && 'text-destructive opacity-100',
                        conv.pinned && !inFlightPins.has(convKey(agent.id, conv.id))
                          ? 'text-brand opacity-100'
                          : !conv.pinned && !pinError
                            ? 'text-muted-foreground/40 opacity-0 group-hover:opacity-100 hover:bg-accent/50 hover:text-muted-foreground'
                            : '',
                      )}
                    >
                      <Icon name="pin" className="h-3 w-3" />
                    </span>
                  </button>
                )
              })
            )}
            {/* 批量管理按钮（柱在私聊列表底部） */}
            {dmList.length > 0 && !dmBatchMode && (
              <button
                type="button"
                onClick={() => setDmBatchMode(true)}
                className="flex w-full items-center justify-center gap-1.5 rounded-md px-2 py-2 text-[11px] text-muted-foreground/60 transition-colors hover:bg-accent hover:text-muted-foreground"
              >
                <Icon name="check" className="h-3 w-3" />
                批量管理
              </button>
            )}
            {dmBatchMode && (
              <div className="flex items-center justify-between rounded-md px-2 py-2">
                <span className="text-[11px] text-muted-foreground">已选 {dmSelected.size} 个</span>
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={exitDmBatch}
                    className="rounded px-2 py-0.5 text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    onClick={() => dmSelected.size > 0 && setDmBatchDeleteConfirm(true)}
                    disabled={dmSelected.size === 0}
                    className="rounded px-2 py-0.5 text-[11px] text-destructive transition-colors hover:bg-destructive/10 disabled:opacity-30"
                  >
                    删除选中
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </nav>

      <CreateGroupModal open={groupCreateOpen} onClose={() => setGroupCreateOpen(false)} />
      <ConfirmDialog
        open={deleteConfirming !== null}
        title="删除群组"
        message="确定删除该群组？此操作不可恢复。"
        confirmLabel="删除"
        danger
        onConfirm={() => {
          const gid = deleteConfirming!
          deleteGroup(gid)
          if (activeGroupId === gid && activeAgentId && activeConversationId) {
            openConversation(activeAgentId, activeConversationId)
          }
          setDeleteConfirming(null)
        }}
        onCancel={() => setDeleteConfirming(null)}
      />
      <ConfirmDialog
        open={dmBatchDeleteConfirm}
        title="批量删除会话"
        message={`确定删除选中的 ${dmSelected.size} 个私聊会话？此操作不可恢复。`}
        confirmLabel="删除"
        danger
        onConfirm={confirmDmBatchDelete}
        onCancel={() => setDmBatchDeleteConfirm(false)}
      />
      {menu && (
        <ContextMenu
          x={menu.x}
          y={menu.y}
          onClose={() => setMenu(null)}
          items={
            [
              {
                icon: 'pencil',
                label: '重命名',
                onClick: () => {
                  const name = window.prompt(
                    '新名称',
                    groups.find((g) => g.id === menu.groupId)?.name ?? '',
                  )
                  if (name && name.trim()) renameGroup(menu.groupId, name.trim())
                },
              },
              {
                icon: 'trash2',
                label: '删除群组',
                danger: true,
                onClick: () => {
                  setDeleteConfirming(menu.groupId)
                  setMenu(null)
                },
              },
            ] satisfies ContextMenuItem[]
          }
        />
      )}
    </aside>
  )
}
