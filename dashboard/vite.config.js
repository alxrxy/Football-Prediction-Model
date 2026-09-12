import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Relative base so a built dashboard works from any static host or file path.
export default defineConfig({
  plugins: [react()],
  base: './',
  server: { port: 5173, open: true },
})
