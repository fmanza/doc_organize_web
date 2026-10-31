import { expect, test } from '@playwright/test';

test('la portada carga y muestra el estado de la API', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByRole('heading', { name: 'doc_organize web' })).toBeVisible();
  await expect(page.getByText('Servicio operativo')).toBeVisible();
});

test('una ruta del cliente desconocida muestra la página 404 de la SPA', async ({ page }) => {
  await page.goto('/no-existe');

  await expect(page.getByText('Página no encontrada')).toBeVisible();
});
