import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  // Same `~` alias as Nuxt, so the pure helpers in app/utils can be tested without a Nuxt runtime.
  resolve: { alias: { '~': fileURLToPath(new URL('./app', import.meta.url)) } },
  test: { include: ['tests/**/*.test.ts'] },
})
