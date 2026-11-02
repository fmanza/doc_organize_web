import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';
import { nameFromFile } from './useContext';
import { SITE_SANDBOX } from './SiteViewerPage';

const RUN_ID = '55555555-5555-4555-8555-555555555555';
const NO_MANIFEST = { markdown: null, error: null, domains: [], material_types: [] };
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
      'GET /api/v1/projects/7/context/taxonomy-manifest': { body: NO_MANIFEST },
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
    await user.click(screen.getByRole('radio', { name: 'Plantilla' }));
    const build = screen.getByRole('button', { name: 'Construir' });
    expect(build).toBeDisabled();
    await user.click(screen.getByRole('combobox', { name: 'Plantilla' }));
    await user.click(await screen.findByRole('option', { name: 'Calidad (calidad)', hidden: true }));
    await user.click(build);

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
      'GET /api/v1/projects/7/context/taxonomy-manifest': { body: NO_MANIFEST },
      'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
    });

    renderRoute('/projects/7/context');

    expect(await screen.findByText(/1 documento no se pudo copiar/)).toBeInTheDocument();
    expect(screen.getByText(/2 documentos comparten nombre/)).toBeInTheDocument();
    expect(await screen.findByText('2024/enero/factura.pdf')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ver el sitio' })).toHaveAttribute(
      'href',
      '/projects/7/context/site',
    );
    expect(screen.getByRole('button', { name: 'Borrar contexto' })).toBeInTheDocument();
    // Reconstruir no deja cambiar la carpeta.
    expect(screen.getByText(/Se reconstruye en la carpeta «organizado»/)).toBeInTheDocument();
  });

  it('un lector no construye ni edita el manifiesto', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: { ...PROJECT, role: 'viewer' } },
      'GET /api/v1/projects/7/context': NOT_BUILT,
      'GET /api/v1/projects/7/context/taxonomy-manifest': { body: NO_MANIFEST },
    });

    renderRoute('/projects/7/context');

    expect(await screen.findByText('El proyecto aún no tiene contexto.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Construir' })).not.toBeInTheDocument();
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
