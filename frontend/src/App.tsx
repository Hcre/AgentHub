import { useEffect } from 'react'
import { AppShell } from './components/layout/AppShell'
import { applyTweaks } from './lib/theme'
import { useAgentStore } from './stores/agentStore'
import { useUIStore } from './stores/uiStore'

function App() {
  const theme = useUIStore((s) => s.theme)
  const accent = useUIStore((s) => s.accent)
  const density = useUIStore((s) => s.density)
  const headingFont = useUIStore((s) => s.headingFont)
  const loadAgents = useAgentStore((s) => s.loadAgents)

  useEffect(() => {
    applyTweaks({ theme, accent, density, headingFont })
  }, [theme, accent, density, headingFont])

  // 挂载时拉取后端真实 Agent 并入列表（失败保持 mock）
  useEffect(() => {
    void loadAgents()
  }, [loadAgents])

  return <AppShell />
}

export default App
