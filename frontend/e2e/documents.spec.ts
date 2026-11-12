import { expect, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, createProject, login } from './helpers';

// Fase 5 con el worker de compose: escanear los documentos sintéticos de /mnt/e2e/proyectos/2024 (factura.txt y
// nota.html, que crea el CI), verlos en «Documentos», abrir el Markdown, buscar en el contenido y exportar un Excel.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

test('documentos: lista, visor, búsqueda de texto completo y exportación', async ({ page }) => {
  test.setTimeout(300_000);
  const project = `Documentos ${Date.now()}`;
  await login(page);
  const id = await createProject(page, project);

  await page.goto(`/projects/${id}/scan`);
  await page.getByRole('button', { name: 'Escanear todas las carpetas' }).click();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 180_000 });

  // Lista de la caché, con rutas relativas a la carpeta de origen.
  await page.goto(`/projects/${id}`);
  await page.getByRole('link', { name: 'Documentos' }).click();
  await expect(page.getByText('2 documentos.')).toBeVisible();
  await expect(page.getByRole('listitem').filter({ hasText: 'nota.html' })).toBeVisible();

  // Visor del Markdown convertido.
  await page.getByRole('link', { name: 'Ver nota.html' }).click();
  await expect(page.getByRole('heading', { name: 'Nota sintética' })).toBeVisible();
  await page.getByRole('tab', { name: 'JSON' }).click();
  // doc_organize escribe la ruta absoluta del origen (G23): el visor la muestra relativa a su carpeta.
  await expect(page.locator('pre')).toContainText('"source_path": "2024/nota.html"');
  await expect(page.locator('pre')).not.toContainText('/mnt');

  // La búsqueda de texto completo se preparó al terminar el escaneo.
  await page.goto(`/projects/${id}/search`);
  await page.getByRole('textbox', { name: 'Buscar', exact: true }).fill('sintetica');
  await expect(page.getByRole('link', { name: 'Nota sintética' })).toBeVisible();

  // Exportación como ejecución, con el fichero para descargar.
  await page.goto(`/projects/${id}/documents`);
  await page.getByRole('button', { name: 'Excel de la caché' }).click();
  await expect(page.getByRole('heading', { name: 'Exportar Excel' })).toBeVisible();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 120_000 });
  const download = page.waitForEvent('download');
  await page.getByRole('link', { name: /-cache\.xlsx/ }).click();
  expect((await download).suggestedFilename()).toMatch(/-cache\.xlsx$/);
});
