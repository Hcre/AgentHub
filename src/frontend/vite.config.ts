import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 本地默认指向 localhost:8000；Docker 内设 VITE_PROXY_TARGET=http://backend:8000
const PROXY_TARGET = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': PROXY_TARGET,
      '/ws': {
        target: PROXY_TARGET.replace('http://', 'ws://'),
        ws: true,
      },
    },
  },
})
