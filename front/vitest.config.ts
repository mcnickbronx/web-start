import { defineConfig } from 'vitest/config'

// Тесты чистых функций слоёв: layers/<слой>/tests/*.test.ts
export default defineConfig({
  test: { include: ['layers/*/tests/**/*.test.ts'], environment: 'node' },
})
