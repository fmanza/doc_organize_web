import { expect, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, login } from './helpers';

// web 1.2.0: listados con orden y búsqueda en la URL, Roles como Usuarios y borrado de auditoría por fechas.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

test('ordenar y buscar usuarios queda en la URL', async ({ page }) => {
  await login(page);
  await page.goto('/admin/users');

  await page.getByRole('button', { name: /^Alta/ }).click();
  await page.getByRole('button', { name: /^Alta/ }).click();
  await expect(page).toHaveURL(/sort=created_at/);
  await expect(page).toHaveURL(/order=desc/);
  await expect(page.getByRole('columnheader', { name: /^Alta/ })).toHaveAttribute('aria-sort', 'descending');

  await page.getByRole('textbox', { name: 'Buscar por usuario o nombre' }).fill(ADMIN_USER ?? '');
  await expect(page).toHaveURL(new RegExp(`q=${ADMIN_USER ?? ''}`));
  // En la pila E2E el nombre visible del admin es su usuario: dos celdas con el mismo texto en la fila.
  await expect(page.getByRole('cell', { name: ADMIN_USER ?? '', exact: true }).first()).toBeVisible();
});

test('Roles: listado con los predeterminados y su vista de solo lectura', async ({ page }) => {
  await login(page);
  await page.goto('/admin/roles');

  const admin = page
    .getByRole('row')
    .filter({ has: page.getByRole('cell', { name: 'Administrador', exact: true }) });
  await expect(admin.getByText('Predeterminado')).toBeVisible();
  await admin.getByRole('button', { name: 'Ver el rol Administrador' }).click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('checkbox', { name: /Gestionar usuarios/ })).toBeDisabled();
  await dialog.getByRole('button', { name: 'Cerrar' }).click();
  await expect(page.getByRole('button', { name: 'Nuevo rol' })).toBeVisible();
});

test('borrar auditoría por fechas comprueba antes (rango antiguo, sin entradas)', async ({ page }) => {
  await login(page);
  await page.goto('/admin/audit');

  await page.getByRole('button', { name: 'Eliminar por fechas' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Desde (incluido)').fill('2000-01-01');
  await dialog.getByLabel(/Hasta \(sin incluir\)/).fill('2000-02-01');
  await dialog.getByRole('button', { name: 'Comprobar' }).click();
  await expect(dialog.getByText('No hay entradas en ese rango.')).toBeVisible();
});
