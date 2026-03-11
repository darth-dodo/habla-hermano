import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    root: '.',
    include: ['tests/js/**/*.test.js'],
  },
});
