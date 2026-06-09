import { useEffect, useMemo, useState } from 'react'
import { groupsApi } from '../../api/groups'
import { useDebounce } from '../../hooks/useDebounce'
import { useAgentStore } from '../../stores/agentStore'
import { useGroupStore } from '../../stores/groupStore'
import { useUIStore } from '../../stores/uiStore'
import { Avatar, Button, Dialog, DialogContent, Icon, Input, Textarea, WorkspaceBrowser } from '../ui'

function Label({ children }: { children: string }) {
  return <span className="text-[12px] font-medium text-muted-foreground">{children}</span>
}

type NameState = 'idle' | 'checking' | 'ok' | 'taken' | 'invalid'

// 名称规则：首字符为字母或中文，后可跟字母/中文/数字/连字符/下划线，2-32 字符
const NAME_RE = /^[一-鿿a-zA-Z][一-鿿a-zA-Z0-9_-]{1,31}$/

const HINT: Record<NameState, { text: string; cls: string }> = {
  idle: { text: '字母或中文开头，支持中文、字母、数字、连字符、下划线。', cls: 'text-muted-foreground' },
  checking: { text: '校验中…', cls: 'text-muted-foreground' },
  ok: { text: '✓ 名称可用', cls: 'text-emerald-600' },
  taken: { text: '名称已存在', cls: 'text-destructive' },
  invalid: { text: '格式不合法：字母或中文开头，2-32 字符。', cls: 'text-destructive' },
}

