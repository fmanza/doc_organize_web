import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';
import { nameFromFile } from './useContext';
import { SITE_SANDBOX } from './SiteViewerPage';

const RUN_ID = '55555555-5555-4555-8555-555555555555';
const NO_MANIFEST = {
  markdown: null,
  error: null,
  domains: [],
  material_types: [],
  etag: 'none',
  last_changed_at: null,
};
const NO_VERSIONS = { items: [], limit: 5 };
const CONTEXT = {
  output_folder_name: 'organizado',
  catalog_kind: 'template',
  taxonomy_template_name: 'calidad',
  documents_count: 2,
  unclassified_count: 1,
  failed_count: 1,
  collisions_count: 2,
  site_built: true,
  domains: [{ slug: 'facturas', name: 'Facturas', description: null, status: 'borrador', documents: 2 }],
  built_by_run_id: RUN_ID,
  built_at: '2026-11-02T08:00:00Z',
};
const DOCUMENT = {
  title: 'Factura enero',
  domain_slug: 'facturas',
  document_type: 'pdf',
  material_type: null,
  material_type_name: null,
  folder: '2024',
  path: 'enero/factura.pdf',
  organized_path: 'organizado/facturas/pdf/factura/factura.pdf',
  failed: false,
  collision: false,
  output_path: '2024/enero/factura.md',
  keywords: [],
  ai_filled: [],
};
const TEMPLATES = {
  items: [
    { name: 'calidad', title: 'Calidad', description: null, builtin: true, updated_at: null },
    {
      name: 'obras',
      title: 'Obras',
      description: 'Propia',
      builtin: false,
      updated_at: '2026-11-02T08:00:00Z',
    },
  ],
};
const NOT_BUILT = {
  status: 404,
  body: { title: 'Contexto no encontrado', status: 404, code: 'context_not_found' },
};

