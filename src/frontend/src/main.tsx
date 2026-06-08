import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/index.css'
import App from './App.tsx'

// 一次性清理旧 mock 缓存，避免过期数据阻塞 WebSocket 连接
const CLEARED_KEY = '__agenthub_cache_cleared_v1'
if (!localStorage.getItem(CLEARED_KEY)) {
  localStorage.removeItem('agenthub-chat')
  localStorage.removeItem('agenthub-agents')
  localStorage.setItem(CLEARED_KEY, '1')
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