export function CreateGroupModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const agents = useAgentStore((s) => s.agents)
  const createGroup = useGroupStore((s) => s.createGroup)
  const openGroup = useUIStore((s) => s.openGroup)
  const setFileWorkdir = useUIStore((s) => s.setFileWorkdir)

  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [workdir, setWorkdir] = useState('')
  const [wsBrowserOpen, setWsBrowserOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string[]>([])
  // 服务端校验结果按名称缓存；'unknown' = 后端不可用，提交时由 409 兜底
  const [checked, setChecked] = useState<Record<string, 'ok' | 'taken' | 'unknown'>>({})
  const [submitting, setSubmitting] = useState(false)

  const debouncedName = useDebounce(name, 300)

  // 名称服务端唯一性校验。setState 只在异步回调里发生（满足 react-hooks/set-state-in-effect）。
  useEffect(() => {
    if (!debouncedName || !NAME_RE.test(debouncedName) || debouncedName in checked) return
    let alive = true
    groupsApi
      .checkName(debouncedName)
      .then((r) => {
        if (alive) setChecked((m) => ({ ...m, [debouncedName]: r.available ? 'ok' : 'taken' }))
      })
      .catch(() => {
        if (alive) setChecked((m) => ({ ...m, [debouncedName]: 'unknown' }))
      })
    return () => {
      alive = false
    }
  }, [debouncedName, checked])

  // 名称状态：格式由 name 直接派生；服务端结果查缓存（未命中=校验中，'unknown'=后端不可用→可提交兜底）
  const cached = checked[name]
  const nameState: NameState = !name
    ? 'idle'
    : !NAME_RE.test(name)
      ? 'invalid'
      : cached === undefined
        ? 'checking'
        : cached === 'unknown'
          ? 'idle'
          : cached

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? agents.filter((a) => a.name.toLowerCase().includes(q)) : agents
  }, [agents, query])

  const reset = () => {
    setName('')
    setDescription('')
    setWorkdir('')
    setQuery('')
    setSelected([])
    setChecked({})
  }

  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  const canSubmit =
    NAME_RE.test(name) &&
    nameState !== 'taken' &&
    nameState !== 'checking' &&
    workdir.trim().length > 0 &&
    !submitting

  const [credMissing, setCredMissing] = useState(false)

  const submit = async () => {
    if (!canSubmit) return
    setSubmitting(true)
    setCredMissing(false)
    try {
      // 预检：协调者凭证是否已配置
      const statusRes = await fetch('/api/agents/coordinator/credential/status')
      const status = await statusRes.json().catch(() => ({}))
      if (!status.configured) {
        setCredMissing(true)
        return
      }
      const id = await createGroup({
        name: name.trim(),
        description: description.trim() || undefined,
        member_ids: selected,
        workdir: workdir.trim(),
      })
      if (workdir.trim()) setFileWorkdir(workdir.trim())
      reset()
      onClose()
      openGroup(id)
    } catch {
      // 创建失败：留 UI 让用户重试
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <header className="border-b px-4 py-3">
          <div className="flex items-center justify-between">
            <h3 className="text-[15px] font-medium">新建群组频道</h3>
            <Button variant="ghost" size="iconSm" onClick={onClose}>
              <Icon name="x" className="h-3.5 w-3.5" />
            </Button>
          </div>
          <p className="mt-0.5 text-[12px] text-muted-foreground">和合适的队友一起开始共享对话。</p>
        </header>

        <div className="flex flex-col gap-3 overflow-y-auto p-4">
          <label className="flex flex-col gap-1">
            <Label>频道名称 *</Label>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="design-review"
              autoFocus
            />
            <span className={`text-[11px] ${HINT[nameState].cls}`}>{HINT[nameState].text}</span>
          </label>

          <label className="flex flex-col gap-1">
            <Label>描述</Label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="这个频道用于什么?"
              className="min-h-[60px]"
            />
          </label>

          <label className="flex flex-col gap-1">
            <Label>工作目录 *</Label>
            <div className="flex gap-1">
              <Input
                value={workdir}
                onChange={(e) => setWorkdir(e.target.value)}
                placeholder="选择项目根目录（必填，用于群聊上下文）…"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => setWsBrowserOpen(true)}
                type="button"
              >
                浏览
              </Button>
            </div>
            <p className="font-mono text-[11px] text-muted-foreground/70">
              群聊将以该目录作为上下文根（可在 WorkspaceBrowser 里点 + 新建文件夹）
            </p>
          </label>

          <div className="flex flex-col gap-1">
            <div className="flex items-center justify-between">
              <Label>成员</Label>
              <span className="text-[11px] text-muted-foreground">已选择 {selected.length} 位</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
              {/* 左：搜索 + 勾选 */}
              <div className="flex flex-col rounded-md border">
                <div className="flex items-center gap-2 border-b px-2.5 py-1.5 text-muted-foreground">
                  <Icon name="search" className="h-3.5 w-3.5" />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="搜索工作区成员"
                    className="min-w-0 flex-1 bg-transparent text-[13px] outline-none placeholder:text-muted-foreground/70"
                  />
                </div>
                <div className="max-h-[180px] overflow-y-auto p-1">
                  {filtered.map((a) => {
                    const on = selected.includes(a.id)
                    return (
                      <button
                        key={a.id}
                        onClick={() => toggle(a.id)}
                        className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                      >
                        <span className="grid h-4 w-4 place-items-center rounded border">
                          {on && <Icon name="check" className="h-3 w-3 text-brand" />}
                        </span>
                        <Avatar initial={a.name[0] ?? '?'} color={a.color} size={32} />
                        <span className="flex-1 truncate">{a.name}</span>
                      </button>
                    )
                  })}
                  {filtered.length === 0 && (
                    <p className="px-2 py-4 text-center text-[12px] text-muted-foreground">无匹配成员</p>
                  )}
                </div>
              </div>

              {/* 右：已选成员 */}
              <div className="flex flex-col rounded-md border">
                <div className="border-b px-2.5 py-1.5 text-[12px] font-medium text-muted-foreground">
                  已选成员
                </div>
                <div className="max-h-[180px] overflow-y-auto p-1">
                  <p className="px-2 pt-1 text-[11px] text-muted-foreground">频道创建者会自动包含在内。</p>
                  {selected.length === 0 ? (
                    <p className="px-2 py-4 text-center text-[12px] text-muted-foreground">
                      还没有选择其他成员。
                    </p>
                  ) : (
                    selected.map((id) => {
                      const a = agents.find((x) => x.id === id)
                      if (!a) return null
                      return (
                        <div key={id} className="flex items-center gap-2 rounded-md px-2 py-1.5 text-sm">
                          <Avatar initial={a.name[0] ?? '?'} color={a.color} size={32} />
                          <span className="flex-1 truncate">{a.name}</span>
                          <button
                            onClick={() => toggle(id)}
                            className="grid h-4 w-4 place-items-center rounded hover:bg-accent"
                            title="移除"
                          >
                            <Icon name="x" className="h-3 w-3" />
                          </button>
                        </div>
                      )
                    })
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {credMissing && (
          <div className="border-t border-amber-200 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950/30">
            <p className="text-[13px] font-medium text-amber-800 dark:text-amber-200">
              协调者凭证未配置
            </p>
            <p className="mt-0.5 text-[12px] text-amber-700 dark:text-amber-300">
              群组需要协调者调用 LLM 来路由消息和拆解任务。请先前往
              <button
                type="button"
                onClick={() => { onClose(); useUIStore.getState().setSection('settings') }}
                className="mx-1 font-medium underline underline-offset-2 hover:text-amber-900 dark:hover:text-amber-100"
              >
                设置 → 协调者凭证
              </button>
              配置 API Key。
            </p>
          </div>
        )}

        <footer className="flex justify-end gap-2 border-t px-4 py-3">
          <Button variant="outline" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button variant="brand" size="sm" onClick={submit} disabled={!canSubmit}>
            创建
          </Button>
        </footer>

        <WorkspaceBrowser
          key={wsBrowserOpen ? 'open' : 'closed'}
          open={wsBrowserOpen}
          onClose={() => setWsBrowserOpen(false)}
          onSelect={(path) => {
            setWorkdir(path)
            setWsBrowserOpen(false)
          }}
        />
      </DialogContent>
    </Dialog>
  )
}
