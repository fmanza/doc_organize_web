import { expect, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, createProject, login } from './helpers';
import { api, AXES_TEMPLATE, configureAi, MANIFEST_V1 } from './w9';

// W9 (doc_organize 2.0.0rc2) con el LiteLLM falso: ajustes de IA por tarea, diagnóstico de los modelos (también el de
// embeddings) y migración de un manifiesto de la 1.x al restaurarlo. Datos sintéticos.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

test('IA por tarea: guardar un ajuste de una tarea y probar su modelo', async ({ page }) => {
  await login(page);
  await configureAi(page);

  await page.goto('/admin/ai/settings');
  const card = page.getByRole('region', { name: 'Modelos de IA' });
  const embed = card.getByRole('group', { name: 'Embeddings (semántica)' });
  await expect(embed.getByRole('textbox', { name: 'Modelo de embeddings' })).toHaveValue(
    'doc-organize-embed',
  );
  const classify = card.getByRole('group', { name: 'Clasificar' });
  const budget = classify.getByRole('textbox', { name: 'Máximo de documentos a clasificar por ejecución' });
  await budget.fill((await budget.inputValue()) === '40' ? '41' : '40'); // un cambio (los E2E se pueden repetir)
  await card.getByRole('button', { name: 'Guardar Modelos de IA' }).click();
  await expect(card.getByText('Guardado.')).toBeVisible();
  const saved = (await (await api(page, 'GET', '/api/v1/admin/ai-settings')).text()).toString();
  expect(saved).not.toContain('sk-e2e-fake');

  // «Probar el modelo» de la tarea de embeddings pide un vector al proxy (con los valores guardados).
  await card.getByRole('button', { name: 'Probar el modelo de la tarea Embeddings (semántica)' }).click();
  await expect(card.getByText('Tarea probada: Embeddings (semántica).')).toBeVisible({ timeout: 30_000 });
});

test('diagnóstico: los modelos de cada tarea responden, también el de embeddings', async ({ page }) => {
  test.setTimeout(240_000);
  await login(page);
  await configureAi(page);

  await page.goto('/admin/diagnostics');
  await page.getByLabel('Probar también los modelos de IA').check();
  const result = page.getByRole('region', { name: 'Resultado del diagnóstico' });
  const tooSoon = page.getByRole('alert').filter({ hasText: 'Espera antes de volver a diagnosticar' });
  // Como mucho uno cada 30 s en la instancia: si otro acaba de ejecutarse (un reintento), se espera y se repite.
  await expect(async () => {
    await page.getByRole('button', { name: 'Ejecutar diagnóstico' }).click();
    await expect(result.or(tooSoon)).toBeVisible({ timeout: 200_000 });
    await expect(result).toBeVisible({ timeout: 1_000 });
  }).toPass({ timeout: 230_000, intervals: [31_000] });
  for (const task of ['classify', 'enrich', 'taxonomy_design', 'agent', 'embed']) {
    await expect(result.getByRole('row', { name: new RegExp(`ai:${task}\\b`) })).toContainText('Correcto');
  }
  // El informe no lleva la clave ni la URL del proxy.
  await expect(result).not.toContainText('sk-e2e-fake');
  await expect(result).not.toContainText('litellm-fake');
});

test('migración: un manifiesto de la 1.x se restaura en formato 2.0', async ({ page }) => {
  await login(page);
  const id = await createProject(page, `Migración ${Date.now()}`, ['2024']);
  const url = `/api/v1/projects/${id}/context/taxonomy-manifest`;
  const etag = async () => ((await (await api(page, 'GET', url)).json()) as { etag: string }).etag;

  // El manifiesto 1.x se acepta; después se guarda otro, y el 1.x queda como versión anterior.
  let saved = await api(page, 'PUT', url, { markdown: MANIFEST_V1 }, { 'If-Match': await etag() });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  saved = await api(page, 'PUT', url, { markdown: AXES_TEMPLATE }, { 'If-Match': await etag() });
  expect(saved.ok(), await saved.text()).toBeTruthy();
  const versions = (await (await api(page, 'GET', `${url}/versions`)).json()) as {
    items: { id: number; action: string; empty: boolean }[];
  };
  const v1 = versions.items.find((item) => !item.empty);
  expect(v1).toBeDefined();

  const restored = await api(
    page,
    'POST',
    `${url}/versions/${v1?.id}/restore`,
    {},
    { 'If-Match': await etag() },
  );
  expect(restored.ok(), await restored.text()).toBeTruthy();
  const manifest = (await (await api(page, 'GET', url)).json()) as { markdown: string; error: string | null };
  expect(manifest.error).toBeNull();
  expect(manifest.markdown).toMatch(/^---\nschema: 2\n/);
  expect(manifest.markdown).toContain('slug: facturas');

  // En la página, el manifiesto del proyecto es ya el migrado.
  await page.goto(`/projects/${id}/context`);
  await page.getByText('Manifiesto del proyecto', { exact: true }).click();
  await expect(page.getByRole('textbox', { name: /^Markdown \(front matter/ })).toHaveValue(/schema: 2/);
});