describe('ContextPage', () => {
  it('sin contexto, construye con una plantilla', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': NOT_BUILT,
      'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'context_build' }),
      },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: runOut({ id: RUN_ID, operation: 'context_build' }) },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    expect(await screen.findByText('El proyecto aún no tiene contexto.')).toBeInTheDocument();
    // Sin contexto se empieza por la taxonomía; los pasos que necesitan contexto están deshabilitados.
    expect(screen.getByRole('link', { name: '1. Taxonomía' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: '3. Resultado' })).toBeDisabled();
    await user.click(screen.getByRole('radio', { name: 'Plantilla' }));
    expect(screen.getByRole('button', { name: 'Siguiente: Construir' })).toBeDisabled();
    expect(
      screen.getByText('Elige una plantilla en el paso Taxonomía.', { ignore: '[hidden] *' }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Plantilla' }));
    await user.click(await screen.findByRole('option', { name: 'Calidad (calidad)', hidden: true }));
    await user.click(screen.getByRole('link', { name: 'Siguiente: Construir' }));
    expect(await screen.findByText('Taxonomía: Plantilla «calidad»')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Construir' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toMatchObject({
      operation: 'context_build',
      catalog: 'template',
      template_name: 'calidad',
      output_folder_name: 'organizado',
      build_site: true,
    });
  });

  it('muestra dominios, avisos, documentos y el sitio', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': { body: CONTEXT },
      'GET /api/v1/projects/7/context/documents': { body: { items: [DOCUMENT], total: 1 } },
      'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
    });

    const user = userEvent.setup();
    renderRoute('/projects/7/context');

    // Con contexto se abre en «Resultado» (D2).
    expect(await screen.findByText(/1 documento no se pudo copiar/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '3. Resultado' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: '4. Revisar' })).toHaveAttribute(
      'href',
      '/projects/7/context/review',
    );
    expect(screen.getByText(/2 documentos comparten nombre/)).toBeInTheDocument();
    expect(await screen.findByText('2024/enero/factura.pdf')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Borrar contexto' })).toBeInTheDocument();

    await user.click(screen.getByRole('link', { name: '6. Entregar' }));
    expect(await screen.findByRole('link', { name: 'Ver el sitio' })).toHaveAttribute(
      'href',
      '/projects/7/context/site',
    );
    // Reconstruir no deja cambiar la carpeta.
    await user.click(screen.getByRole('link', { name: '2. Construir' }));
    expect(await screen.findByText(/Se reconstruye en la carpeta «organizado»/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reconstruir' })).toBeEnabled();
  });

  it('muestra los metadatos, la trazabilidad y filtra por idioma, palabra clave y propuesta de la IA (1.5.0)', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': {
        body: { ...CONTEXT, built_with_version: '1.5.0', ai_classification_model: 'clasificador' },
      },
      'GET /api/v1/projects/7/context/documents': {
        body: {
          items: [
            {
              ...DOCUMENT,
              author: 'Ana Pérez',
              language: 'es',
              description: 'Factura de la luz',
              keywords: ['energía', 'IVA'],
              ai_filled: ['description'],
              rules_domain: 'informes',
              rules_confidence: 0.31,
              ai_domain: 'facturas',
              ai_confidence: 0.9,
              ai_reasoning: 'Habla de importes.',
            },
          ],
          total: 1,
        },
      },
      'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    expect(
      await screen.findByText('doc_organize 1.5.0 · clasificación con clasificador'),
    ).toBeInTheDocument();
    expect(await screen.findByText('Autor: Ana Pérez · Idioma: es')).toBeInTheDocument();
    expect(screen.getByText('energía')).toBeInTheDocument();
    expect(screen.getByTitle('Lo rellenó la IA porque el documento no lo declaraba')).toBeInTheDocument();
    expect(screen.getByText('Cómo se clasificó')).toBeInTheDocument();
    expect(screen.getByText('Reglas: informes (31 %)')).toBeInTheDocument();
    expect(screen.getByText('IA: facturas (90 %)')).toBeInTheDocument();
    expect(screen.queryByText('No aplicada')).not.toBeInTheDocument();
    expect(screen.getByText('Motivo de la IA: Habla de importes.')).toBeInTheDocument();

    await user.type(screen.getByRole('textbox', { name: 'Idioma' }), 'ES');
    await user.type(screen.getByRole('textbox', { name: 'Palabra clave' }), 'iva');
    await user.click(screen.getByRole('radio', { name: 'La IA propuso otro' }));

    await waitFor(() => {
      const urls = callsTo(fetchMock, 'GET', '/api/v1/projects/7/context/documents').map(
        (request) => new URL(request.url).searchParams,
      );
      const last = urls.at(-1);
      expect(last?.get('language')).toBe('es');
      expect(last?.get('keyword')).toBe('iva');
      expect(last?.get('only')).toBe('ai_disagrees');
    });
  });

  it('los sin clasificar dicen por qué y qué propusieron las reglas (1.6.0, G42)', async () => {
    const unclassified = {
      ...DOCUMENT,
      domain_slug: null,
      organized_path: null,
      output_path: null,
      author: 'Luis',
      language: 'es',
    };
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': { body: CONTEXT },
      'GET /api/v1/projects/7/context/documents': (request: Request) =>
        new URL(request.url).searchParams.has('domain')
          ? { body: { items: [DOCUMENT], total: 1 } }
          : {
              body: {
                items: [
                  {
                    ...unclassified,
                    path: 'a.pdf',
                    unclassified_reason: 'below_threshold',
                    rules_domain: 'facturas',
                    rules_confidence: 0.4,
                  },
                  { ...unclassified, path: 'b.pdf', unclassified_reason: 'incomplete_artifacts' },
                ],
                total: 2,
              },
            },
      'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');
    await user.click(await screen.findByRole('button', { name: 'Sin clasificar' }));

    const below = (await screen.findByText('2024/a.pdf')).closest('tr') as HTMLElement;
    expect(within(below).getByText('Por debajo del umbral')).toBeInTheDocument();
    expect(within(below).getByText('Reglas: facturas (40 %)')).toBeInTheDocument();
    expect(within(below).getByText('Autor: Luis · Idioma: es')).toBeInTheDocument();
    const missing = screen.getByText('2024/b.pdf').closest('tr') as HTMLElement;
    expect(within(missing).getByText('Sin convertir')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Motivo' })).toBeInTheDocument();
    expect(screen.queryByText(/Reconstruye el contexto para ver por qué/)).not.toBeInTheDocument();
  });

  it('un contexto anterior a la 1.6 pide reconstruir para ver el motivo', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': { body: { ...CONTEXT, domains: [] } },
      'GET /api/v1/projects/7/context/documents': {
        body: { items: [{ ...DOCUMENT, domain_slug: null, organized_path: null }], total: 1 },
      },
      'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
    });

    renderRoute('/projects/7/context');

    expect(await screen.findByText(/Reconstruye el contexto para ver por qué/)).toBeInTheDocument();
  });

  it('muestra el historial aunque no haya contexto y lo exporta a Excel (1.5.0)', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': NOT_BUILT,
      'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
      'GET /api/v1/projects/7/context/history': {
        body: {
          items: [
            {
              built_at: '2026-11-02T08:00:00+00:00',
              previous_built_at: '2026-11-01T08:00:00+00:00',
              built_with_version: '1.5.0',
              taxonomy_manifest_used: false,
              ai_classification_model: null,
              ai_enrichment_model: 'describe',
              classified: 3,
              unclassified: 1,
              changes_total: 250,
              changes: [
                {
                  path: '2024/enero/factura.pdf',
                  change: 'reclassified',
                  previous_domain: null,
                  domain: 'facturas',
                  previous_material_type: null,
                  material_type: null,
                  classified_by: 'rules',
                },
              ],
            },
          ],
          total: 3,
          error: null,
        },
      },
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'export_xlsx' }),
      },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: runOut({ id: RUN_ID, operation: 'export_xlsx' }) },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context?paso=historial');

    const history = await screen.findByRole('region', { name: 'Historial' });
    expect(await within(history).findByText('250 cambios')).toBeInTheDocument();
    expect(within(history).getByText('doc_organize 1.5.0 · descripciones con describe')).toBeInTheDocument();
    expect(within(history).getByText('2024/enero/factura.pdf')).toBeInTheDocument();
    expect(within(history).getByText('sin clasificar → facturas')).toBeInTheDocument();
    expect(within(history).getByText(/primeros 1 de 250/)).toBeInTheDocument();
    expect(within(history).getByText(/2 construcciones más antiguas/)).toBeInTheDocument();
    await user.click(within(history).getByRole('button', { name: 'Descargar Excel' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toEqual({ operation: 'export_xlsx', kind: 'context_history' });
  });

  it('un historial demasiado grande remite al Excel', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': NOT_BUILT,
      'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
      'GET /api/v1/projects/7/context/history': {
        body: { items: [], total: 0, error: 'history_too_large' },
      },
    });

    renderRoute('/projects/7/context?paso=historial');

    expect(await screen.findByText(/demasiado grande para mostrarlo aquí/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Descargar Excel' })).toBeInTheDocument();
  });

  it('avisa de un contexto a medio guardar y deja completarlo o borrarlo (2.1)', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': NOT_BUILT,
      'GET /api/v1/projects/7/context/leftover': { body: { output_folder_name: 'organizado' } },
      'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    const alert = await screen.findByText('Hay un contexto a medio guardar');
    const box = alert.closest('[role="status"]') as HTMLElement;
    expect(within(box).getByText(/carpeta «organizado»/)).toBeInTheDocument();
    expect(within(box).getByRole('button', { name: 'Borrar contexto' })).toBeInTheDocument();
    await user.click(within(box).getByRole('link', { name: 'Ir a Construir' }));
    expect(
      await screen.findByText(/Se construye en la carpeta «organizado», que quedó a medias/),
    ).toBeInTheDocument();
  });

  it('un lector no construye ni edita el manifiesto', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: { ...PROJECT, role: 'viewer' } },
      'GET /api/v1/projects/7/context': NOT_BUILT,
      'GET /api/v1/projects/7/context/taxonomy-manifest': { body: NO_MANIFEST },
      'GET /api/v1/projects/7/context/taxonomy-manifest/versions': { body: NO_VERSIONS },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    expect(await screen.findByText('El proyecto aún no tiene contexto.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Construir' })).not.toBeInTheDocument();
    // Sin contexto construido con el manifiesto, se ve con un enlace.
    await user.click(screen.getByRole('button', { name: 'Ver el manifiesto del proyecto' }));
    expect(await screen.findByRole('textbox', { name: /Markdown/ })).toHaveAttribute('readonly');
    expect(screen.queryByRole('button', { name: 'Guardar manifiesto' })).not.toBeInTheDocument();
  });
});

