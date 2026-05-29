import { useEffect, useRef, useState } from 'react'
import { cn } from '../../lib/cn'
import { groupsApi } from '../../api/groups'
import { useGroupWebSocket } from '../../hooks/useGroupWebSocket'
import { useGroupStore } from '../../stores/groupStore'
import { useTaskStore } from '../../stores/taskStore'
import { useUIStore } from '../../stores/uiStore'
import { Avatar, Button, Icon } from '../ui'
import { GroupComposer } from './GroupComposer'
import { GroupMembersStrip } from './GroupMembersStrip'
import { GroupMessageItem } from './GroupMessageItem'
import { lookupActor } from './actors'
import type { IconName } from '../../types'

const CHANNEL_TABS: { id: string; icon: IconName; label: string }[] = [
  { id: 'chat', icon: 'chat', label: '聊天' },
  { id: 'files', icon: 'files', label: '文件' },
  { id: 'tasks', icon: 'listCheck', label: '任务' },
]

export function GroupChatView() {
  const activeGroupId = useUIStore((s) => s.activeGroupId)
  const theme = useUIStore((s) => s.theme)
  const toggleTheme = useUIStore((s) => s.toggleTheme)
  const viewAgent = useUIStore((s) => s.viewAgent)
  const groups = useGroupStore((s) => s.groups)
  const messagesByGroup = useGroupStore((s) => s.messagesByGroup)
  const sendGroup = useGroupStore((s) => s.sendGroup)
  const sessionIdsByGroup = useGroupStore((s) => s.sessionIdsByGroup)
  const setGroupSession = useGroupStore((s) => s.setGroupSession)
  const loadGroupHistory = useGroupStore((s) => s.loadGroupHistory)
  const tasks = useTaskStore((s) => s.tasks)
  const [tab, setTab] = useState('chat')
  const scrollRef = useRef<HTMLDivElement>(null)

  const group = groups.find((g) => g.id === activeGroupId)
  const msgs = activeGroupId ? (messagesByGroup[activeGroupId] ?? []) : []
  const sessionId = activeGroupId ? (sessionIdsByGroup[activeGroupId] ?? null) : null

  // 1. 切换群聊 → 找回或创建对应 session
  useEffect(() => {
    if (!activeGroupId || sessionId) return
    let cancelled = false
    groupsApi
      .findOrCreateSession(activeGroupId)
      .then((s) => {
        if (!cancelled) setGroupSession(activeGroupId, s.id)
      })
      .catch(() => {
        // 后端不可用 → 保留 UI 骨架，sendGroup 仅本地回显
      })
    return () => {
      cancelled = true
    }
  }, [activeGroupId, sessionId, setGroupSession])

  // 2. session 就绪 → 拉一次历史
  useEffect(() => {
    if (!activeGroupId || !sessionId) return
    void loadGroupHistory(activeGroupId)
  }, [activeGroupId, sessionId, loadGroupHistory])

  // 3. 挂载 WS
  useGroupWebSocket(activeGroupId ?? null, sessionId)

  useEffect(() => {
    if (tab === 'chat' && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [msgs.length, tab])

  if (!group) {
    return (
      <div className="glass-panel flex h-full flex-col items-center justify-center rounded-2xl border text-muted-foreground shadow-sm">
        <Icon name="channels" className="h-8 w-8" />
        <p className="mt-2 text-sm">在左侧「频道」里挑一个团队对话。</p>
      </div>
    )
  }

  const channelTasks = tasks.filter((t) => t.assignee && group.members.includes(t.assignee))

  return (
    <main className="glass-panel flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border shadow-sm">
      <header className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-3.5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
            <Icon name="channels" className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-[20px] font-medium tracking-tight">{group.name}</h1>
            <div className="mt-0.5 truncate font-mono text-[10.5px] uppercase tracking-wider text-muted-foreground">
              群聊 · {group.description}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <GroupMembersStrip group={group} onPick={viewAgent} />
          <div className="h-5 w-px bg-border" />
          <Button variant="ghost" size="iconSm" onClick={toggleTheme} title="切换主题">
            <Icon name={theme === 'light' ? 'moon' : 'sun'} className="h-3.5 w-3.5" />
          </Button>
          <Button variant="ghost" size="iconSm" title="频道设置">
            <Icon name="settings" className="h-3.5 w-3.5" />
          </Button>
        </div>
      </header>

      <nav className="border-b border-border/70 px-3 py-1.5 glass-soft">
        <div className="flex gap-0.5">
          {CHANNEL_TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              data-active={tab === t.id ? 'true' : undefined}
              className={cn(
                'inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-[12.5px] font-medium text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground',
                'data-[active=true]:text-foreground data-[active=true]:shadow-sm data-[active=true]:glass-strong',
              )}
            >
              <Icon name={t.icon} className="h-3.5 w-3.5" />
              {t.label}
            </button>
          ))}
        </div>
      </nav>

      {tab === 'chat' && (
        <>
          {group.pinnedTask && (
            <div className="flex items-center gap-2 border-b border-border/60 bg-brand-soft/30 px-5 py-1.5">
              <Icon name="pin" className="h-2.5 w-2.5 text-brand-deep" />
              <span className="text-[12px] text-brand-deep">{group.pinnedTask}</span>
            </div>
          )}
          <div ref={scrollRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5">
            {msgs.map((m) => (
              <GroupMessageItem key={m.id} msg={m} group={group} />
            ))}
          </div>
          <GroupComposer group={group} onSend={(text, opts) => sendGroup(group.id, text, opts)} />
        </>
      )}

      {tab === 'files' && (
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <div className="grid grid-cols-[repeat(auto-fill,minmax(200px,1fr))] gap-3">
            {[`${group.name}-brief.mdx`, `${group.name}-tokens.json`].map((name) => (
              <div
                key={name}
                className="space-y-2 rounded-xl border bg-card p-4 transition-all hover:-translate-y-px hover:shadow-sm"
              >
                <div className="grid h-10 w-10 place-items-center rounded-md border bg-muted/30">
                  <Icon name="doc" className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="truncate font-mono text-[13px]">{name}</div>
                <div className="font-mono text-[11px] text-muted-foreground">Document</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === 'tasks' && (
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
          <div className="overflow-hidden rounded-xl border bg-card">
            {channelTasks.length === 0 ? (
              <div className="px-4 py-10 text-center text-[12.5px] text-muted-foreground">
                该频道还没有任务
              </div>
            ) : (
              channelTasks.map((t, i) => {
                const a = t.assignee ? lookupActor(t.assignee, group) : undefined
                return (
                  <div
                    key={t.id}
                    className={cn('flex items-center gap-3 px-4 py-2.5', i > 0 && 'border-t')}
                  >
                    <span className="w-10 font-mono text-[10.5px] text-muted-foreground">
                      {t.id}
                    </span>
                    <span className="flex-1 text-[13px]">{t.title}</span>
                    {a && <Avatar initial={a.initial} color={a.color} size={20} />}
                    <span className="w-12 text-right font-mono text-[10.5px] text-muted-foreground">
                      {t.due}
                    </span>
                  </div>
                )
              })
            )}
          </div>
        </div>
      )}
    </main>
  )
}
