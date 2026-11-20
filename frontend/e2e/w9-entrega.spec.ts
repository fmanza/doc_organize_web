import { expect, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, login } from './helpers';
import {
  api,
  ensureTemplate,
  runFromUrl,
  runOperation,
  scannedProject,
  SECRET,
  sha256,
  unzip,
  waitRun,
  zipText,
} from './w9';

// W9 (doc_organize 2.0.0rc2): las tres entregas del contexto (Excel, sitio sin conexión y paquete para IA) desde la
// tarjeta «Entregar el contexto»: cada una se descarga y su SHA-256 coincide con el que enseña el detalle; la
// contraseña sintética de la carpeta `w9` no sale en ninguna (redacción). Datos sintéticos.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

test('entregar el contexto: Excel, sitio sin conexión y paquete para IA, con su SHA-256', async ({
  page,
}) => {
  test.setTimeout(600_000);
  await login(page);
  await ensureTemplate(page);
  const id = await scannedProject(page, `Entrega ${Date.now()}`);
  await runOperation(page, id, {
    operation: 'context_build',
    catalog: 'template',
    template_name: 'ejes-e2e',
  });

  const deliver = async (button: RegExp, configure?: () => Promise<void>) => {
    await page.goto(`/projects/${id}/context`);
    const card = page.getByRole('region', { name: 'Entregar el contexto' });
    await configure?.();
    await card.getByRole('button', { name: button }).click();
    const runId = await runFromUrl(page);
    const run = await waitRun(page, runId);
    await expect(page.getByText('Terminada')).toBeVisible();
    const [artifact] = run.artifacts;
    expect(artifact).toBeDefined();
    // Descarga desde el enlace del detalle (como lo haría la persona).
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('link', { name: artifact?.name ?? '' }).click(),
    ]);
    const path = await download.path();
    const { readFileSync } = await import('node:fs');
    const data = readFileSync(path);
    return { run, data };
  };

  // Excel del contexto.
  const excel = await deliver(/^Excel del contexto$/);
  const sheets = zipText(excel.data); // un .xlsx es un ZIP
  expect(sheets).toContain('Valores');
  expect(sheets).toContain('Manual_proceso_v2.txt');
  expect(sheets).not.toContain('/mnt/'); // claves relativas, sin rutas del contenedor

  // Sitio sin conexión con llms.txt: la huella del detalle es la del fichero descargado.
  const site = await deliver(/^Sitio sin conexión$/, async () => {
    await page.getByRole('checkbox', { name: /llms\.txt/ }).check();
  });
  const siteSha = String(site.run.result?.sha256);
  expect(siteSha).toBe(sha256(site.data));
  await expect(page.getByTestId('sha256')).toHaveText(siteSha);
  await expect(page.getByText(/contenido de terceros de las páginas está neutralizado/)).toBeVisible();
  const siteFiles = unzip(site.data);
  expect(siteFiles.has('sitio/index.html') && siteFiles.has('sitio/llms.txt')).toBe(true);
  expect(siteFiles.has('VER_SITIO.md') && siteFiles.has('start_server.py')).toBe(true);
  // Credenciales redactadas en las páginas (ajuste del proyecto). La copia del original y su conversión (.json) van
  // tal cual en el sitio: limitación de doc_organize 2.0.0rc2, pedida en el informe de W9.
  const pages = [...siteFiles].filter(([file]) => file.endsWith('.html') || file.endsWith('.md'));
  const page_ = pages.find(([file]) => file.includes('nota_acceso') && file.endsWith('.html'));
  expect(page_?.[1].toString('utf8')).toContain('REDACTADO');
  expect(pages.map(([, content]) => content.toString('utf8')).join(' ')).not.toContain(SECRET);

  // Paquete para IA (redactado: quien no es admin no puede desactivarlo; aquí se deja como está).
  const bundle = await deliver(/^Paquete para IA$/, async () => {
    await expect(page.getByText(/sale de la aplicación y puede ser confidencial/)).toBeVisible();
  });
  const bundleSha = String(bundle.run.result?.sha256);
  expect(bundleSha).toBe(sha256(bundle.data));
  await expect(page.getByTestId('sha256')).toHaveText(bundleSha);
  const bundleFiles = unzip(bundle.data);
  expect(bundleFiles.has('llms.txt') && bundleFiles.has('context.json')).toBe(true);
  const bundleText = zipText(bundle.data);
  expect(bundleText).toContain('REDACTADO');
  expect(bundleText).not.toContain(SECRET);

  // Las huellas quedan en la auditoría.
  const audit = await (await api(page, 'GET', '/api/v1/audit?action=project.export&limit=50')).text();
  expect(audit).toContain(siteSha);
  expect(audit).toContain(bundleSha);
});
