import { useEffect } from 'react'
import { AppShell } from './components/layout/AppShell'
import { applyTweaks } from './lib/theme'
import { useUIStore } from './stores/uiStore'

function App() {
  const theme = useUIStore((s) => s.theme)
  const accent = useUIStore((s) => s.accent)
  const density = useUIStore((s) => s.density)
  const headingFont = useUIStore((s) => s.headingFont)

  useEffect(() => {
    applyTweaks({ theme, accent, density, headingFont })
  }, [theme, accent, density, headingFont])

  return <AppShell />
}

export default App
