import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

import pkg from './package.json' with { type: 'json' };

// En desarrollo, /api va al backend (uvicorn local o docker-compose.dev.yml en el puerto 8000).
export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rolldownOptions: {
      output: {
        // Librerías que se cargan siempre al inicio, en chunks propios: el código de la app cambia en cada versión y
        // estos no, así que el navegador los reutiliza de la caché. Solo se agrupa lo que ya carga la entrada: un
        // grupo genérico de node_modules arrastraría a la carga inicial lo que hoy es lazy.
        codeSplitting: {
          groups: [
            {
              name: 'vendor-react',
              test: /node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/,
              priority: 30,
            },
            { name: 'vendor-mantine', test: /node_modules[\\/]@mantine[\\/]/, priority: 20 },
            {
              name: 'vendor-app',
              test: /node_modules[\\/](i18next|react-i18next|@tanstack|openapi-fetch|react-hook-form|zod)[\\/]/,
              priority: 10,
            },
          ],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    css: false,
  },
});