describe('SiteViewerPage', () => {
  it('carga el sitio en un iframe aislado', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'POST /api/v1/projects/7/context/site-session': {
        body: { url: '/site/7.1.99.abc/', expires_at: '2026-11-02T09:00:00Z' },
      },
    });

    renderRoute('/projects/7/context/site');

    const frame = await screen.findByTitle('Sitio del contexto');
    expect(frame).toHaveAttribute('src', '/site/7.1.99.abc/');
    expect(frame.getAttribute('sandbox')).toBe(SITE_SANDBOX);
    expect(SITE_SANDBOX).not.toContain('allow-same-origin');
    expect(screen.getByRole('link', { name: 'Abrir en otra pestaña' })).toHaveAttribute(
      'rel',
      'noopener noreferrer',
    );
  });

  it('2.1.1: desde el visor se vuelve a «6. Entregar» con un enlace fijo', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'POST /api/v1/projects/7/context/site-session': {
        body: { url: '/site/7.1.99.abc/', expires_at: '2026-11-02T09:00:00Z' },
      },
    });

    renderRoute('/projects/7/context/site');

    const back = await screen.findByRole('link', { name: 'Volver a 6. Entregar' });
    expect(back).toHaveAttribute('href', '/projects/7/context?paso=entregar');
    // El visor no se presenta como si fuera el propio paso «Entregar».
    const nav = screen.getByRole('navigation', { name: 'Pasos del contexto' });
    expect(nav.querySelector('[aria-current="page"]')).toBeNull();
  });
});

