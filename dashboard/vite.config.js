import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api goes to the local Claude Q&A server (python -m src.api_server), which
// holds the API key so the page never has to.
const api = { '/api': 'http://127.0.0.1:8787' }

// Relative base so a built dashboard works from any static host or file path.
// Port 5174: localhost:5173 is the Vite default, and another project's service
// worker registered there will answer for it instead of this dashboard.
export default defineConfig({
  plugins: [react()],
  base: './',
  server: { port: 5174, open: true, proxy: api },
  preview: { proxy: api },
})
