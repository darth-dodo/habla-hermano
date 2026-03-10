import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    root: '.',
    include: ['tests/js/**/*.test.js'],
  },
  resolve: {
    alias: {
      'https://unpkg.com/wavesurfer.js@7/dist/wavesurfer.esm.js': 'wavesurfer.js',
    },
  },
});
