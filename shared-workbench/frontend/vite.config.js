import { defineConfig } from 'vite';

export default defineConfig({
  server: { proxy: { '/api': 'http://127.0.0.1:8061' } },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('/node_modules/zrender/') || id.includes('/node_modules/tslib/')) return 'chart-renderer';
          if (id.includes('/node_modules/echarts/')) return 'charts';
        },
      },
    },
  },
  preview: { proxy: { '/api': 'http://127.0.0.1:8061' } },
});
