import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Plan 7 / C0: ../shared/ has no node_modules of its own. When vitest runs
// the shared tests, Node's module resolution walks UP from the test file
// (pitcher_program_app/shared/...) past pitcher_program_app/ and never reaches
// mini-app/node_modules/. Forward those package names through resolve.alias
// so the shared tests pick up the consuming app's installed copies.
const sharedTestDeps = {
  '@testing-library/react':      path.resolve(__dirname, 'node_modules/@testing-library/react'),
  '@testing-library/user-event': path.resolve(__dirname, 'node_modules/@testing-library/user-event'),
  '@testing-library/jest-dom':   path.resolve(__dirname, 'node_modules/@testing-library/jest-dom'),
  vitest:                        path.resolve(__dirname, 'node_modules/vitest'),
  react:                         path.resolve(__dirname, 'node_modules/react'),
  'react-dom':                   path.resolve(__dirname, 'node_modules/react-dom'),
};

export default defineConfig({
  plugins: [react({ jsxRuntime: 'automatic' })],
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, '../shared'),
      ...sharedTestDeps,
    },
  },
  // Plan 7 / C0: vite's fs.allow guard blocks files outside the project root
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
    css: false,
    // Plan 7 / C0: pick up tests from `../shared/` so the mini-app suite
    // exercises the shared BuilderSlideOver alongside its in-tree consumers.
    include: [
      'src/**/*.{test,spec}.?(c|m)[jt]s?(x)',
      '../shared/**/*.{test,spec}.?(c|m)[jt]s?(x)',
    ],
  },
})
