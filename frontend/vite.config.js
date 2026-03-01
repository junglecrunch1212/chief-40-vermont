import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../static',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:3141',
      '/health': 'http://localhost:3141',
      '/webhooks': 'http://localhost:3141',
      '/scoreboard': 'http://localhost:3141',
    },
  },
})
