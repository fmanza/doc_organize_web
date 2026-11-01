import { expect, type Page } from '@playwright/test';

// Utilidades comunes de los E2E de proyectos y escaneo. Requieren el admin de los E2E y `web` + `worker` levantados con
// docker-compose.e2e.yml: /mnt/e2e/proyectos/2024 (solo lectura) como origen y /mnt/e2e-out (escritura) como destino.
// Los nombres no empiezan por «E2E» para que locations.spec.ts no intente borrar estas ubicaciones (409).
export const ADMIN_USER = process.env.DOW_E2E_ADMIN_USER;
export const ADMIN_PASSWORD = process.env.DOW_E2E_ADMIN_PASSWORD;
export const SOURCE = 'Proyectos E2E origen';
export const DESTINATION = 'Proyectos E2E salidas';

export async function login(page: Page) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(ADMIN_USER ?? '');
  await page.getByLabel('Contraseña').fill(ADMIN_PASSWORD ?? '');
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page.getByText('Servicio operativo')).toBeVisible();
}

/** Registra la ubicación si no existe (los E2E se pueden repetir sobre el mismo volumen `data`). */
export async function ensureLocation(
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

export async function choose(page: Page, label: RegExp, option: string) {
  await page.getByRole('combobox', { name: label }).click();
  await page.getByRole('option', { name: option }).click();
}

export async function locationId(page: Page, name: string): Promise<number> {
  const response = await page.request.get('/api/v1/locations?limit=200');
  const body = (await response.json()) as { items: { id: number; name: string }[] };
  const found = body.items.find((item) => item.name === name);
  if (!found) {
    throw new Error(`Ubicación ${name} no encontrada`);
  }
  return found.id;
}

/** Cabecera CSRF para llamadas directas a la API desde el test. */
export async function csrf(page: Page): Promise<Record<string, string>> {
  const cookie = (await page.context().cookies()).find((c) => c.name.endsWith('dow_csrf'));
  return { 'X-CSRF-Token': cookie?.value ?? '' };
}

/** Crea por la API un proyecto con origen `2024` y carpeta de salidas nueva `name`; devuelve su id. */
export async function createProject(page: Page, name: string): Promise<number> {
  await ensureLocation(page, SOURCE, [/^e2e$/, /proyectos/], { usage: 'Origen', rw: false });
  await ensureLocation(page, DESTINATION, [/^e2e-out$/], { usage: 'Destino', rw: true });
  const response = await page.request.post('/api/v1/projects', {
    headers: await csrf(page),
    data: {
      name,
      source_location_id: await locationId(page, SOURCE),
      source_subpaths: ['2024'],
      destination_location_id: await locationId(page, DESTINATION),
      destination_parent: '',
      new_folder: name,
    },
  });
  expect(response.status()).toBe(201);
  return ((await response.json()) as { id: number }).id;
}
