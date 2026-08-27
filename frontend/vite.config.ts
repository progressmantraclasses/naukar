import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
  },
  base: './',
  optimizeDeps: {
    include: ['react', 'react-dom', 'zustand', 'framer-motion'],
  },
  build: {
    target: 'es2022',
    sourcemap: false,
    cssCodeSplit: true,
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
})
