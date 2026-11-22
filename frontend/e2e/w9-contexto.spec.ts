import { mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

import { expect, test } from '@playwright/test';

import { ADMIN_PASSWORD, ADMIN_USER, login } from './helpers';
import {
  api,
  configureAi,
  ensureTemplate,
  resultValue,
  runFromUrl,
  runOperation,
  scannedProject,
  waitRun,
} from './w9';

// W9 (doc_organize 2.0.0rc2) con el LiteLLM falso (json_schema, herramientas y embeddings), sobre la carpeta sintética
// `w9`: perfil y vista previa → construir por ejes con IA, semántica y versiones → evidencia y procedencia →
// versiones → frescura → revisar clasificación y Calidad → diseñador, revisor y auditor.
test.skip(!ADMIN_USER || !ADMIN_PASSWORD, 'Define DOW_E2E_ADMIN_USER y DOW_E2E_ADMIN_PASSWORD');

/** La carpeta `w9` en el host (los E2E corren en frontend/; compose la monta en /mnt/e2e/w9). */
const W9 = join(process.cwd(), '..', 'dev-data', 'e2e', 'w9');

interface Axis {
  slug: string;
  classified_by: string | null;
  evidence: string | null;
  evidence_verified: boolean | null;
}
interface Doc {
  path: string;
  axes: Record<string, Axis[]>;
  version: string | null;
  is_current: boolean | null;
}

test('contexto 2.0: ejes con IA, semántica y versiones; revisión, calidad y agentes', async ({ page }) => {
  test.setTimeout(900_000);
  const name = `Contexto 2.0 ${Date.now()}`;
  await login(page);
  await configureAi(page);
  await ensureTemplate(page);
  const id = await scannedProject(page, name);
  const settings = await api(page, 'PUT', `/api/v1/projects/${id}/ai-settings`, {
    context_semantic: true,
    context_versions: 'mark',
  });
  expect(settings.ok(), await settings.text()).toBeTruthy();

  // Perfil del proyecto y vista previa del prompt (con la plantilla elegida, sin llamar al modelo).
  await page.goto(`/projects/${id}/context`);
  await page.getByText('Plantilla', { exact: true }).first().click();
  await page.getByRole('combobox', { name: 'Plantilla' }).click();
  await page.getByRole('option', { name: /ejes-e2e/ }).click();
  const profile = page.getByRole('region', { name: 'Perfil del proyecto' });
  await profile
    .getByRole('textbox', { name: /^Perfil/ })
    .fill('## Glosario\n- Receta: documento sintético de cocina de los E2E.\n');
  await profile.getByRole('button', { name: 'Guardar perfil' }).click();
  await expect(profile.getByText('Perfil guardado.')).toBeVisible();
  await profile.getByRole('button', { name: 'Vista previa del prompt' }).click();
  const preview = profile.getByRole('region', { name: 'Vista previa del prompt' });
  await expect(preview).toContainText('documento sintético de cocina de los E2E', { timeout: 30_000 });
  await expect(preview).toContainText('Eje impuestos: Impuestos');

  // Construir con la plantilla de ejes y la IA para lo que las reglas no clasifican.
  await page.getByRole('link', { name: 'Siguiente: Construir' }).click();
  await page.getByRole('switch', { name: 'Construir el sitio' }).uncheck(); // el sitio lo prueba w9-entrega
  await page.getByRole('switch', { name: /Clasificar con IA/ }).check();
  await page.getByRole('button', { name: 'Construir' }).click();
  const buildId = await runFromUrl(page);
  await expect(page.getByText('Terminada')).toBeVisible({ timeout: 300_000 });
  const build = await waitRun(page, buildId);
  const semantic = build.result?.semantic as { enabled: boolean; index_vectors: number };
  expect(semantic.enabled).toBe(true);
  expect(semantic.index_vectors).toBeGreaterThan(0);
  await expect(resultValue(page, 'Con IA')).toHaveText('Sí');

  // Ejes, evidencia y procedencia.
  const context = (await (await api(page, 'GET', `/api/v1/projects/${id}/context`)).json()) as {
    taxonomy_axes: { key: string }[];
    ai_provenance: { task: string; model: string }[];
    version_groups: { members: string[] }[];
    domains: { slug: string }[];
  };
  expect(context.taxonomy_axes.map((axis) => axis.key)).toEqual(['domains', 'material_types', 'impuestos']);
  expect(context.ai_provenance.some((item) => item.task === 'classify')).toBe(true);
  expect(context.version_groups).toHaveLength(1);
  const docs: Doc[] = [];
  for (const domain of [...context.domains.map((d) => `domain=${d.slug}&`), '']) {
    const page_ = await api(page, 'GET', `/api/v1/projects/${id}/context/documents?${domain}limit=50`);
    expect(page_.ok(), `${domain}: ${await page_.text()}`).toBeTruthy();
    docs.push(...((await page_.json()) as { items: Doc[] }).items);
  }
  const factura = docs.find((doc) => doc.path.endsWith('factura_luz.txt'));
  expect(factura?.axes.impuestos?.map((value) => value.slug)).toEqual(['iva']);
  const byAi = docs.flatMap((doc) => Object.values(doc.axes).flat()).filter((v) => v.classified_by === 'ai');
  expect(byAi.length).toBeGreaterThan(0);
  expect(byAi.some((value) => value.evidence && value.evidence_verified === false)).toBe(true);
  const old = docs.find((doc) => doc.path.endsWith('Manual_proceso_v1.txt'));
  expect(old?.is_current).toBe(false);

  // En la página: evidencia de la IA con su procedencia, y la tarjeta de versiones.
  await page.goto(`/projects/${id}/context`);
  // La lista conserva los documentos del dominio anterior mientras carga (`keepPreviousData`): sin esperar a la
  // respuesta, «Cómo se clasificó» abría un documento de otro dominio y la prueba fallaba a veces.
  const manuals = page.waitForResponse(
    (response) =>
      response.url().includes('/context/documents') && /[?&]domain=manuales(&|$)/.test(response.url()),
  );
  await page.getByRole('button', { name: 'Manuales', exact: true }).click();
  await manuals;
  await expect(page.getByRole('heading', { name: 'Manuales', level: 4 })).toBeVisible();
  for (const summary of await page.getByText('Cómo se clasificó').all()) {
    await summary.click();
  }
  await expect(page.getByText('Cita no encontrada en el texto').first()).toBeVisible();
  await expect(page.getByText(/Clasificado con el prompt .* y el modelo/).first()).toBeVisible();
  const versions = page.getByRole('region', { name: 'Versiones de un documento' });
  await expect(versions).toContainText('Vigente');
  await versions.getByRole('button', { name: /Marcar .*Manual_proceso_v1\.txt como vigente/ }).click();
  await expect(versions.getByText('Decidido: se aplica al reconstruir.')).toBeVisible();

  // Frescura: un documento nuevo en el origen y otro escaneo → el contexto avisa de que está desactualizado.
  const extra = `nuevo-${Date.now()}.txt`;
  mkdirSync(W9, { recursive: true });
  writeFileSync(join(W9, extra), 'Documento sintético añadido después de construir.\n');
  try {
    await runOperation(page, id, { operation: 'scan' }, 300_000);
    await page.goto(`/projects/${id}/context`);
    await expect(page.getByText('El contexto está desactualizado')).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText('1 documento nuevo sin incluir')).toBeVisible();
  } finally {
    rmSync(join(W9, extra), { force: true });
  }

  // Revisar clasificación: la cola tiene la cita no verificada y se decide a mano.
  await page.goto(`/projects/${id}/context/review`);
  await expect(page.getByText('Cita no verificada').first()).toBeVisible();
  await page.getByRole('button', { name: 'Confirmar' }).first().click();
  const decisions = page.getByRole('region', { name: 'Decisiones' });
  await expect(decisions.getByRole('button', { name: /Revocar la decisión de/ }).first()).toBeVisible();

  // Calidad: con las decisiones del proyecto como referencia.
  await page.goto(`/projects/${id}/context/quality`);
  await page.getByText('Decisiones del proyecto', { exact: true }).click();
  const evaluation = page.getByRole('region', { name: 'Evaluación del contexto' });
  await evaluation.getByRole('button', { name: 'Evaluar' }).click();
  await expect(evaluation.getByRole('table').first()).toContainText('domains', { timeout: 120_000 });

  // Revisor (agente): propone sin aplicar; se acepta su propuesta.
  await page.goto(`/projects/${id}/context/review`);
  const reviewer = page.getByRole('region', { name: 'Propuestas del revisor (IA)' });
  await reviewer.getByRole('button', { name: 'Pedir propuestas' }).click();
  await expect(reviewer.getByText('Terminó')).toBeVisible({ timeout: 120_000 });
  const accept = reviewer.getByRole('button', { name: /Aceptar la propuesta para/ }).first();
  await expect(accept).toBeVisible();
  await accept.click();
  await expect(reviewer.getByText('No hay propuestas pendientes.')).toBeVisible();
  const decided = (await (await api(page, 'GET', `/api/v1/projects/${id}/context/decisions`)).json()) as {
    decisions: { reason: string | null }[];
  };
  expect(decided.decisions.some((d) => d.reason?.startsWith('Propuesta del revisor'))).toBe(true);

  // Informe del auditor (sin IA).
  await page.goto(`/projects/${id}/context/quality`);
  const audit = page.getByRole('region', { name: 'Informe del auditor' });
  await audit.getByRole('button', { name: 'Auditar' }).click();
  await expect(audit.getByRole('table', { name: 'Informe del auditor' })).toContainText('impuestos', {
    timeout: 120_000,
  });

  // Diseñador de la taxonomía (agente) desde la plantilla: propone «Recetas»; se carga en el editor sin guardarse.
  await page.goto(`/projects/${id}/context?paso=taxonomia`);
  await page.getByText('Manifiesto del proyecto', { exact: true }).click();
  // Con un manifiesto guardado, «Crear o mejorar con IA» empieza plegado.
  await expect(page.getByRole('textbox', { name: /^Markdown \(front matter/ })).toBeVisible();
  // `aria-expanded` espera al botón (sea «Crear…» u «Ocultar…»); `isVisible()` no espera y dependía del momento.
  const create = page.getByRole('button', { name: /Crear o mejorar con IA/ });
  if ((await create.getAttribute('aria-expanded')) === 'false') {
    await create.click();
  }
  const designer = page.getByRole('region', { name: 'Diseñar taxonomía con IA (agente)' });
  await designer.getByText('Una plantilla', { exact: true }).click();
  await designer.getByRole('combobox', { name: 'Plantilla' }).click();
  await page.getByRole('option', { name: 'Ejes E2E' }).click();
  await designer.getByRole('button', { name: 'Diseñar con IA' }).click();
  await expect(designer.getByText('Terminó')).toBeVisible({ timeout: 180_000 });
  await designer.getByRole('button', { name: 'Cargar la propuesta en el editor' }).click();
  await expect(page.getByRole('textbox', { name: /^Markdown \(front matter/ })).toHaveValue(/slug: recetas/);
  await page.getByRole('button', { name: 'Comprobar manifiesto' }).click();
  await expect(page.getByRole('table', { name: 'Informe por reglas' }).first()).toContainText('domains', {
    timeout: 120_000,
  });
  const manifest = (await (
    await api(page, 'GET', `/api/v1/projects/${id}/context/taxonomy-manifest`)
  ).json()) as {
    markdown: string | null;
  };
  expect(manifest.markdown ?? '').not.toContain('recetas'); // la propuesta no se guarda sola
});
