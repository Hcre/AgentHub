import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      // 开发时前端请求自动转发到后端，规避 CORS
      '/api': 'http://localhost:9000',
      '/ws': {
        target: 'ws://localhost:9000',
        ws: true,
      },
    },
  },
})
