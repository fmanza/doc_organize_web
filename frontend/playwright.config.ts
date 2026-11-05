import { defineConfig, devices } from '@playwright/test';

// E2E contra la aplicación ya levantada (docker compose up). URL configurable con DOW_E2E_URL.
// Primera vez: npx playwright install chromium
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  // Todos los E2E usan el mismo admin, con un tope de 5 ejecuciones activas, y el escaneo E2E va en tramos (Fase 10):
  // con más procesos a la vez, las ejecuciones se acumulan en la cola y el tope las rechaza.
  workers: 3,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.DOW_E2E_URL ?? 'http://127.0.0.1:8080',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
