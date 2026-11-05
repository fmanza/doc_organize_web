import { expect, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, createProject, login } from './helpers';

// Fase 10: menú del proyecto con Duplicados primero, recursos del worker en Ajustes y cabeceras (el aviso al terminar
// una ejecución se comprueba en scan.spec.ts, sin lanzar ejecuciones de más: el tope es de 5 por usuario).
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

test('el proyecto abierto pone Duplicados el primero', async ({ page }) => {
  await login(page);
  const id = await createProject(page, `Menú ${Date.now()}`);

  await page.goto(`/projects/${id}`);
  const nav = page.getByRole('navigation', { name: 'Navegación principal' });
  await expect(nav.getByRole('link', { name: 'Duplicados' })).toBeVisible();
  const links = await nav.getByRole('link').allTextContents();
  const start = links.indexOf('Proyectos') + 1;
  expect(links.slice(start, start + 4)).toEqual(['Duplicados', 'Escaneo', 'Documentos', 'Contexto']);
});

test('Ajustes enseña la memoria de cada worker', async ({ page }) => {
  await login(page);
  await page.goto('/admin/settings');

  await expect(page.getByRole('columnheader', { name: 'Memoria' })).toBeVisible();
  await expect(page.getByText(/^Pico .+ de .+$/).first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText(/^Escaneo en tramos de \d+ documentos?$/).first()).toBeVisible();
});

test('la API no se guarda en cachés y no acepta cuerpos gigantes', async ({ request }) => {
  const health = await request.get('/api/health');
  expect(health.headers()['cache-control']).toBe('no-store');

  const big = await request.post('/api/v1/auth/login', {
    data: { username: 'x', password: 'y'.repeat(17 * 1024 * 1024) },
  });
  expect(big.status()).toBe(413);
});
