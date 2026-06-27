import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src/frontend/src'),
    },
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true
      }
    },
    watch: {
      // 排除后端数据文件，防止后端操作触发前端 HMR full page reload
      ignored: ['**/output/**', '**/*.db', '**/*.db-journal', '**/*.db-wal', '**/.env']
    }
  },
  build: {
    outDir: 'dist'
  }
})
