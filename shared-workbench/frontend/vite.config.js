import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const proxy = {
  '/api': 'http://127.0.0.1:8061',
  '/electrical-api': {
    target: process.env.ELECTRICAL_PROXY_TARGET || 'http://127.0.0.1:8066',
    rewrite: (path) => path.replace(/^\/electrical-api/, ''),
  },
};

export default defineConfig({
  server: { proxy },
  build: {
    rollupOptions: {
      input: {
        workbench: fileURLToPath(new URL('./index.html', import.meta.url)),
        electrical: fileURLToPath(new URL('./electrical.html', import.meta.url)),
      },
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/zrender/') || id.includes('/node_modules/tslib/')) return 'chart-renderer';
          if (id.includes('/node_modules/echarts/')) return 'charts';
        },
      },
    },
  },
  preview: { proxy },
});
