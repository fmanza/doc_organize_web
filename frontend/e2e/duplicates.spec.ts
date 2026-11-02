import { expect, type Page, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, createProject, login } from './helpers';

// Fase 6 con el worker de compose: /mnt/e2e/proyectos/duplicados tiene dos actas sintéticas idénticas (las crea el CI).
// Escanear → buscar duplicados → revisar el grupo → copiar (dos pasos) → informe. Copiar no toca el origen (de solo
// lectura), así que el E2E se puede repetir.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

function resultValue(page: Page, label: string) {
  return page.locator('dt', { hasText: new RegExp(`^${label}$`) }).locator('xpath=following-sibling::dd[1]');
}

test('duplicados: buscar, revisar y copiar en dos pasos', async ({ page }) => {
  test.setTimeout(300_000);
  const project = `Duplicados ${Date.now()}`;
  await login(page);
  const id = await createProject(page, project, ['duplicados']);

  await page.goto(`/projects/${id}/scan`);
  await page.getByRole('button', { name: 'Escanear todas las carpetas' }).click();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 180_000 });

  // Buscar no toca ficheros: la ejecución lleva al resolutor.
  await page.goto(`/projects/${id}`);
  await page.getByRole('link', { name: 'Duplicados' }).click();
  await page.getByRole('button', { name: 'Buscar' }).click();
  await expect(page.getByRole('heading', { name: 'Buscar duplicados' })).toBeVisible();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 120_000 });
  await expect(resultValue(page, 'Grupos de duplicados exactos')).toHaveText('1');
  await page.getByRole('link', { name: 'Revisar los grupos de duplicados' }).click();

  // El grupo, lado a lado, con el documento que se conserva marcado.
  await expect(page.getByText('duplicados/acta.txt')).toBeVisible();
  await expect(page.getByText('duplicados/acta copia.txt')).toBeVisible();
  await expect(page.getByRole('checkbox', { name: 'Aplicar el grupo 1 (acta.txt)' })).toBeChecked();

  // Aplicar: vista previa, nombre del proyecto y copia.
  await page.getByRole('button', { name: 'Aplicar…' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('radio', { name: /^Mover/ })).toBeDisabled();
  await dialog.getByRole('button', { name: 'Calcular qué se aplicaría' }).click();
  await dialog.getByRole('textbox', { name: /Escribe/ }).fill(project);
  await dialog.getByRole('button', { name: 'Copiar' }).click();
  await expect(page.getByRole('heading', { name: 'Aplicar duplicados' })).toBeVisible();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 120_000 });
  await expect(resultValue(page, 'Ficheros aplicados')).toHaveText('1');

  await page.goto(`/projects/${id}/duplicates`);
  await expect(page.getByText(/Ya se aplicaron duplicados/)).toBeVisible();
});