describe('TaxonomyTemplatesPage', () => {
  it('las incluidas solo se duplican; las propias se editan, descargan y borran', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
      'GET /api/v1/taxonomy-templates/calidad': {
        body: { ...TEMPLATES.items[0], markdown: '---\ndomains: []\n---\n', domains: [], material_types: [] },
      },
      'PUT /api/v1/taxonomy-templates/calidad-copia': { status: 201, body: TEMPLATES.items[1] },
    });
    const user = userEvent.setup();

    renderRoute('/admin/taxonomy-templates');

    expect(await screen.findByRole('button', { name: 'Duplicar calidad' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Borrar calidad' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Borrar obras' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Descargar obras como Markdown' })).toHaveAttribute(
      'href',
      '/api/v1/taxonomy-templates/obras/download',
    );

    await user.click(screen.getByRole('button', { name: 'Duplicar calidad' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('textbox', { name: /Nombre/ })).toHaveValue('calidad-copia');
    // Un nombre en uso no se sobrescribe sin querer.
    const nameBox = within(dialog).getByRole('textbox', { name: /Nombre/ });
    await user.clear(nameBox);
    await user.type(nameBox, 'obras');
    expect(within(dialog).getByText(/Ya existe una plantilla con ese nombre/)).toBeInTheDocument();
    await user.clear(nameBox);
    await user.type(nameBox, 'calidad-copia');
    await waitFor(() =>
      expect(within(dialog).getByRole('textbox', { name: /Markdown/ })).toHaveValue(
        '---\ndomains: []\n---\n',
      ),
    );
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() =>
      expect(callsTo(fetchMock, 'PUT', '/api/v1/taxonomy-templates/calidad-copia')).toHaveLength(1),
    );
  });

  it('un nombre importado se normaliza', () => {
    expect(nameFromFile('SGI Calidad 2026.md')).toBe('sgi-calidad-2026');
    expect(nameFromFile('Ñandú — Obras.MD')).toBe('nandu-obras');
  });
});
