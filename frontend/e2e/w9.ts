import { createHash } from 'node:crypto';
import { inflateRawSync } from 'node:zlib';

import { expect, type Page } from '@playwright/test';

import { csrf, DESTINATION, ensureLocation, locationId } from './helpers';

// Utilidades de los E2E de 2.0 (W9) con el LiteLLM falso de docker-compose.e2e.yml. La carpeta de origen /mnt/e2e/w9 la crea
// scripts/e2e_data.sh con documentos sintéticos: factura con IVA, informe, dos versiones de un manual, una receta (para
// la IA) y una nota con una contraseña inventada (para la redacción).
export const FAKE_URL = 'http://litellm-fake:4000';
export const FAKE_KEY = 'sk-e2e-fake';
export const SECRET = 'Sintetica-E2E-2024!';

/** Plantilla con tres ejes: dominio (carpeta), tipo de material (subcarpeta) e impuestos (solo etiqueta, varios). */
export const AXES_TEMPLATE = `---
schema: 2
title: Ejes E2E
axes:
  - key: domains
    name: Dominios
    organizes: folder
    entries:
      - slug: facturas
        name: Facturas
        keywords: [factura]
      - slug: informes
        name: Informes
        keywords: [informe]
      - slug: manuales
        name: Manuales
        keywords: [manual]
      - slug: notas
        name: Notas
        keywords: [nota]
  - key: material_types
    name: Tipos de material
    organizes: subfolder
    entries:
      - slug: original
        name: Original
  - key: impuestos
    name: Impuestos
    multiple: true
    entries:
      - slug: iva
        name: IVA
        keywords: [iva]
      - slug: irpf
        name: IRPF
---
Plantilla sintética de los E2E.
`;

/** El mismo catálogo en el formato de la 1.x (sin `schema` ni `axes`): se restaura migrado a 2.0 (U4). */
export const MANIFEST_V1 = `---
title: Manifiesto 1.x E2E
domains:
  - slug: facturas
    name: Facturas
    keywords: [factura]
  - slug: informes
    name: Informes
    keywords: [informe]
material_types:
  - slug: original
    name: Original
---
Manifiesto sintético en formato 1.x.
`;

type Json = Record<string, unknown>;

export async function api(
  page: Page,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  url: string,
  data?: Json,
  headers = {},
) {
  const response = await page.request.fetch(url, {
    method,
    headers: { ...(method === 'GET' ? {} : await csrf(page)), ...headers },
    ...(data === undefined ? {} : { data }),
  });
  return response;
}

/** IA («Conexión con LiteLLM» y «Modelos por funcionalidad») contra el LiteLLM falso, con modelo propio para agentes y embeddings (idempotente). */
export async function configureAi(page: Page) {
  const current = (await (await api(page, 'GET', '/api/v1/admin/ai-settings')).json()) as {
    families: { key: string; fields: { name: string; value: string | null; hint: string | null }[] }[];
  };
  const fields = Object.fromEntries(
    (current.families.find((family) => family.key === 'litellm')?.fields ?? []).map((f) => [f.name, f]),
  );
  if (
    fields.base_url?.value === FAKE_URL &&
    fields.virtual_key?.hint &&
    fields.model_agent?.value === 'doc-organize-agent' &&
    fields.model_embed?.value === 'doc-organize-embed'
  ) {
    return; // otro test ya la dejó así (los E2E van en paralelo)
  }
  const response = await api(page, 'PUT', '/api/v1/admin/ai-settings/litellm', {
    fields: {
      base_url: FAKE_URL,
      virtual_key: FAKE_KEY,
      model_agent: 'doc-organize-agent',
      model_embed: 'doc-organize-embed',
    },
  });
  expect(response.ok(), await response.text()).toBeTruthy();
}

/** La plantilla `ejes-e2e` (idempotente). */
export async function ensureTemplate(page: Page) {
  const response = await api(page, 'PUT', '/api/v1/taxonomy-templates/ejes-e2e', { markdown: AXES_TEMPLATE });
  expect([200, 201]).toContain(response.status());
}

