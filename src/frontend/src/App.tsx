import { useEffect } from 'react'
import { AppShell } from './components/layout/AppShell'
import { applyTweaks } from './lib/theme'
import { sessionsApi } from './api/sessions'
import { useAgentStore } from './stores/agentStore'
import { useChatStore } from './stores/chatStore'
import { useGroupStore } from './stores/groupStore'
import { useUIStore } from './stores/uiStore'

function App() {
  const theme = useUIStore((s) => s.theme)
  const accent = useUIStore((s) => s.accent)
  const density = useUIStore((s) => s.density)
  const headingFont = useUIStore((s) => s.headingFont)
  const loadAgents = useAgentStore((s) => s.loadAgents)
  const fetchGroups = useGroupStore((s) => s.fetchGroups)
  const hydrateFromSessions = useChatStore((s) => s.hydrateFromSessions)

  useEffect(() => {
    applyTweaks({ theme, accent, density, headingFont })
  }, [theme, accent, density, headingFont])

  // 挂载时拉取后端真实 Agent 并入列表（失败保持 mock）
  useEffect(() => {
    void loadAgents()
  }, [loadAgents])

  // 挂载时拉取后端真实群组并入左栏（失败保持 mock）
  useEffect(() => {
    void fetchGroups()
  }, [fetchGroups])

  // M1#1：挂载时拉取后端私聊 Session 并回灌到 chatStore（私聊死路修复）
  // 失败静默 — 新用户本就无会话，store 保持空态 → LeftPanel 渲染 CTA
  useEffect(() => {
    sessionsApi
      .list({ type: 'private' })
      .then((sessions) => hydrateFromSessions(sessions))
      .catch((err) => console.warn('[hydrate] sessions list failed', err))
  }, [hydrateFromSessions])

  return <AppShell />
}

export default App
