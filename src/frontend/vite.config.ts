import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // proxy target 用 docker-compose service name 'backend'（不是 localhost:8000，
    // 后者在容器内指向 frontend 容器自己，没有 8000 端口）。
    // nginx.conf 已经这么写；v0.dev nginx serve 静态产物模式下也用 backend:8000。
    // host/CHOKIDAR_USEPOLLING 由 docker-compose + Dockerfile 注入（dev 容器专用）。
    proxy: {
      '/api': 'http://backend:8000',
      '/ws': {
        target: 'ws://backend:8000',
        ws: true,
      },
    },
  },
})
