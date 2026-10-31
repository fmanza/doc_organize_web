import { expect, test } from '@playwright/test';

test('sin sesión, la portada redirige al login', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveURL(/\/login\?next=%2F$/);
  await expect(page.getByRole('heading', { name: 'doc_organize web' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Iniciar sesión' })).toBeVisible();
});

test('la API de salud sigue siendo pública', async ({ request }) => {
  const response = await request.get('/api/health');

  expect(response.status()).toBe(200);
  expect((await response.json()).status).toBe('ok');
});
