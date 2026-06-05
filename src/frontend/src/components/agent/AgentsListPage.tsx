import { useMemo, useState } from 'react'
import { cn } from '../../lib/cn'
import { useAgentStore } from '../../stores/agentStore'
import { useChatStore } from '../../stores/chatStore'
import { useUIStore } from '../../stores/uiStore'
import { StartChatModal } from '../chat/StartChatModal'
import { Avatar, Button, Icon } from '../ui'
import type { IconName } from '../../types'
import { CreateAgentModal } from './CreateAgentModal'

/**
 * AI 队友主页（替代原 AgentDetailPage 的"单 Agent 详情"路由）：
 *   - 顶部：标题 + 计数 + 创建队友 + 批量管理
 *   - 卡片网格：紧凑 4-5 列；每张卡 = 头像 + 名称 + 角色 + 1 行 bio + 3 图标按钮
 *   - 3 按钮：发起私聊（chat）/ 详细（moreVertical）/ 删除（trash2）
 *   - 批量模式：复选框替代按钮区；已选 N + 全选 + 删除选中 + 退出
 *   - 详细按钮 → 打开右侧 AgentDetailDrawer
 */
export function AgentsListPage() {
  const { agents, profiles, removeAgent } = useAgentStore()
  const conversations = useChatStore((s) => s.conversations)
  const addConversation = useChatStore((s) => s.addConversation)
  const { openConversation, openAgentDrawer } = useUIStore()

  const [batchMode, setBatchMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [createOpen, setCreateOpen] = useState(false)
  const [pendingChat, setPendingChat] = useState<{ agentId: string; agentName: string } | null>(null)

  const selectedCount = selectedIds.size
  const allSelected = agents.length > 0 && selectedCount === agents.length

  const enterBatch = () => {
    setBatchMode(true)
    setSelectedIds(new Set())
  }
  const exitBatch = () => {
    setBatchMode(false)
    setSelectedIds(new Set())
  }
  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }
  const toggleSelectAll = () => {
    if (allSelected) setSelectedIds(new Set())
    else setSelectedIds(new Set(agents.map((a) => a.id)))
  }

  const handleStartChat = (agentId: string) => {
    // 每次点都弹窗：让用户决定"随便聊聊"还是"看看我的项目"，并指定会话名 / 目录
    const agent = agents.find((a) => a.id === agentId)
    setPendingChat({ agentId, agentName: agent?.name ?? '队友' })
  }

  const handleStartChatConfirm = (name: string, workdir?: string) => {
    if (!pendingChat) return
    const convId = addConversation(pendingChat.agentId, { name, workdir })
    openConversation(pendingChat.agentId, convId)
    setPendingChat(null)
  }

  const handleDelete = (agentId: string, agentName: string) => {
    if (window.confirm(`确定删除队友「${agentName}」？该操作不可恢复。`)) {
      removeAgent(agentId)
      setSelectedIds((prev) => {
        const next = new Set(prev)
        next.delete(agentId)
        return next
      })
    }
  }

  const handleBatchDelete = () => {
    if (selectedCount === 0) return
    if (!window.confirm(`确定删除选中的 ${selectedCount} 个队友？该操作不可恢复。`)) return
    selectedIds.forEach((id) => removeAgent(id))
    exitBatch()
  }

  const sortedAgents = useMemo(() => agents, [agents])

  return (
    <div className="glass-panel flex h-full flex-col overflow-hidden rounded-2xl border shadow-sm">
      {/* 顶部 */}
      <header className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-4">
        <div className="min-w-0">
          <h1 className="text-[18px] font-semibold leading-none">
            {batchMode ? '批量管理' : 'AI 队友'}
          </h1>
          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
            {batchMode
              ? `已选 ${selectedCount} / ${agents.length} 个`
              : `共 ${agents.length} 个队友`}
          </p>
        </div>

        {batchMode ? (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={toggleSelectAll}
              aria-pressed={allSelected}
            >
              <Icon name="check" className="h-3.5 w-3.5" />
              {allSelected ? '取消全选' : '全选'}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleBatchDelete}
              disabled={selectedCount === 0}
            >
              <Icon name="trash2" className="h-3.5 w-3.5" />
              删除选中{selectedCount > 0 ? ` (${selectedCount})` : ''}
            </Button>
            <Button variant="ghost" size="sm" onClick={exitBatch}>
              退出批量
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={enterBatch}
              disabled={agents.length === 0}
            >
              <Icon name="check" className="h-3.5 w-3.5" />
              批量管理
            </Button>
            <Button variant="brand" size="sm" onClick={() => setCreateOpen(true)}>
              <Icon name="plus" className="h-3.5 w-3.5" />
              创建队友
            </Button>
          </div>
        )}
      </header>

      {/* 卡片网格（紧凑 4-5 列） */}
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {sortedAgents.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <div className="mb-3 grid h-14 w-14 place-items-center rounded-full bg-muted text-muted-foreground">
                <Icon name="users" className="h-6 w-6" />
              </div>
              <p className="text-[14px] font-medium">还没有队友</p>
              <p className="mt-1 text-[12.5px] text-muted-foreground">
                点击右上角「创建队友」开始
              </p>
              <Button
                variant="brand"
                size="sm"
                className="mt-4"
                onClick={() => setCreateOpen(true)}
              >
                <Icon name="plus" className="h-3.5 w-3.5" />
                创建第一个队友
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-4">
            {sortedAgents.map((agent) => {
              const selected = selectedIds.has(agent.id)
              const profile = profiles[agent.id]
              return (
                <article
                  key={agent.id}
                  data-batch={batchMode ? 'true' : undefined}
                  data-selected={selected ? 'true' : undefined}
                  onClick={batchMode ? () => toggleSelect(agent.id) : undefined}
                  className={cn(
                    'group relative flex flex-col gap-2 rounded-xl glass-soft p-3 transition-colors',
                    'border border-border/60',
                    'hover:border-border',
                    batchMode && 'cursor-pointer',
                    selected
                      ? 'border-brand bg-brand/10 ring-1 ring-brand/40'
                      : '',
                  )}
                >
                  {/* Row 1: 头像 + 名称/角色 + 弹性占位 + 按钮区
                      - 弹性占位 flex-1 把按钮推到卡片右边（p-3 提供 12px 边距）
                      - 占位 min-w-2（8px）保证名字再长也不会贴近按钮
                      - 名字过长 truncate（占位压到 8px） */}
                  <div className="flex items-start gap-2">
                    <Avatar
                      initial={agent.name[0] ?? '?'}
                      color={agent.color}
                      size={32}
                      online={agent.online}
                      className="flex-shrink-0"
                    />
                    <div className="min-w-0">
                      <div className="truncate text-[13.5px] font-semibold leading-tight">
                        {agent.name}
                      </div>
                      <div className="mt-0.5 truncate text-[11px] leading-tight text-muted-foreground">
                        {agent.role}
                      </div>
                    </div>

                    {/* 弹性占位（吃剩余空间 + 8px 最小） */}
                    <div className="min-w-2 flex-1" aria-hidden />

                    {/* 右侧：批量模式=复选框；普通模式=3 个玻璃图标按钮（贴右） */}
                    {batchMode ? (
                      <span
                        className={cn(
                          'grid h-5 w-5 flex-shrink-0 place-items-center rounded border-2',
                          selected
                            ? 'border-brand bg-brand text-brand-foreground'
                            : 'border-border bg-background',
                        )}
                      >
                        {selected && <Icon name="check" className="h-3 w-3" strokeWidth={3} />}
                      </span>
                    ) : (
                      <div
                        className="flex flex-shrink-0 items-center gap-0.5"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <GlassIconBtn
                          icon="chat"
                          title="发起私聊"
                          onClick={() => handleStartChat(agent.id)}
                        />
                        <GlassIconBtn
                          icon="moreVertical"
                          title="详细"
                          onClick={() => openAgentDrawer(agent.id)}
                        />
                        <GlassIconBtn
                          icon="trash2"
                          title="删除队友"
                          onClick={() => handleDelete(agent.id, agent.name)}
                          danger
                        />
                      </div>
                    )}
                  </div>

                  {/* Row 2: 至少 2 行 bio，min-h 锁高度让所有卡片同高 */}
                  <p className="line-clamp-2 min-h-[2.6em] text-[12px] leading-snug text-foreground/75">
                    {profile?.bio?.trim() ? profile.bio : '暂无简介'}
                  </p>
                </article>
              )
            })}
          </div>
        )}
      </div>

      <CreateAgentModal open={createOpen} onClose={() => setCreateOpen(false)} />
      {pendingChat && (
        <StartChatModal
          open
          onOpenChange={(o) => !o && setPendingChat(null)}
          agentName={pendingChat.agentName}
          existingCount={(conversations[pendingChat.agentId] ?? []).length}
          onConfirm={handleStartChatConfirm}
        />
      )}
    </div>
  )
}

/** 玻璃质感小图标按钮（h-7 w-7），用于卡片右侧动作区。 */
function GlassIconBtn({
  icon,
  title,
  onClick,
  danger,
}: {
  icon: IconName
  title: string
  onClick: () => void
  danger?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      aria-label={title}
      className={cn(
        'grid h-7 w-7 place-items-center rounded-lg border border-border/60 glass-soft transition-colors',
        'text-muted-foreground',
        'hover:bg-accent hover:text-foreground',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-background',
        danger && 'hover:bg-destructive/10 hover:text-destructive hover:border-destructive/40',
      )}
    >
      <Icon name={icon} className="h-3.5 w-3.5" />
    </button>
  )
}
