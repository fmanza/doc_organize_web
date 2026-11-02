import { expect, type Page, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, createProject, login } from './helpers';

// Fase 7 con el worker de compose: escanear /mnt/e2e/proyectos/2024 (documentos sintéticos del CI) → construir el
// contexto con la plantilla incluida «calidad» → abrir el sitio Zensical aislado → borrar el contexto en dos pasos.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

function resultValue(page: Page, label: string) {
  return page.locator('dt', { hasText: new RegExp(`^${label}$`) }).locator('xpath=following-sibling::dd[1]');
}

test('contexto: construir con plantilla, ver el sitio aislado y borrar', async ({ page }) => {
  test.setTimeout(420_000);
  const project = `Contexto ${Date.now()}`;
  await login(page);
  const id = await createProject(page, project, ['2024']);

  await page.goto(`/projects/${id}/scan`);
  await page.getByRole('button', { name: 'Escanear todas las carpetas' }).click();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 180_000 });

  // Construir con una plantilla incluida (dos ejes).
  await page.goto(`/projects/${id}`);
  await page.getByRole('link', { name: 'Contexto' }).click();
  await expect(page.getByText('El proyecto aún no tiene contexto.')).toBeVisible();
  await page.getByText('Plantilla', { exact: true }).first().click();
  await page.getByRole('combobox', { name: 'Plantilla' }).click();
  await page.getByRole('option', { name: /\(calidad\)$/ }).click();
  await page.getByRole('button', { name: 'Construir' }).click();
  await expect(page.getByRole('heading', { name: 'Construir contexto' })).toBeVisible();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 180_000 });
  await expect(resultValue(page, 'Sitio construido')).toHaveText('Sí');
  await page.getByRole('link', { name: 'Ver el contexto' }).click();
  await expect(page.getByText(/Contexto construido el/)).toBeVisible();

  // El sitio se carga en un iframe aislado: navega, pero no ve las cookies de la app.
  await page.getByRole('link', { name: 'Ver el sitio' }).click();
  const iframe = page.locator('iframe[title="Sitio del contexto"]');
  await expect(iframe).toHaveAttribute('sandbox', /allow-scripts/);
  await expect(iframe).not.toHaveAttribute('sandbox', /allow-same-origin/);
  const site = page.frameLocator('iframe[title="Sitio del contexto"]');
  await expect(site.locator('body')).toContainText(project, { timeout: 30_000 });
  const frame = page.frames().find((f) => f.url().includes('/site/'));
  if (!frame) throw new Error('No se cargó el iframe del sitio');
  // Como texto: el tsconfig de los E2E no incluye los tipos del DOM. En un origen opaco, leer la cookie lanza.
  const cookies = String(
    await frame.evaluate("(() => { try { return document.cookie; } catch { return 'bloqueado'; } })()"),
  );
  expect(cookies).not.toContain('dow_');

  // La URL del sitio sin el token no sirve nada.
  const src = (await iframe.getAttribute('src')) ?? '';
  const response = await page.request.get(src.replace(/\/site\/[^/]+\//, '/site/0.0.0.x/'));
  expect(response.status()).toBe(404);
  expect(response.headers()['content-security-policy']).toContain('sandbox');

  // Borrar: vista previa y nombre del proyecto.
  await page.goto(`/projects/${id}/context`);
  await page.getByRole('button', { name: 'Borrar contexto' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Ver vista previa' }).click();
  await dialog.getByRole('textbox', { name: /Escribe/ }).fill(project);
  await dialog.getByRole('button', { name: 'Borrar contexto' }).click();
  await expect(page.getByRole('heading', { name: 'Borrar contexto' })).toBeVisible();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 120_000 });
  await page.goto(`/projects/${id}/context`);
  await expect(page.getByText('El proyecto aún no tiene contexto.')).toBeVisible();
});
