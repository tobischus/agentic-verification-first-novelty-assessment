import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server on :5173; the SPA talks to the FastAPI backend (default
// http://127.0.0.1:8099) via VITE_API_BASE (CORS is enabled on the backend).
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
})
