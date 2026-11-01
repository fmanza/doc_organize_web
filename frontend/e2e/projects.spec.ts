import { expect, test } from '@playwright/test';

import {
  ADMIN_PASSWORD,
  ADMIN_USER,
  choose,
  createProject,
  csrf,
  DESTINATION,
  ensureLocation,
  login,
  SOURCE,
} from './helpers';

test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

test('crea un proyecto, prueba el motor y sigue el progreso en vivo', async ({ page }) => {
  const project = `Proyecto ${Date.now()}`;
  await login(page);
  await ensureLocation(page, SOURCE, [/^e2e$/, /proyectos/], { usage: 'Origen', rw: false });
  await ensureLocation(page, DESTINATION, [/^e2e-out$/], { usage: 'Destino', rw: true });

  await page.getByRole('link', { name: 'Proyectos', exact: true }).click();
  await page.getByRole('button', { name: 'Nuevo proyecto' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: /^Nombre/ }).fill(project);
  await choose(page, /^Ubicación de origen/, SOURCE);
  await dialog.getByRole('button', { name: /2024/ }).click();
  await dialog.getByRole('button', { name: 'Elegir esta carpeta' }).first().click();
  await choose(page, /^Ubicación de destino/, DESTINATION);
  await dialog.getByRole('textbox', { name: /Nombre de la carpeta nueva/ }).fill(project);
  await dialog.getByRole('button', { name: 'Crear proyecto' }).click();

  await expect(page.getByRole('heading', { name: project })).toBeVisible();
  await page.getByRole('button', { name: 'Probar el motor' }).click();

  // Detalle del run: progreso por SSE y fin con artefactos.
  await expect(page.getByRole('heading', { name: 'Prueba del motor' })).toBeVisible();
  await expect(page.getByText(/de 5$/)).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 60_000 });
  await expect(page.getByRole('link', { name: 'noop.txt' })).toBeVisible();

  await page.getByRole('link', { name: 'Ejecuciones', exact: true }).click();
  await expect(page.getByRole('row', { name: new RegExp(project) }).first()).toBeVisible();
});

test('una ejecución se cancela aunque se cierre la página', async ({ page, context }) => {
  const project = `Cancelar ${Date.now()}`;
  await login(page);
  const id = await createProject(page, project);
  // Un noop largo (60 pasos de 1 s) para que dé tiempo a cancelarlo.
  const run = await page.request.post(`/api/v1/projects/${id}/runs`, {
    headers: await csrf(page),
    data: { operation: 'noop', steps: 60, step_seconds: 1, fail_at_step: null },
  });
  expect(run.status()).toBe(202);
  const url = `/runs/${((await run.json()) as { id: string }).id}`;
  await page.goto(url);
  await expect(page.getByText('En marcha')).toBeVisible({ timeout: 30_000 });

  // La pestaña se cierra: el run sigue en el worker.
  await page.close();
  const again = await context.newPage();
  await again.goto(url);
  await again.getByRole('button', { name: 'Cancelar ejecución' }).click();
  await again.getByRole('dialog').getByRole('button', { name: 'Cancelar ejecución' }).click();
  await expect(again.getByText('Cancelada')).toBeVisible({ timeout: 30_000 });
});
