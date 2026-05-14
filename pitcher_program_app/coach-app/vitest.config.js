import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Plan 7 / C4: ../shared/ has no node_modules of its own. When vitest imports
// the shared BuilderSlideOver (or runs shared/__tests__/), Node walks up from
// pitcher_program_app/shared/ past pitcher_program_app/ and never reaches
// coach-app/node_modules/. Forward those package names through resolve.alias
// so shared code picks up the consuming app's installed copies. Same pattern
// as the mini-app's vitest.config.js (Plan 7 / C0).
const sharedTestDeps = {
  '@testing-library/react':      path.resolve(__dirname, 'node_modules/@testing-library/react'),
  '@testing-library/user-event': path.resolve(__dirname, 'node_modules/@testing-library/user-event'),
  '@testing-library/jest-dom':   path.resolve(__dirname, 'node_modules/@testing-library/jest-dom'),
  vitest:                        path.resolve(__dirname, 'node_modules/vitest'),
  react:                         path.resolve(__dirname, 'node_modules/react'),
  'react-dom':                   path.resolve(__dirname, 'node_modules/react-dom'),
};

export default defineConfig({
  plugins: [react({ jsxRuntime: 'automatic' }), tailwindcss()],
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, '../shared'),
      ...sharedTestDeps,
    },
  },
  // Plan 7 / C4: vite's fs.allow guard blocks files outside the project root
  // unless explicitly permitted. The shared/ workspace sits one level up.
  server: {
    fs: {
      allow: [path.resolve(__dirname, '..')],
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.js'],
    css: true,
  },
})
