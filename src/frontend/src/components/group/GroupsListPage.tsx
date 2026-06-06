import { useMemo, useState } from 'react'
import { cn } from '../../lib/cn'
import { useAgentStore } from '../../stores/agentStore'
import { useGroupStore } from '../../stores/groupStore'
import { useUIStore } from '../../stores/uiStore'
import type { Agent } from '../../types'
import { Avatar, Button, Icon } from '../ui'
import { CreateGroupModal } from './CreateGroupModal'

/**
 * 群组主页（仿照 AgentsListPage 风格）：
 *   - 顶部：标题 + 计数 + 创建群组 + 批量管理
 *   - 卡片网格：每张卡 = 头像 + 群名 + 简介 + 工作目录预览 + 2 按钮（进入群聊 / 详细）
 *   - 批量模式：复选框 + 已选 N + 全选 + 删除选中 + 退出（删除走确认弹窗）
 *   - 「进入群聊」 → setSection('group') 进入群聊主界面
 */
export function GroupsListPage() {
  const groups = useGroupStore((s) => s.groups)
  const deleteGroup = useGroupStore((s) => s.deleteGroup)
  const agents = useAgentStore((s) => s.agents)
  const { setSection } = useUIStore()

  const [batchMode, setBatchMode] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() => new Set())
  const [createOpen, setCreateOpen] = useState(false)

  const selectedCount = selectedIds.size
  const allSelected = groups.length > 0 && selectedCount === groups.length

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
    else setSelectedIds(new Set(groups.map((g) => g.id)))
  }

  const handleBatchDelete = () => {
    if (selectedCount === 0) return
    if (!window.confirm(`确定删除选中的 ${selectedCount} 个群组？该操作不可恢复。`)) return
    selectedIds.forEach((id) => deleteGroup(id))
    exitBatch()
  }

  const sortedGroups = useMemo(() => groups, [groups])

  return (
    <div className="glass-panel flex h-full flex-col overflow-hidden rounded-2xl border shadow-sm">
      {/* 顶部 */}
      <header className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-4">
        <div className="min-w-0">
          <h1 className="text-[18px] font-semibold leading-none">
            {batchMode ? '批量管理' : '群组'}
          </h1>
          <p className="mt-1 font-mono text-[11px] text-muted-foreground">
            {batchMode ? `已选 ${selectedCount} / ${groups.length} 个` : `共 ${groups.length} 个群组`}
          </p>
        </div>

        {batchMode ? (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={toggleSelectAll} aria-pressed={allSelected}>
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
              disabled={groups.length === 0}
            >
              <Icon name="check" className="h-3.5 w-3.5" />
              批量管理
            </Button>
            <Button variant="brand" size="sm" onClick={() => setCreateOpen(true)}>
              <Icon name="plus" className="h-3.5 w-3.5" />
              创建群组
            </Button>
          </div>
        )}
      </header>

      {/* 卡片网格（与 AI 队友一致 4 列） */}
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {sortedGroups.length === 0 ? (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <div className="mb-3 grid h-14 w-14 place-items-center rounded-full bg-muted text-muted-foreground">
                <Icon name="channels" className="h-6 w-6" />
              </div>
              <p className="text-[14px] font-medium">还没有群组</p>
              <p className="mt-1 text-[12.5px] text-muted-foreground">
                点击右上角「创建群组」开始
              </p>
              <Button
                variant="brand"
                size="sm"
                className="mt-4"
                onClick={() => setCreateOpen(true)}
              >
                <Icon name="plus" className="h-3.5 w-3.5" />
                创建第一个群组
              </Button>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 md:grid-cols-3">
            {sortedGroups.map((g) => {
              const selected = selectedIds.has(g.id)
              // 协调者不在 g.members 里，单独 +1 算总成员数（产品口径：协调者也是成员）
              const totalMembers = g.members.length + (g.coordinatorId ? 1 : 0)
              // 头像只显示 g.members 里的 agent（协调者在 agentStore 不存在，不显示头像）
              const memberAgents: Agent[] = g.members
                .map((id) => agents.find((a) => a.id === id))
                .filter((a): a is Agent => a !== undefined)
              const visibleMembers = memberAgents.slice(0, 3)
              // +N 包含「剩余成员 + 协调者」
              const extraCount =
                memberAgents.length - visibleMembers.length + (g.coordinatorId ? 1 : 0)
              return (
                <article
                  key={g.id}
                  data-batch={batchMode ? 'true' : undefined}
                  data-selected={selected ? 'true' : undefined}
                  onClick={batchMode ? () => toggleSelect(g.id) : undefined}
                  className={cn(
                    'group relative flex flex-col gap-2 rounded-xl glass-soft p-3 transition-colors',
                    'border border-border/60',
                    'hover:border-border',
                    batchMode && 'cursor-pointer',
                    selected ? 'border-brand bg-brand/10 ring-1 ring-brand/40' : '',
                  )}
                >
                  {/* 批量模式复选框 */}
                  {batchMode && (
                    <span
                      className={cn(
                        'absolute right-3 top-3 grid h-5 w-5 place-items-center rounded border-2',
                        selected
                          ? 'border-brand bg-brand text-brand-foreground'
                          : 'border-border bg-background',
                      )}
                    >
                      {selected && <Icon name="check" className="h-3 w-3" strokeWidth={3} />}
                    </span>
                  )}

                  {/* 头部：群头像 + 群名 + 总成员数 + 成员堆叠头像 + 2 个 GlassIconBtn
                      - 成员堆叠挪到「按钮左边」（同一行）— 卡片瘦身
                      - 简介行已删（产品口径：群组卡片不展示描述） */}
                  <div className="flex items-center gap-1.5">
                    <Avatar
                      initial={g.name[0] ?? '?'}
                      color="brand"
                      size={32}
                      className="flex-shrink-0"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[13.5px] font-semibold leading-tight">
                        {g.name}
                      </div>
                      <div className="mt-0.5 flex items-center gap-1 text-[11px] leading-tight text-muted-foreground">
                        <Icon name="users" className="h-2.5 w-2.5" />
                        <span>{totalMembers} 成员</span>
                      </div>
                    </div>

                    {/* 成员堆叠头像（最多 3 个 + +N 隐藏）— 与按钮同列，按钮在右 */}
                    {visibleMembers.length > 0 && (
                      <div className="flex flex-shrink-0 items-center">
                        {visibleMembers.map((m, i) => (
                          <div
                            key={m.id}
                            title={m.name}
                            className="inline-flex rounded-full ring-2 ring-background"
                            style={{ marginLeft: i === 0 ? 0 : -6 }}
                          >
                            <Avatar initial={m.name[0] ?? '?'} color={m.color} size={18} />
                          </div>
                        ))}
                        {extraCount > 0 && (
                          <span className="ml-1 text-[10.5px] text-muted-foreground">
                            +{extraCount}
                          </span>
                        )}
                      </div>
                    )}

                    {/* 右侧：批量模式=复选框；普通模式=2 个玻璃图标按钮（贴右） */}
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
                          title="进入群聊"
                          onClick={() => {
                            useUIStore.getState().openGroup(g.id)
                          }}
                        />
                        <GlassIconBtn
                          icon="moreVertical"
                          title="详细"
                          onClick={() =>
                            window.alert(
                              `「${g.name}」\n\n成员：${totalMembers} 个\n${g.workdir ? `工作目录：\n${g.workdir}` : '工作目录：未设置'}\n\n（详细抽屉后续接入）`,
                            )
                          }
                        />
                      </div>
                    )}
                  </div>

                  {/* 工作目录预览（仅在有值时显示） */}
                  {g.workdir && (
                    <div className="flex items-center gap-1.5 rounded-md border bg-muted/30 px-2 py-1 text-[10.5px] text-muted-foreground">
                      <Icon name="folderOpen" className="h-3 w-3 flex-shrink-0" />
                      <span className="truncate font-mono" title={g.workdir}>
                        {g.workdir}
                      </span>
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        )}
      </div>

      <CreateGroupModal open={createOpen} onClose={() => setCreateOpen(false)} />
    </div>
  )
}

/** 与 AI 队友卡（AgentsListPage.GlassIconBtn）同款玻璃图标按钮。 */
function GlassIconBtn({
  icon,
  title,
  onClick,
}: {
  icon: 'chat' | 'moreVertical'
  title: string
  onClick: () => void
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
      )}
    >
      <Icon name={icon} className="h-3.5 w-3.5" />
    </button>
  )
}
