import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/',
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, '../shared'),
      // ../shared/ has no node_modules of its own. Under Vite 8 (Rolldown), a
      // bare `react`/`react-dom` import from a file outside the project root
      // can't be resolved by walking up. Forward them to the mini-app's copy —
      // same fix vitest.config.js already applies for the shared tests.
      react: path.resolve(__dirname, 'node_modules/react'),
      'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
    },
    dedupe: ['react', 'react-dom'],
  },
  // Let the dev server serve files from the sibling shared/ workspace.
  server: {
    fs: {
      allow: [path.resolve(__dirname, '..')],
    },
  },
})
