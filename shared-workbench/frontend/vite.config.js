import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const here = (path) => fileURLToPath(new URL(path, import.meta.url));

const proxy = {
  '/api': 'http://127.0.0.1:8061',
  '/sucompute-api': {
    target: process.env.SUCOMPUTE_PROXY_TARGET || 'http://127.0.0.1:8000',
    rewrite: (path) => path.replace(/^\/sucompute-api/, ''),
  },
  '/electrical-api': {
    target: process.env.ELECTRICAL_PROXY_TARGET || 'http://127.0.0.1:8066',
    rewrite: (path) => path.replace(/^\/electrical-api/, ''),
  },
  '/fluvax-api': {
    target: process.env.FLUVAX_PROXY_TARGET || 'http://127.0.0.1:8765',
    rewrite: (path) => path.replace(/^\/fluvax-api/, ''),
  },
};

export default defineConfig({
  server: { proxy },
  build: {
    rollupOptions: {
      input: {
        workbench: here('./index.html'),
        sucompute: here('./sucompute.html'),
        electrical: here('./electrical.html'),
        fluvax: here('./fluvax.html'),
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
