import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Docker 内设 VITE_PROXY_TARGET=http://backend:8000；本地默认 localhost:8000
const backendUrl = process.env.VITE_PROXY_TARGET || process.env.BACKEND_URL || 'http://localhost:8000'
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
