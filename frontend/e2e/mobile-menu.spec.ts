import { expect, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, login } from './helpers';

// 3.0: el menú en pantallas estrechas. jsdom (31+) evalúa las media queries con un ancho fijo de 1024 px, así que en
// Vitest el botón (`hiddenFrom="sm"`) queda oculto: que se vea, abra y pliegue el menú se prueba aquí, con un móvil.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');
test.use({ viewport: { width: 375, height: 800 } });

test('en un móvil, el botón abre el menú y se pliega al navegar', async ({ page }) => {
  await login(page);

  const open = page.getByRole('button', { name: 'Abrir el menú' });
  await expect(open).toBeVisible();
  await expect(open).toHaveAttribute('aria-expanded', 'false');
  await expect(open).toHaveAttribute('aria-controls', 'app-navbar');

  await open.click();
  await expect(page.getByRole('button', { name: 'Cerrar el menú' })).toHaveAttribute('aria-expanded', 'true');
  const navigation = page.getByRole('navigation', { name: 'Navegación principal' });
  await expect(navigation).toBeVisible();

  await navigation.getByRole('link', { name: 'Ejecuciones' }).click();
  await expect(page).toHaveURL(/\/runs/);
  // Mantine pliega el menú desplazándolo fuera de la pantalla (sigue en el DOM): el estado lo da `aria-expanded`.
  await expect(page.getByRole('button', { name: 'Abrir el menú' })).toHaveAttribute('aria-expanded', 'false');
});
