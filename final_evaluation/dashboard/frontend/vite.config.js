import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Study dashboard build config. Proxies /api to the local backend during `npm run dev`
// so the two can be developed against each other without CORS; the production build
// (`npm run build` -> dist/) is served by FastAPI itself (see backend/app.py), same
// origin, no proxy needed there.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5183,
    proxy: {
      '/api': 'http://127.0.0.1:8010',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
