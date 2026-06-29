import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { visualizer } from 'rollup-plugin-visualizer'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // Ref: #149 — Generate bundle size stats for analysis.
    // Output: dist/stats.json (rollup visualizer JSON format).
    visualizer({
      filename: 'dist/stats.json',
      template: 'raw-data' as const,
    }),
  ],
  // Ref: #66 — Use relative asset paths so file:// loading works in
  // PyWebView / PyInstaller bundles (default '/' breaks when not served
  // by an HTTP server).
  base: './',
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: 'dist',
  },
})
