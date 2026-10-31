import { expect, type Page, test } from '@playwright/test';

// Requiere un admin creado antes con el CLI:
//   docker compose exec web python -m app.cli create-admin --username e2e-admin
// y sus credenciales en DOW_E2E_ADMIN_USER / DOW_E2E_ADMIN_PASSWORD.
const ADMIN_USER = process.env.DOW_E2E_ADMIN_USER;
const ADMIN_PASSWORD = process.env.DOW_E2E_ADMIN_PASSWORD;

test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

async function login(page: Page, username: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contraseña').fill(password);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
}

test('credenciales incorrectas muestran un error genérico', async ({ page }) => {
  await login(page, ADMIN_USER ?? '', 'no-es-la-contrasena');

  await expect(page.getByRole('alert')).toContainText('Credenciales no válidas');
  await expect(page).toHaveURL(/\/login/);
});

test('el admin inicia sesión, ve la administración y cierra sesión', async ({ page, context }) => {
  await login(page, ADMIN_USER ?? '', ADMIN_PASSWORD ?? '');

  await expect(page.getByText('Servicio operativo')).toBeVisible();
  const cookies = await context.cookies();
  const session = cookies.find((cookie) => cookie.name === '__Host-dow_session');
  expect(session?.httpOnly).toBe(true);
  expect(session?.secure).toBe(true);
  expect(session?.sameSite).toBe('Lax');

  await page.getByRole('link', { name: 'Sesiones' }).click();
  await expect(page.getByRole('heading', { name: 'Sesiones activas' })).toBeVisible();
  await expect(page.getByText('Esta sesión')).toBeVisible();

  await page.getByRole('link', { name: 'Auditoría' }).click();
  await expect(page.getByRole('cell', { name: 'Inicio de sesión' }).first()).toBeVisible();

  await page.getByRole('button', { name: /Menú de usuario/ }).click();
  await page.getByRole('menuitem', { name: 'Cerrar sesión' }).click();
  await expect(page.getByRole('button', { name: 'Iniciar sesión' })).toBeVisible();

  await page.goto('/admin/users');
  await expect(page).toHaveURL(/\/login\?next=%2Fadmin%2Fusers/);
});

test('el admin crea un usuario que puede entrar pero no ve la administración', async ({ page, browser }) => {
  const username = `e2e-${Date.now()}`;
  const password = 'frase-de-paso-e2e-1234';
  await login(page, ADMIN_USER ?? '', ADMIN_PASSWORD ?? '');
  await page.getByRole('link', { name: 'Usuarios' }).click();
  await page.getByRole('button', { name: 'Nuevo usuario' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: /^Usuario/ }).fill(username);
  await dialog.getByRole('textbox', { name: /Nombre visible/ }).fill('Usuaria E2E');
  await dialog.getByLabel(/^Contraseña/).fill(password);
  await dialog.getByRole('button', { name: 'Crear usuario' }).click();
  await expect(page.getByRole('cell', { name: username, exact: true })).toBeVisible();

  const other = await browser.newPage();
  await login(other, username, password);
  await expect(other.getByRole('button', { name: /Menú de usuario de Usuaria E2E/ })).toBeVisible();
  await expect(other.getByRole('link', { name: 'Usuarios' })).toHaveCount(0);
  await other.goto('/admin/users');
  await expect(other.getByText('Sin permiso')).toBeVisible();
  await other.close();
});

test('un usuario cambia su contraseña y entra con la nueva', async ({ page, browser }) => {
  const username = `e2e-pw-${Date.now()}`;
  const first = 'frase-de-paso-inicial-1';
  const second = 'frase-de-paso-cambiada-2';
  await login(page, ADMIN_USER ?? '', ADMIN_PASSWORD ?? '');
  await page.getByRole('link', { name: 'Usuarios' }).click();
  await page.getByRole('button', { name: 'Nuevo usuario' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: /^Usuario/ }).fill(username);
  await dialog.getByRole('textbox', { name: /Nombre visible/ }).fill('Cambio E2E');
  await dialog.getByLabel(/^Contraseña/).fill(first);
  await dialog.getByRole('button', { name: 'Crear usuario' }).click();
  await expect(page.getByRole('cell', { name: username, exact: true })).toBeVisible();

  const other = await browser.newPage();
  await login(other, username, first);
  await other.getByRole('button', { name: /Menú de usuario/ }).click();
  await other.getByRole('menuitem', { name: 'Cambiar contraseña' }).click();
  await other.getByRole('textbox', { name: 'Contraseña actual', exact: true }).fill(first);
  await other.getByRole('textbox', { name: 'Contraseña nueva', exact: true }).fill(second);
  await other.getByRole('textbox', { name: 'Repite la contraseña nueva' }).fill(second);
  await other.getByRole('button', { name: 'Cambiar contraseña' }).click();
  await expect(other.getByRole('status')).toContainText('Contraseña cambiada');

  await other.getByRole('button', { name: /Menú de usuario/ }).click();
  await other.getByRole('menuitem', { name: 'Cerrar sesión' }).click();
  await login(other, username, first);
  await expect(other.getByRole('alert')).toContainText('Credenciales no válidas');
  await login(other, username, second);
  await expect(other.getByText('Servicio operativo')).toBeVisible();
  await other.close();
});
