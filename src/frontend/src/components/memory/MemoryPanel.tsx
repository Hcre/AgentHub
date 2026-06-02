import { useCallback, useEffect, useState } from 'react'
import { cn } from '../../lib/cn'
import { useMemoryStore } from '../../stores/memoryStore'
import { Button, Icon } from '../ui'
import type { ApiMemory, MemoryType } from '../../types'

const TYPE_LABEL: Record<MemoryType, string> = {
  facts: '事实',
  preferences: '偏好',
  procedures: '流程',
  context: '上下文',
}

const TYPE_COLOR: Record<MemoryType, string> = {
  facts: 'text-blue-500',
  preferences: 'text-emerald-500',
  procedures: 'text-amber-500',
  context: 'text-purple-500',
}

function daysSince(dateStr: string): string {
  const d = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000)
  if (d === 0) return '今天'
  if (d < 30) return `${d}d`
  if (d < 365) return `${Math.floor(d / 30)}mo`
  return `${Math.floor(d / 365)}y`
}

function decayScore(m: ApiMemory): number {
  const halfLife = 90
  const ageDays = (Date.now() - new Date(m.updated_at).getTime()) / 86_400_000
  const recency = Math.pow(0.5, ageDays / halfLife)
  const usage = 1 + Math.log2(1 + m.hits)
  return Math.min(1, 0.7 * recency * usage * (m.pinned ? 10 : 1))
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  const color =
    score > 0.6 ? 'bg-emerald-500' : score > 0.2 ? 'bg-brand' : 'bg-destructive'
  return (
    <div className="h-[3px] w-10 rounded-full bg-border">
      <div className={cn('h-full rounded-full', color)} style={{ width: `${pct}%` }} />
    </div>
  )
}

// ── Inline Edit ──

function EditForm({ memory, agentId, onDone }: { memory: ApiMemory; agentId: string; onDone: () => void }) {
  const [content, setContent] = useState(memory.content)
  const updateMemory = useMemoryStore((s) => s.updateMemory)

  const handleSave = async () => {
    if (!content.trim()) return
    await updateMemory(agentId, memory.id, { content })
    onDone()
  }

  return (
    <div className="space-y-1.5">
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        className="w-full resize-y rounded-md border border-input bg-secondary px-2.5 py-2 text-[13px] leading-relaxed outline-none focus:border-brand focus:ring-1 focus:ring-brand/30"
        rows={2}
        autoFocus
      />
      <div className="flex justify-end gap-1.5">
        <Button variant="ghost" size="sm" onClick={onDone}>取消</Button>
        <Button variant="brand" size="sm" onClick={handleSave}>保存</Button>
      </div>
    </div>
  )
}

// ── Delete Confirm ──

function DeleteConfirm({ memory, agentId, onCancel }: { memory: ApiMemory; agentId: string; onCancel: () => void }) {
  const deleteMemory = useMemoryStore((s) => s.deleteMemory)
  return (
    <div className="mt-2 rounded-md border border-destructive/30 bg-destructive/5 p-2.5">
      <p className="text-[12px] font-medium text-destructive">确定删除这条记忆？</p>
      <div className="mt-2 flex justify-end gap-1.5">
        <Button variant="ghost" size="sm" onClick={onCancel}>取消</Button>
        <Button variant="destructive" size="sm" onClick={() => deleteMemory(agentId, memory.id)}>删除</Button>
      </div>
    </div>
  )
}

// ── Add Memory Form ──

