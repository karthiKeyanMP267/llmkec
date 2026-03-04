import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts: ['.ngrok-free.app'],
    proxy: {
      '/api': {
        // Point the web dev server at the running backend API (currently on 4001)
        target: process.env.VITE_SERVER_URL || 'http://localhost:4001',
        changeOrigin: true,
        timeout: 120_000,
        proxyTimeout: 120_000,
      },
      '/auth': {
        // Proxy auth requests so ngrok only needs one tunnel (port 5173)
        target: process.env.VITE_AUTH_PROXY_URL || 'http://localhost:4005',
        changeOrigin: true,
        timeout: 30_000,
        proxyTimeout: 30_000,
      },
    },
  },
})
