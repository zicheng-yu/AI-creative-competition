import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const proxy = {
  '/api': 'http://127.0.0.1:8061',
  '/sucompute-api': {
    target: process.env.SUCOMPUTE_PROXY_TARGET || 'http://127.0.0.1:8000',
    rewrite: (path) => path.replace(/^\/sucompute-api/, ''),
  },
};
const here = (path) => fileURLToPath(new URL(path, import.meta.url));

export default defineConfig({
  server: { proxy },
  build: {
    rollupOptions: {
      input: { workbench: here('./index.html'), sucompute: here('./sucompute.html') },
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