function AddMemoryForm({ agentId, onDone }: { agentId: string; onDone: () => void }) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [memoryType, setMemoryType] = useState<MemoryType>('facts')
  const [content, setContent] = useState('')
  const createMemory = useMemoryStore((s) => s.createMemory)

  const handleCreate = async () => {
    if (!name.trim() || !content.trim()) return
    await createMemory(agentId, {
      name: name.trim(),
      description: description.trim() || content.slice(0, 150),
      memory_type: memoryType,
      content: content.trim(),
    })
    onDone()
  }

  return (
    <div className="space-y-2 border-t p-3">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="记忆名称（简短标识，≤150 字符）"
        className="w-full rounded-md border border-input bg-secondary px-2.5 py-1.5 text-[13px] outline-none placeholder:text-muted-foreground/50 focus:border-brand focus:ring-1 focus:ring-brand/30"
        maxLength={150}
      />
      <input
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="一句话摘要，写清楚在什么场景下应被选中（≤300 字符）"
        className="w-full rounded-md border border-input bg-secondary px-2.5 py-1.5 text-[13px] outline-none placeholder:text-muted-foreground/50 focus:border-brand focus:ring-1 focus:ring-brand/30"
        maxLength={300}
      />
      <select
        value={memoryType}
        onChange={(e) => setMemoryType(e.target.value as MemoryType)}
        className="w-full rounded-md border border-input bg-secondary px-2.5 py-1.5 text-[13px] outline-none focus:border-brand focus:ring-1 focus:ring-brand/30"
      >
        <option value="facts">事实 — 不可从代码推导的事实</option>
        <option value="preferences">偏好 — 行为偏好/已验证的做法</option>
        <option value="procedures">流程 — 操作步骤/规范</option>
        <option value="context">上下文 — 项目动态/外部约束</option>
      </select>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="输入记忆内容..."
        className="w-full resize-y rounded-md border border-input bg-secondary px-2.5 py-2 text-[13px] leading-relaxed outline-none placeholder:text-muted-foreground/50 focus:border-brand focus:ring-1 focus:ring-brand/30"
        rows={2}
        autoFocus
      />
      <div className="flex justify-end gap-1.5">
        <Button variant="ghost" size="sm" onClick={onDone}>取消</Button>
        <Button
          variant="brand"
          size="sm"
          onClick={handleCreate}
          disabled={!name.trim() || !content.trim()}
        >
          添加
        </Button>
      </div>
    </div>
  )
}

// ── Memory Card ──

function MemoryCard({ memory, agentId }: { memory: ApiMemory; agentId: string }) {
  const { editingId, deletingId, setEditing, setDeleting, togglePin } = useMemoryStore()
  const isEditing = editingId === memory.id
  const isDeleting = deletingId === memory.id
  const score = decayScore(memory)

  return (
    <div
      className={cn(
        'group relative rounded-[10px] border bg-card p-3 transition-all',
        memory.pinned && 'border-brand/30 bg-brand-soft/30',
        isEditing && 'border-brand ring-1 ring-brand/20',
        isDeleting && 'border-destructive/40',
      )}
    >
      {/* Hover actions */}
      {!isEditing && !isDeleting && (
        <div className="absolute right-2 top-2 hidden gap-1 group-hover:flex">
          <Button
            variant="outline"
            size="iconSm"
            className={cn('h-6 w-6', memory.pinned && 'text-brand')}
            onClick={() => togglePin(agentId, memory)}
            title={memory.pinned ? '取消钉选' : '钉选'}
          >
            <Icon name="pin" className="h-3 w-3" />
          </Button>
          <Button variant="outline" size="iconSm" className="h-6 w-6" onClick={() => setEditing(memory.id)} title="编辑">
            <Icon name="pencil" className="h-3 w-3" />
          </Button>
          <Button
            variant="outline"
            size="iconSm"
            className="h-6 w-6 hover:border-destructive/40 hover:text-destructive"
            onClick={() => setDeleting(memory.id)}
            title="删除"
          >
            <Icon name="trash2" className="h-3 w-3" />
          </Button>
        </div>
      )}

      {/* Top row: name + type + source */}
      <div className="flex items-center gap-2">
        <span className="text-[13px] font-medium">{memory.name}</span>
        {memory.pinned && <Icon name="pin" className="h-3 w-3 text-brand" />}
        <span className={cn('text-[10px] font-medium', TYPE_COLOR[memory.memory_type])}>
          {TYPE_LABEL[memory.memory_type]}
        </span>
        <span className="ml-auto font-mono text-[9.5px] uppercase tracking-wider text-muted-foreground">
          {memory.source}
        </span>
      </div>

      {/* Description */}
      {memory.description && !isEditing && (
        <p className="mt-0.5 text-[11px] text-muted-foreground">{memory.description}</p>
      )}

      {/* Content or edit form */}
      {isEditing ? (
        <div className="mt-2">
          <EditForm memory={memory} agentId={agentId} onDone={() => setEditing(null)} />
        </div>
      ) : (
        <p className={cn('mt-1.5 text-[13px] leading-relaxed', isDeleting && 'opacity-40', score < 0.15 && 'opacity-50')}>
          {memory.content}
        </p>
      )}

      {/* Delete confirm */}
      {isDeleting && (
        <DeleteConfirm memory={memory} agentId={agentId} onCancel={() => setDeleting(null)} />
      )}

      {/* Meta row */}
      {!isEditing && (
        <div className="mt-2 flex items-center gap-3 font-mono text-[10px] text-muted-foreground">
          <span>{daysSince(memory.updated_at)}</span>
          <span className="text-brand">{memory.hits} hits</span>
          <ScoreBar score={score} />
          {score < 0.15 && !memory.pinned && (
            <span className="text-[9px] uppercase tracking-wider text-destructive">即将淘汰</span>
          )}
        </div>
      )}
    </div>
  )
}

