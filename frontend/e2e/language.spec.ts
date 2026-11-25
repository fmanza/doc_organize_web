import { expect, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, login } from './helpers';
import { api } from './w9';

// 2.6: idioma por usuario. Con un usuario propio, como el tema: el admin de los E2E lo comparten los workers.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

const PASSWORD = 'frase-de-paso-del-idioma-e2e';

test('el idioma elegido se guarda en el usuario, cambia la interfaz y se aplica al volver', async ({
  page,
  browser,
}) => {
  await login(page);
  const username = `idioma${Date.now()}`;
  const created = await api(page, 'POST', '/api/v1/users', {
    username,
    display_name: `Idioma ${username}`,
    password: PASSWORD,
    role_id: null,
    is_instance_admin: false,
  });
  expect(created.status()).toBe(201);

  const context = await browser.newContext({ locale: 'es-ES' });
  const own = await context.newPage();
  await own.goto('/login');
  await own.getByLabel('Usuario').fill(username);
  await own.getByLabel('Contraseña').fill(PASSWORD);
  await own.getByRole('button', { name: 'Iniciar sesión' }).click();

  await own.getByRole('button', { name: `Menú de usuario de Idioma ${username}` }).click();
  await own.getByRole('group', { name: 'Idioma' }).getByRole('menuitem', { name: 'English' }).click();
  await expect(own.getByRole('group', { name: 'Language' })).toBeVisible();
  await expect(own.locator('html')).toHaveAttribute('lang', 'en');

  // Sin copia local (otro navegador) lo trae el servidor con /me.
  await own.evaluate('window.localStorage.clear()');
  await own.reload();
  await expect(own.getByRole('button', { name: `User menu for Idioma ${username}` })).toBeVisible();

  // Al cerrar sesión, el inicio de sesión sigue en el último idioma usado en este navegador.
  await own.getByRole('button', { name: `User menu for Idioma ${username}` }).click();
  await own.getByRole('menuitem', { name: 'Sign out' }).click();
  await expect(own.locator('html')).toHaveAttribute('lang', 'en');
  await context.close();
});
