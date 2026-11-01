import { expect, type Page, test } from '@playwright/test';

// Requiere el admin de los E2E (DOW_E2E_ADMIN_USER / DOW_E2E_ADMIN_PASSWORD) y la carpeta de
// docker-compose.e2e.yml montada en /mnt/e2e con expedientes/{2024,2025}.
const ADMIN_USER = process.env.DOW_E2E_ADMIN_USER;
const ADMIN_PASSWORD = process.env.DOW_E2E_ADMIN_PASSWORD;

test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

async function login(page: Page, username: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contraseña').fill(password);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page.getByText('Servicio operativo')).toBeVisible();
}

test('el admin registra una ubicación y la explora', async ({ page }) => {
  const name = `E2E ${Date.now()}`;
  await login(page, ADMIN_USER ?? '', ADMIN_PASSWORD ?? '');
  await page.getByRole('link', { name: 'Ubicaciones' }).click();

  // Una ubicación por carpeta: si un E2E anterior ya registró /mnt/e2e/expedientes, se borra antes (una vez cargada
  // la lista: contar antes daría 0).
  await expect(
    page
      .getByRole('columnheader', { name: 'Última comprobación' })
      .or(page.getByText(/^Todavía no hay ubicaciones/)),
  ).toBeVisible();
  const previous = page.getByRole('button', { name: /^Borrar E2E/ });
  if (await previous.count()) {
    const existing = (await previous.first().getAttribute('aria-label'))?.replace('Borrar ', '') ?? '';
    await previous.first().click();
    await page.getByRole('dialog').getByRole('textbox').fill(existing);
    await page.getByRole('dialog').getByRole('button', { name: 'Borrar' }).click();
  }

  await page.getByRole('button', { name: 'Nueva ubicación' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: /^Nombre/ }).fill(name);
  await dialog.getByRole('button', { name: /^e2e$/ }).click();
  await dialog.getByRole('button', { name: /expedientes/ }).click();
  await dialog.getByRole('button', { name: 'Elegir esta carpeta' }).click();
  await dialog.getByRole('button', { name: 'Registrar ubicación' }).click();

  const row = page.getByRole('row', { name: new RegExp(name) });
  await expect(row.getByText('Disponible')).toBeVisible();
  await row.getByRole('link', { name }).click();
  await expect(page.getByRole('heading', { name })).toBeVisible();
  await page.getByRole('button', { name: /2024/ }).click();
  await expect(page.getByRole('button', { name: /Subir un nivel/ })).toBeVisible();
});
