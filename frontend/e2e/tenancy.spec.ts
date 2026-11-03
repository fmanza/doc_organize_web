import { expect, type Page, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, createProject, login } from './helpers';

// Fase 9: el admin de instancia crea un tenant, actúa en él con el selector y da de alta a una usuaria; esa usuaria no
// ve nada del tenant predeterminado (ni proyectos ni ubicaciones), y el admin vuelve a su tenant.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

async function loginAs(page: Page, username: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contraseña').fill(password);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page.getByRole('button', { name: /Menú de usuario/ })).toBeVisible();
}

test('tenants: alta, selector y aislamiento entre tenants', async ({ page, browser }) => {
  test.setTimeout(180_000);
  const stamp = Date.now();
  const slug = `e2e-${stamp}`;
  const tenantName = `Tenant ${stamp}`;
  const username = `e2e-t-${stamp}`;
  const password = 'frase-de-paso-tenant-1';
  await login(page);
  const projectId = await createProject(page, `Aislado ${stamp}`, ['2024']);

  await page.goto('/admin/tenants');
  await page.getByRole('textbox', { name: /Identificador/ }).fill(slug);
  await page.getByRole('textbox', { name: 'Nombre', exact: true }).fill(tenantName);
  await page.getByRole('button', { name: 'Crear tenant' }).click();
  await page.getByRole('button', { name: `Actuar en ${tenantName}` }).click();
  await expect(page.getByRole('combobox', { name: 'Tenant activo' })).toHaveValue(tenantName);

  // En el tenant nuevo no hay proyectos ni ubicaciones del predeterminado.
  await page.goto('/projects');
  await expect(page.getByText(`Aislado ${stamp}`)).toHaveCount(0);
  await page.goto('/admin/users');
  await page.getByRole('button', { name: 'Nuevo usuario' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: /^Usuario/ }).fill(username);
  await dialog.getByRole('textbox', { name: /Nombre visible/ }).fill('Usuaria del tenant');
  await dialog.getByLabel(/^Contraseña/).fill(password);
  await dialog.getByRole('button', { name: 'Crear usuario' }).click();
  await expect(page.getByRole('cell', { name: username, exact: true })).toBeVisible();

  const other = await browser.newPage();
  await loginAs(other, username, password);
  await expect(other.getByLabel(`Tenant: ${tenantName}`)).toBeVisible();
  const project = await other.request.get(`/api/v1/projects/${projectId}`);
  expect(project.status()).toBe(404);
  const locations = (await (await other.request.get('/api/v1/locations')).json()) as { total: number };
  expect(locations.total).toBe(0);
  await other.goto('/admin/users');
  await expect(other.getByText('Sin permiso')).toBeVisible();
  await other.close();

  // El admin vuelve a su tenant y ve otra vez su proyecto.
  await page.goto('/admin/tenants');
  await page.getByRole('button', { name: 'Actuar en Predeterminado' }).click();
  await expect(page.getByRole('combobox', { name: 'Tenant activo' })).toHaveValue('Predeterminado');
  const back = await page.request.get(`/api/v1/projects/${projectId}`);
  expect(back.status()).toBe(200);
});
