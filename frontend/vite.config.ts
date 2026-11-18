import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig(({ mode }) => {
  const page = ['proxy', 'extractStats'].includes(mode) ? mode : 'dashboard';
  return {
    plugins: [vue()],
    define: { 'process.env.NODE_ENV': JSON.stringify('production') },
    build: {
      outDir: `../webui/static/${page}`,
      emptyOutDir: false,
      lib: {
        entry: fileURLToPath(new URL(`./src/${page}.ts`, import.meta.url)),
        formats: ['es'],
        fileName: () => `${page}.js`,
        cssFileName: page,
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
  };
});
