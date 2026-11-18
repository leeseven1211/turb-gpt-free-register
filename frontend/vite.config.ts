import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: '../webui/static/dashboard',
    emptyOutDir: false,
    lib: {
      entry: fileURLToPath(new URL('./src/dashboard.ts', import.meta.url)),
      formats: ['es'],
      fileName: () => 'dashboard.js',
      cssFileName: 'dashboard',
    },
    sourcemap: false,
  },
  server: {
    host: '127.0.0.1',
    proxy: { '/api': 'http://127.0.0.1:8000', '/static': 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.ts'],
    restoreMocks: true,
  },
});