export interface Run {
  id: string;
  status: string;
  result: Json | null;
  error_code: string | null;
  error_message: string | null;
  artifacts: { id: number; name: string; size_bytes: number }[];
}

export async function waitRun(page: Page, id: string, timeout = 240_000): Promise<Run> {
  let run: Run | undefined;
  await expect
    .poll(
      async () => {
        run = (await (await api(page, 'GET', `/api/v1/runs/${id}`)).json()) as Run;
        return run.status;
      },
      { timeout, intervals: [1_000, 2_000, 3_000] },
    )
    .toMatch(/^(succeeded|failed|cancelled)$/);
  if (!run) throw new Error('sin run');
  expect(run.status, `${run.error_code}: ${run.error_message}`).toBe('succeeded');
  return run;
}

/** Encola un run del proyecto por la API y espera a que termine bien. */
export async function runOperation(
  page: Page,
  projectId: number,
  body: Json,
  timeout?: number,
): Promise<Run> {
  const response = await api(page, 'POST', `/api/v1/projects/${projectId}/runs`, body);
  expect(response.status(), await response.text()).toBe(202);
  return waitRun(page, ((await response.json()) as { id: string }).id, timeout);
}

export const W9_SOURCE = 'W9 origen';

/** Proyecto sobre la ubicación `w9` (toda), escaneado. */
export async function scannedProject(page: Page, name: string): Promise<number> {
  await ensureLocation(page, W9_SOURCE, [/^e2e$/, /^w9$/], { usage: 'Origen', rw: false });
  await ensureLocation(page, DESTINATION, [/^e2e-out$/], { usage: 'Destino', rw: true });
  const response = await api(page, 'POST', '/api/v1/projects', {
    name,
    source_location_id: await locationId(page, W9_SOURCE),
    source_subpaths: [''],
    destination_location_id: await locationId(page, DESTINATION),
    destination_parent: '',
    new_folder: name,
  });
  expect(response.status(), await response.text()).toBe(201);
  const id = ((await response.json()) as { id: number }).id;
  await runOperation(page, id, { operation: 'scan' }, 300_000);
  return id;
}

/** El run que muestra la página de detalle tras lanzarlo desde la interfaz. */
export async function runFromUrl(page: Page): Promise<string> {
  await page.waitForURL(/\/runs\/[0-9a-f-]{36}$/);
  return page.url().split('/').pop() ?? '';
}

export function sha256(data: Buffer): string {
  return createHash('sha256').update(data).digest('hex');
}

export function resultValue(page: Page, label: string) {
  return page.locator('dt', { hasText: new RegExp(`^${label}$`) }).locator('xpath=following-sibling::dd[1]');
}

/** Los ficheros de un ZIP (directorio central; sin dependencias): nombre → contenido. Solo «stored» y «deflate». */
export function unzip(data: Buffer): Map<string, Buffer> {
  const end = data.lastIndexOf(Buffer.from([0x50, 0x4b, 0x05, 0x06]));
  if (end < 0) throw new Error('No es un ZIP');
  const entries = data.readUInt16LE(end + 10);
  let offset = data.readUInt32LE(end + 16);
  const files = new Map<string, Buffer>();
  for (let i = 0; i < entries; i += 1) {
    const method = data.readUInt16LE(offset + 10);
    const size = data.readUInt32LE(offset + 20);
    const nameLength = data.readUInt16LE(offset + 28);
    const extraLength = data.readUInt16LE(offset + 30);
    const commentLength = data.readUInt16LE(offset + 32);
    const local = data.readUInt32LE(offset + 42);
    const name = data.subarray(offset + 46, offset + 46 + nameLength).toString('utf8');
    const start = local + 30 + data.readUInt16LE(local + 26) + data.readUInt16LE(local + 28);
    const raw = data.subarray(start, start + size);
    files.set(name, method === 8 ? inflateRawSync(raw) : raw);
    offset += 46 + nameLength + extraLength + commentLength;
  }
  return files;
}

/** Todo el texto de un ZIP (para buscar lo que no debe salir). */
export function zipText(data: Buffer): string {
  return [...unzip(data).values()].map((file) => file.toString('utf8')).join('\n');
}
