/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BACKEND_URL: string;
  // tambahkan variabel .env lainnya di sini nanti kalau ada
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}