import { fileURLToPath } from 'node:url'
import { defineConfig, searchForWorkspaceRoot } from 'vite'
import react from '@vitejs/plugin-react'

// The Mammoth Paths SDK lives in the repo root and is consumed from source.
const pathsSdkDir = fileURLToPath(new URL('../../packages/mammoth-paths', import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@mammothos/paths': `${pathsSdkDir}/src/index.js`,
    },
  },
  server: {
    host: '0.0.0.0',
    fs: {
      allow: [searchForWorkspaceRoot(process.cwd()), pathsSdkDir],
    },
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/ws':  { target: 'ws://localhost:8000',  ws: true },
    },
  },
  build: {
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react/') || id.includes('node_modules/react-dom/')) {
            return 'react'
          }
          if (id.includes('node_modules/lucide-react/')) {
            return 'icons'
          }
        },
      },
    },
  },
})