// ── Main Panel ──

interface MemoryPanelProps {
  agentId: string
  agentName?: string
}

export function MemoryPanel({ agentId, agentName }: MemoryPanelProps) {
  const { memories, stats, loading, load, loadStats } = useMemoryStore()
  const [adding, setAdding] = useState(false)
  const filterType = useMemoryStore((s) => s.filterType)
  const setFilter = useMemoryStore((s) => s.setFilter)

  const refresh = useCallback(() => {
    load(agentId)
    loadStats(agentId)
  }, [agentId, load, loadStats])

  useEffect(() => {
    refresh()
  }, [refresh])

  const total = stats?.total ?? memories.length
  const FILTERS: Array<{ label: string; value: MemoryType | null }> = [
    { label: '全部', value: null },
    { label: '事实', value: 'facts' },
    { label: '偏好', value: 'preferences' },
    { label: '流程', value: 'procedures' },
    { label: '上下文', value: 'context' },
  ]

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b px-5 py-3">
        <h2 className="text-[15px] font-medium">Agent 记忆</h2>
        <div className="text-[12px] text-muted-foreground">
          {agentName ?? 'Agent'} &middot; {total} 条记忆
        </div>
      </div>

      {/* Type filter */}
      <div className="flex gap-1 overflow-x-auto border-b bg-card/50 px-3 py-2 [scrollbar-width:none]">
        {FILTERS.map((f) => (
          <button
            key={String(f.value)}
            type="button"
            onClick={() => { setFilter(f.value); load(agentId) }}
            className={cn(
              'shrink-0 rounded-full px-2.5 py-0.5 text-[11px] transition-colors',
              filterType === f.value
                ? 'bg-brand text-white'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {f.label}
            {f.value && stats?.by_type[f.value] != null && (
              <span className="ml-1 opacity-60">{stats.by_type[f.value]}</span>
            )}
          </button>
        ))}
      </div>

      {/* Memory list */}
      <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto p-3 [scrollbar-width:thin]">
        {loading && memories.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-[13px] text-muted-foreground">加载中...</div>
        ) : memories.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-[13px] text-muted-foreground">暂无记忆</div>
        ) : (
          memories.map((m) => <MemoryCard key={m.id} memory={m} agentId={agentId} />)
        )}
      </div>

      {/* Add button / form */}
      {adding ? (
        <AddMemoryForm agentId={agentId} onDone={() => { setAdding(false); refresh() }} />
      ) : (
        <div className="border-t p-3">
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="w-full rounded-[10px] border border-dashed border-border py-2.5 text-[13px] text-muted-foreground transition-colors hover:border-brand hover:text-brand"
          >
            <Icon name="plus" className="mr-1.5 inline h-3.5 w-3.5" />
            手动添加记忆
          </button>
        </div>
      )}
    </div>
  )
}
