import { expect, test, type Page } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, login } from './helpers';
import { api } from './w9';

// 2.3: tema por usuario. Con un usuario propio: el admin de los E2E lo comparten los workers en paralelo, y cambiarle
// el tema lo cambiaría también en los demás tests (y en las siguientes ejecuciones si este fallara a medias).
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

const PASSWORD = 'frase-de-paso-del-tema-e2e';
const scheme = (page: Page) => page.locator('html').getAttribute('data-mantine-color-scheme');

async function loginAs(page: Page, username: string) {
  await page.goto('/login');
  await page.getByLabel('Usuario').fill(username);
  await page.getByLabel('Contraseña').fill(PASSWORD);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page.getByRole('button', { name: `Menú de usuario de Tema ${username}` })).toBeVisible();
}

test('el tema elegido se guarda en el usuario y se aplica al volver', async ({ page, browser }) => {
  await login(page);
  const username = `tema${Date.now()}`;
  const created = await api(page, 'POST', '/api/v1/users', {
    username,
    display_name: `Tema ${username}`,
    password: PASSWORD,
    role_id: null,
    is_instance_admin: false,
  });
  expect(created.status()).toBe(201);

  const context = await browser.newContext({ colorScheme: 'light' });
  const own = await context.newPage();
  await loginAs(own, username);
  expect(await scheme(own)).toBe('light'); // «Como el sistema», y el sistema del navegador es claro

  await own.getByRole('button', { name: `Menú de usuario de Tema ${username}` }).click();
  const dark = own.getByRole('group', { name: 'Tema' }).getByRole('menuitem', { name: 'Oscuro' });
  await dark.click();
  await expect(dark).toHaveAttribute('aria-current', 'true');
  await expect.poll(() => scheme(own)).toBe('dark');

  // Al recargar, el script previo a React lo aplica antes de pintar (copia local)…
  await own.reload();
  expect(await scheme(own)).toBe('dark');
  // …y sin copia local (otro navegador) lo trae el servidor con /me.
  await own.evaluate(() => window.localStorage.clear());
  await own.reload();
  await expect.poll(() => scheme(own)).toBe('dark');

  // Otro usuario en el mismo navegador ve el suyo: el admin sigue en «Como el sistema».
  await own.getByRole('button', { name: `Menú de usuario de Tema ${username}` }).click();
  await own.getByRole('menuitem', { name: 'Cerrar sesión' }).click();
  await own.getByLabel('Usuario').fill(ADMIN_USER ?? '');
  await own.getByLabel('Contraseña').fill(ADMIN_PASSWORD ?? '');
  await own.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(own.getByText('Servicio operativo')).toBeVisible();
  await expect.poll(() => scheme(own)).toBe('light');
  await context.close();
});
