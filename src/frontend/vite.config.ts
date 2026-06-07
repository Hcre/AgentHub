import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/

// Proxy target 解析规则（按顺序）:
//   1. 环境变量 BACKEND_URL 显式覆盖
//   2. VITE_BACKEND_URL 显式覆盖
//   3. 默认 http://localhost:18000 (主机开发模式 — 后端走 docker 主机端口映射)
//
// 容器内模式: docker compose 注入 BACKEND_URL=http://backend:8000
// 主机模式:   不设环境变量，default 即 localhost:18000
const backendUrl = process.env.BACKEND_URL || process.env.VITE_BACKEND_URL || 'http://localhost:18000'
const backendWsUrl = backendUrl.replace(/^http/, 'ws')

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': backendUrl,
      '/ws': {
        target: backendWsUrl,
        ws: true,
      },
    },
  },
})

