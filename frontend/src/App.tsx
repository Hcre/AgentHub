import { useEffect } from 'react'
import { AppShell } from './components/layout/AppShell'
import { useUIStore } from './stores/uiStore'

function App() {
  const theme = useUIStore((s) => s.theme)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  return <AppShell />
}

export default App
