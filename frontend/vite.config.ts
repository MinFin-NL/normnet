import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // The Python API runs separately in dev; proxying keeps the frontend
    // same-origin so EventSource and fetch need no CORS special-casing.
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
  },
})
