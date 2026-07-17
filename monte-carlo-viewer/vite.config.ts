import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Ubah defineConfig menggunakan callback function supaya bisa menerima parameter `mode`
export default defineConfig(({ mode }) => {
  // loadEnv(mode, process.cwd(), prefix)
  // process.cwd() digunakan untuk mencari posisi file .env di root directory
  // Parameter ketiga kosong ('') artinya kita mau membaca SEMUA variabel (termasuk tanpa prefix VITE_)
  const env = loadEnv(mode, process.cwd(), '');

  // Sekarang kamu bisa mengakses VITE_BACKEND_URL di sini!
  console.log("Backend URL di config:", env.VITE_BACKEND_URL);

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
        '/static': {
          target: env.VITE_BACKEND_URL as string,
          changeOrigin: true,
        }
      },
    },

    // CONTOH PENGGUNAAN 2: Menginjeksikan variabel agar bisa diakses secara global (opsional)
    define: {
      __APP_ENV__: JSON.stringify(env.APP_ENV),
    },
  };
});