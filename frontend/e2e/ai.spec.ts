import { expect, type Page, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, createProject, login } from './helpers';

// Fase 8 (doc_organize 2.0: familia única «Conexión con LiteLLM» + «Modelos por funcionalidad», json_schema estricto) con el LiteLLM falso de docker-compose.e2e.yml (`litellm-fake`, clave `sk-e2e-fake`; nada sale a la red):
// configurar la IA → ver el uso → construir el contexto con IA → pedir un borrador de manifiesto y guardarlo.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

const FAKE_URL = 'http://litellm-fake:4000';
const FAKE_KEY = 'sk-e2e-fake';

function resultValue(page: Page, label: string) {
  return page.locator('dt', { hasText: new RegExp(`^${label}$`) }).locator('xpath=following-sibling::dd[1]');
}

/** Rellena y guarda la URL y la clave de un bloque (`region`); `family` es el nombre de su botón «Guardar». */
async function configure(page: Page, region: string, family: string) {
  const card = page.getByRole('region', { name: region });
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

  await page.goto('/admin/ai/settings');
  await expect(page.getByRole('heading', { name: 'Configuración IA' })).toBeVisible();
  // 2.2: la URL y la clave de los modelos están en «Conexión con LiteLLM» (encima de la tabla por funcionalidad).
  await configure(page, 'Conexión con LiteLLM', 'Conexión con LiteLLM');
  await configure(page, 'Uso de LiteLLM', 'Uso de LiteLLM');
  const settings = await page.request.get('/api/v1/admin/ai-settings');
  expect(await settings.text()).not.toContain(FAKE_KEY);

  // W1: «Uso» dentro del grupo «IA» del menú, abierto porque estamos en una página suya.
  await page
    .getByRole('navigation', { name: 'Navegación principal' })
    .getByRole('link', { name: 'Uso' })
    .click();
  // El gasto de la clave de LiteLLM.
  const usage = page.getByRole('region', { name: 'Clave de LiteLLM' });
  await expect(usage.getByText('Gasto acumulado').locator('xpath=..')).toContainText('0,42');

  const id = await createProject(page, project, ['2024']);
  await page.goto(`/projects/${id}/scan`);
  await page.getByRole('button', { name: 'Escanear todas las carpetas' }).click();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 180_000 });

  // Construir con IA (dominios descubiertos; fila «Clasificar» de «Modelos por funcionalidad»).
  await page.goto(`/projects/${id}/context?paso=construir`);
  await expect(page.getByText('El proyecto aún no tiene contexto.')).toBeVisible();
  await page.getByRole('switch', { name: /Clasificar con IA/ }).check();
  await expect(page.getByText('El contenido sale de la aplicación')).toBeVisible();
  await page.getByRole('button', { name: 'Construir' }).click();
  await expect(page.getByRole('heading', { name: 'Construir contexto' })).toBeVisible();
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 180_000 });
  await expect(resultValue(page, 'Con IA')).toHaveText('Sí');
  await expect(resultValue(page, 'Errores de la IA')).toHaveText('0');

  // Borrador: está con el manifiesto (solo con su catálogo); se carga en el editor sin guardarse y se guarda a mano.
  await page.goto(`/projects/${id}/context?paso=taxonomia`);
  // La opción del catálogo: el `input` de Mantine no tiene tamaño, se pulsa su etiqueta visible.
  await page.getByText('Manifiesto del proyecto', { exact: true }).click();
  await page.getByRole('button', { name: 'Pedir borrador' }).click();
  await expect(page.getByText('Borrador cargado en el editor')).toBeVisible({ timeout: 120_000 });
  const editor = page.getByRole('textbox', { name: /^Markdown \(front matter/ });
  await expect(editor).toHaveValue(/slug: facturas/);
  await page.getByRole('button', { name: 'Guardar manifiesto' }).click();
  await expect(page.getByText('Manifiesto guardado.')).toBeVisible();
  await expect(page.getByText(/2 dominios/)).toBeVisible();

  // 2.1: el borrador llamó al modelo (la construcción por carpetas no: las reglas lo clasifican todo), y su consumo
  // se ve en IA › Uso.
  await page.goto('/admin/ai/usage');
  await expect(
    page.getByRole('region', { name: 'Por tarea' }).getByRole('row', { name: /Diseñar la taxonomía/ }),
  ).toBeVisible();
});
