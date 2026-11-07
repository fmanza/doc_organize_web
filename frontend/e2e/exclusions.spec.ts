import { expect, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, createProject, login } from './helpers';

// web 1.4.0 (doc_organize 1.3.0, G41): subcarpetas excluidas del escaneo con el explorador de la pantalla «Escanear».
// Origen: la raíz de /mnt/e2e/proyectos (2024 con factura.txt y nota.html; duplicados con dos actas, del CI). Al excluir
// «duplicados», el escaneo real solo encuentra los 2 documentos de 2024.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

test('excluye una subcarpeta desde el explorador y el escaneo no la recorre', async ({ page }) => {
  test.setTimeout(300_000);
  const project = `Exclusiones ${Date.now()}`;
  await login(page);
  const id = await createProject(page, project, ['']);

  await page.goto(`/projects/${id}/scan`);
  await page.getByRole('button', { name: 'Excluir subcarpetas de /' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByText('Ninguna: se escanea toda la carpeta.')).toBeVisible();
  await dialog.getByRole('checkbox', { name: 'Excluir duplicados del escaneo' }).check();
  await expect(dialog.getByText('Excluida').first()).toBeVisible();
  await dialog.getByRole('button', { name: 'Guardar' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText('1 subcarpeta excluida')).toBeVisible();

  await page.getByRole('button', { name: 'Escanear todas las carpetas' }).click();
  await expect(page.getByRole('heading', { name: 'Escaneo' })).toBeVisible();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 180_000 });
  const found = page
    .locator('dt', { hasText: /^Documentos encontrados$/ })
    .locator('xpath=following-sibling::dd[1]');
  await expect(found).toHaveText('2');
  await expect(page.getByText('«(raíz)»: 1 subcarpeta excluida.')).toBeVisible();

  // Quitar la exclusión avisa de que lo borrado por un «forzar» se volvería a convertir.
  await page.goto(`/projects/${id}/scan`);
  await page.getByRole('button', { name: 'Excluir subcarpetas de /' }).click();
  await expect(dialog.getByRole('checkbox', { name: 'Excluir duplicados del escaneo' })).toBeChecked();
  await dialog.getByRole('button', { name: 'Dejar de excluir /duplicados' }).click();
  await expect(dialog.getByText('Lo que dejes de excluir vuelve al escaneo')).toBeVisible();
  await dialog.getByRole('button', { name: 'Guardar' }).click();
  await expect(dialog).toBeHidden();
  await expect(page.getByText('1 subcarpeta excluida')).toBeHidden();
});
