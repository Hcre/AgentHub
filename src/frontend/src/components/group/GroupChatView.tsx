import { useEffect, useRef } from 'react'
import { cn } from '../../lib/cn'
import { groupsApi } from '../../api/groups'
import { useGroupWebSocket } from '../../hooks/useGroupWebSocket'
import { useGroupStore } from '../../stores/groupStore'
import { useUIStore } from '../../stores/uiStore'
import { Icon } from '../ui'
import { GroupComposer } from './GroupComposer'
import { GroupMembersStrip } from './GroupMembersStrip'
import { GroupMessageItem } from './GroupMessageItem'

/**
 * 群聊主界面（与私聊 ChatView 同 shell 框架）：
 *   - header：群头像 + 群名 + 描述 + 主题切换 + 设置
 *   - 「同位置条」：私聊是 Tabs，群聊是 群成员条（GroupMembersStrip）
 *   - 消息区
 *   - 群组输入框
 *
 * 这样切换私聊 / 群聊时，header 风格与下方"二级条"位置一致，体感统一。
 */
export function GroupChatView() {
  const activeGroupId = useUIStore((s) => s.activeGroupId)
  const rightCollapsed = useUIStore((s) => s.rightCollapsed)
  const toggleRight = useUIStore((s) => s.toggleRight)
  const viewAgent = useUIStore((s) => s.viewAgent)
  const groups = useGroupStore((s) => s.groups)
  const messagesByGroup = useGroupStore((s) => s.messagesByGroup)
  const sendGroup = useGroupStore((s) => s.sendGroup)
  const sessionIdsByGroup = useGroupStore((s) => s.sessionIdsByGroup)
  const setGroupSession = useGroupStore((s) => s.setGroupSession)
  const loadGroupHistory = useGroupStore((s) => s.loadGroupHistory)
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
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [msgs.length])

  if (!group) {
    return (
      <div className="glass-panel flex h-full flex-col items-center justify-center rounded-2xl border text-muted-foreground shadow-sm">
        <Icon name="channels" className="h-8 w-8" />
        <p className="mt-2 text-sm">在「群组」里挑一个群进入对话。</p>
      </div>
    )
  }

  return (
    <main className="glass-panel flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border shadow-sm">
      {/* header：与私聊 ChatView 同结构 */}
      <header className="flex items-center justify-between gap-3 border-b border-border/70 px-5 py-3.5">
        <div className="flex min-w-0 items-center gap-3">
          <div className="grid h-8 w-8 flex-shrink-0 place-items-center rounded-lg bg-brand/10 text-brand">
            <Icon name="channels" className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-[15px] font-medium">{group.name}</h1>
            <div className="truncate font-mono text-[10.5px] text-muted-foreground">
              {group.members.length} 位成员 · 群组
            </div>
          </div>
        </div>
        <div className="flex flex-shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={toggleRight}
            title={rightCollapsed ? '展开右侧面板' : '收起右侧面板'}
            className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Icon name="panelRight" className="h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      {/* 二级条（同位置：私聊=Tabs / 群聊=群成员条） */}
      <div className="border-b border-border/70 glass-soft">
        <div className="px-3 py-2">
          <GroupMembersStrip group={group} onPick={viewAgent} />
        </div>
      </div>

      {group.pinnedTask && (
        <div className="flex items-center gap-2 border-b border-border/60 bg-brand-soft/30 px-5 py-1.5">
          <Icon name="pin" className="h-2.5 w-2.5 text-brand-deep" />
          <span className="text-[12px] text-brand-deep">{group.pinnedTask}</span>
        </div>
      )}

      {/* 消息区 */}
      <div ref={scrollRef} className={cn('min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5')}>
        {msgs.map((m) => (
          <GroupMessageItem key={m.id} msg={m} group={group} />
        ))}
      </div>

      {/* 输入框 */}
      <GroupComposer group={group} onSend={(text, opts) => sendGroup(group.id, text, opts)} />
    </main>
  )
}
