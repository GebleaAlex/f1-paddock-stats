import { defineConfig } from 'vitest/config'

// Unit tests for the plain TypeScript helpers (formatting, colours, chart maths). Pages are covered by the
// backend API tests and by checking the running site.
export default defineConfig({
  test: { include: ['tests/**/*.test.ts'], environment: 'node' },
})
