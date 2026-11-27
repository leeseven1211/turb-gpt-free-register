import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: '../webui/static/task-center',
    emptyOutDir: false,
    lib: {
      entry: {
        'task-center': fileURLToPath(new URL('./src/main.ts', import.meta.url)),
        codex: fileURLToPath(new URL('./src/codex.ts', import.meta.url)),
        accounts: fileURLToPath(new URL('./src/accounts.ts', import.meta.url)),
        sales: fileURLToPath(new URL('./src/sales.ts', import.meta.url)),
        bulk: fileURLToPath(new URL('./src/bulk.ts', import.meta.url)),
        config: fileURLToPath(new URL('./src/config.ts', import.meta.url)),
        email: fileURLToPath(new URL('./src/email.ts', import.meta.url)),
        proxy: fileURLToPath(new URL('./src/proxy.ts', import.meta.url)),
        dashboard: fileURLToPath(new URL('./src/dashboard.ts', import.meta.url)),
        registration: fileURLToPath(new URL('./src/registration.ts', import.meta.url)),
        extract: fileURLToPath(new URL('./src/extract.ts', import.meta.url)),
        teams: fileURLToPath(new URL('./src/teams.ts', import.meta.url)),
      },
      formats: ['es'],
      fileName: (_format, name) => `${name}.js`,
      cssFileName: 'task-center',
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
