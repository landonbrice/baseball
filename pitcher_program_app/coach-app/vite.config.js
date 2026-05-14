import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Plan 7 / C4: ../shared/ has no node_modules of its own. Vite 8 + rolldown
// (this app) is stricter than Vite 6 (mini-app) — when it transforms a file
// from outside the project root, Node walks up from pitcher_program_app/shared/
// past pitcher_program_app/ and never reaches coach-app/node_modules/, so
// imports of `react` / `react-dom` from shared/builder/BuilderSlideOver.jsx
// fail to resolve at build time. Pointing those package names at this app's
// installed copies via resolve.alias fixes the production build.
const sharedDeps = {
  react:       path.resolve(__dirname, 'node_modules/react'),
  'react-dom': path.resolve(__dirname, 'node_modules/react-dom'),
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    // Vite blocks files outside the project root unless explicitly permitted.
    // shared/ sits one level up.
    fs: {
      allow: [path.resolve(__dirname, '..')],
    },
  },
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, '../shared'),
      ...sharedDeps,
    },
  },
})
