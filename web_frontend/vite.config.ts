import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const apiBase = env.VITE_API_BASE || '/tools/watermark';

  return {
    plugins: [react()],
    base: `${apiBase}/`,
    server: {
      proxy: {
        '/api': 'http://127.0.0.1:2189',
      },
    },
  };
});
