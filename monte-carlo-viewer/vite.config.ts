import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ mode }) => {

  const env = loadEnv(mode, process.cwd(), '')

  console.log("Backend URL:", env.VITE_BACKEND_URL)

  return {
    plugins: [
      react(),
      tailwindcss()
    ],

    server: {
      proxy: {
        '/api': {
          target: env.VITE_BACKEND_URL as string,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },

    define: {
      __APP_ENV__: JSON.stringify(env.APP_ENV),
    },
  };
});