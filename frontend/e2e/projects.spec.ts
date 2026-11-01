import { expect, type Page, test } from '@playwright/test';

// Requiere el admin de los E2E, `web` + `worker` levantados con docker-compose.e2e.yml: /mnt/e2e/proyectos/2024
// (solo lectura) como origen y /mnt/e2e-out (escritura) como destino. Los nombres no empiezan por «E2E» para que
// locations.spec.ts no intente borrar estas ubicaciones (un proyecto las usa: 409).
const ADMIN_USER = process.env.DOW_E2E_ADMIN_USER;
const ADMIN_PASSWORD = process.env.DOW_E2E_ADMIN_PASSWORD;
const SOURCE = 'Proyectos E2E origen';
const DESTINATION = 'Proyectos E2E salidas';

test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(ADMIN_USER ?? '');
  await page.getByLabel('Contraseña').fill(ADMIN_PASSWORD ?? '');
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page.getByText('Servicio operativo')).toBeVisible();
}

/** Registra la ubicación si no existe (los E2E se pueden repetir sobre el mismo volumen `data`). */
async function ensureLocation(
  page: Page,
  name: string,
  folder: RegExp[],
  options: { usage: string; rw: boolean },
) {
  await page.getByRole('link', { name: 'Ubicaciones', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Ubicaciones' })).toBeVisible();
  await expect(
    page
      .getByRole('columnheader', { name: 'Última comprobación' })
      .or(page.getByText(/^Todavía no hay ubicaciones/)),
  ).toBeVisible();
  if (await page.getByRole('link', { name, exact: true }).count()) {
    return;
  }
  await page.getByRole('button', { name: 'Nueva ubicación' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: /^Nombre/ }).fill(name);
  for (const part of folder) {
    await dialog.getByRole('button', { name: part }).click();
  }
  await dialog.getByRole('button', { name: 'Elegir esta carpeta' }).click();
  await dialog.getByText(options.usage, { exact: true }).click();
  if (options.rw) {
    await dialog.getByText('Lectura y escritura', { exact: true }).click();
  }
  await dialog.getByRole('button', { name: 'Registrar ubicación' }).click();
  await expect(page.getByRole('row', { name: new RegExp(name) }).getByText('Disponible')).toBeVisible();
}

async function choose(page: Page, label: RegExp, option: string) {
  await page.getByRole('combobox', { name: label }).click();
  await page.getByRole('option', { name: option }).click();
}

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
  await ensureLocation(page, SOURCE, [/^e2e$/, /proyectos/], { usage: 'Origen', rw: false });
  await ensureLocation(page, DESTINATION, [/^e2e-out$/], { usage: 'Destino', rw: true });
  const response = await page.request.post('/api/v1/projects', {
    headers: {
      'X-CSRF-Token': (await context.cookies()).find((c) => c.name.endsWith('dow_csrf'))?.value ?? '',
    },
    data: {
      name: project,
      source_location_id: await locationId(page, SOURCE),
      source_subpaths: ['2024'],
      destination_location_id: await locationId(page, DESTINATION),
      destination_parent: '',
      new_folder: project,
    },
  });
  expect(response.status()).toBe(201);
  const { id } = (await response.json()) as { id: number };
  // Un noop largo (60 pasos de 1 s) para que dé tiempo a cancelarlo.
  const run = await page.request.post(`/api/v1/projects/${id}/runs`, {
    headers: {
      'X-CSRF-Token': (await context.cookies()).find((c) => c.name.endsWith('dow_csrf'))?.value ?? '',
    },
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

async function locationId(page: Page, name: string): Promise<number> {
  const response = await page.request.get('/api/v1/locations?limit=200');
  const body = (await response.json()) as { items: { id: number; name: string }[] };
  const found = body.items.find((item) => item.name === name);
  if (!found) {
    throw new Error(`Ubicación ${name} no encontrada`);
  }
  return found.id;
}
