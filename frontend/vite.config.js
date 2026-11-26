import {defineConfig} from 'vite';

export default defineConfig({
  server: {
    proxy: {
      '/api': process.env.KARTEJ_API_URL || 'http://127.0.0.1:8000',
    },
  },
});
