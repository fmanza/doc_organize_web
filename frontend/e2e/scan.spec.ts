import { expect, type Page, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, createProject, login } from './helpers';

// Escaneo real con el worker de compose sobre documentos sintéticos de /mnt/e2e/proyectos/2024 (factura.txt y
// nota.html, que crea el CI): no necesitan los modelos de Docling.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

/** Valor de un dato del resultado del run (lista `dl` de RunResult). */
function resultValue(page: Page, label: string) {
  return page.locator('dt', { hasText: new RegExp(`^${label}$`) }).locator('xpath=following-sibling::dd[1]');
}

async function scanAll(page: Page) {
  await page.getByRole('button', { name: 'Escanear todas las carpetas' }).click();
  await expect(page.getByRole('heading', { name: 'Escaneo' })).toBeVisible();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 180_000 });
}

test('escanea el origen, sigue el progreso y el segundo escaneo es incremental', async ({ page }) => {
  test.setTimeout(300_000);
  const project = `Escaneo ${Date.now()}`;
  await login(page);
  const id = await createProject(page, project);

  await page.goto(`/projects/${id}`);
  await page.getByRole('link', { name: 'Escanear' }).click();
  await expect(page.getByRole('heading', { name: `Escanear «${project}»` })).toBeVisible();
  await expect(page.getByRole('cell', { name: '/2024', exact: true })).toBeVisible();
  await scanAll(page);
  await expect(resultValue(page, 'Documentos encontrados')).toHaveText('2');
  await expect(resultValue(page, 'Convertidos')).toHaveText('2');

  // La carpeta queda marcada como escaneada y el segundo escaneo no convierte nada.
  await page.goto(`/projects/${id}/scan`);
  await expect(page.getByText('escaneada')).toBeVisible();
  await scanAll(page);
  await expect(resultValue(page, 'Sin cambios')).toHaveText('2');
  await expect(resultValue(page, 'Convertidos')).toHaveText('0');

  await page.goto(`/projects/${id}/scan-errors`);
  await expect(page.getByText('Todos los documentos se convirtieron sin errores.')).toBeVisible();
});
