import { expect, type Page, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, createProject, login } from './helpers';

// Fase 8 con el LiteLLM falso de docker-compose.e2e.yml (`litellm-fake`, clave `sk-e2e-fake`; nada sale a la red):
// configurar la IA → ver el uso → construir el contexto con IA → pedir un borrador de manifiesto y guardarlo.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

const FAKE_URL = 'http://litellm-fake:4000';
const FAKE_KEY = 'sk-e2e-fake';

function resultValue(page: Page, label: string) {
  return page.locator('dt', { hasText: new RegExp(`^${label}$`) }).locator('xpath=following-sibling::dd[1]');
}

async function configure(page: Page, family: string) {
  const card = page.getByRole('region', { name: family });
  await card
    .locator('input')
    .and(card.getByLabel(/URL del servicio/))
    .fill(FAKE_URL);
  await card
    .locator('input')
    .and(card.getByLabel(/Clave virtual/))
    .fill(FAKE_KEY);
  await card.getByRole('button', { name: `Guardar ${family}` }).click();
  await expect(card.getByText('Guardada: …fake')).toBeVisible();
  await expect(card.getByText('Configurada', { exact: true })).toBeVisible();
  // La clave no vuelve al navegador.
  await expect(card.locator('input').and(card.getByLabel(/Clave virtual/))).toHaveValue('');
}

test('IA: configurar, ver el uso, clasificar el contexto y pedir un borrador de manifiesto', async ({
  page,
}) => {
  test.setTimeout(420_000);
  const project = `IA ${Date.now()}`;
  await login(page);

  await page.goto('/admin/ai-settings');
  await expect(page.getByRole('heading', { name: 'Configuración IA' })).toBeVisible();
  for (const family of ['Clasificación de dominios (un eje)', 'Borrador de manifiesto', 'Uso de LiteLLM']) {
    await configure(page, family);
  }
  const settings = await page.request.get('/api/v1/admin/ai-settings');
  expect(await settings.text()).not.toContain(FAKE_KEY);

  await page.getByRole('link', { name: 'Uso de IA' }).click();
  const usage = page.getByRole('region', { name: 'LiteLLM' });
  await expect(usage.getByText(/Total:/)).toContainText('0,42');

  const id = await createProject(page, project, ['2024']);
  await page.goto(`/projects/${id}/scan`);
  await page.getByRole('button', { name: 'Escanear todas las carpetas' }).click();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 180_000 });

  // Construir con IA (dominios descubiertos: familia de un eje).
  await page.goto(`/projects/${id}/context`);
  await expect(page.getByText('El proyecto aún no tiene contexto.')).toBeVisible();
  await page.getByRole('switch', { name: /Clasificar con IA/ }).check();
  await expect(page.getByText('El contenido sale de la aplicación')).toBeVisible();
  await page.getByRole('button', { name: 'Construir' }).click();
  await expect(page.getByRole('heading', { name: 'Construir contexto' })).toBeVisible();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 180_000 });
  await expect(resultValue(page, 'Con IA')).toHaveText('Sí');
  await expect(resultValue(page, 'Errores de la IA')).toHaveText('0');

  // Borrador: se carga en el editor sin guardarse y se guarda a mano.
  await page.goto(`/projects/${id}/context`);
  await page.getByRole('button', { name: 'Pedir borrador' }).click();
  await expect(page.getByText('Borrador cargado en el editor')).toBeVisible({ timeout: 120_000 });
  const editor = page.getByRole('textbox', { name: /^Markdown \(front matter/ });
  await expect(editor).toHaveValue(/slug: facturas/);
  await page.getByRole('button', { name: 'Guardar manifiesto' }).click();
  await expect(page.getByText('Manifiesto guardado.')).toBeVisible();
  await expect(page.getByText(/2 dominios/)).toBeVisible();
});
