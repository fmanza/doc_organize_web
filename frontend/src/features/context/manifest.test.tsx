import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

/** El manifiesto solo con su catálogo, «Personalizar para este proyecto», versiones, restaurar y borrar (1.8.0). */

const SAVED = '---\ntitle: Guardado\n---\n';
const TEMPLATE_MD = '---\ntitle: Calidad\n---\n';
const NO_MANIFEST = {
  markdown: null,
  error: null,
  domains: [],
  material_types: [],
  etag: 'none',
  last_changed_at: null,
};
const WITH_MANIFEST = {
  ...NO_MANIFEST,
  markdown: SAVED,
  domains: [{ slug: 'a', name: 'A' }],
  material_types: [],
  etag: 'etag-1',
  last_changed_at: '2026-11-17T10:00:00Z',
};
const VERSION = {
  id: 3,
  created_at: '2026-11-17T10:00:00Z',
  created_by: 'Ana',
  action: 'save',
  empty: false,
  valid: true,
  domains: 2,
  material_types: 1,
};
const NOT_BUILT = {
  status: 404,
  body: { title: 'Contexto no encontrado', status: 404, code: 'context_not_found' },
};
const TEMPLATES = {
  items: [{ name: 'calidad', title: 'Calidad', description: null, builtin: true, updated_at: null }],
};
const CONTEXT = {
  output_folder_name: 'organizado',
  catalog_kind: 'manifest',
  taxonomy_template_name: null,
  documents_count: 0,
  unclassified_count: 0,
  failed_count: 0,
  collisions_count: 0,
  site_built: false,
  domains: [],
  built_by_run_id: null,
  built_at: '2026-11-17T09:00:00Z',
};

function routes(
  extra: Record<string, unknown> = {},
  manifest: object = NO_MANIFEST,
  versions: object[] = [],
) {
  return {
    ...session(USER),
    'GET /api/v1/projects/7': { body: PROJECT },
    'GET /api/v1/projects/7/context': NOT_BUILT,
    'GET /api/v1/projects/7/context/taxonomy-manifest': { body: manifest },
    'GET /api/v1/projects/7/context/taxonomy-manifest/versions': { body: { items: versions, limit: 5 } },
    'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
    'GET /api/v1/taxonomy-templates/calidad': {
      body: { ...TEMPLATES.items[0], markdown: TEMPLATE_MD, domains: [], material_types: [] },
    },
    ...extra,
  } as Parameters<typeof stubApi>[0];
}

const editor = () => screen.findByRole('textbox', { name: /^Markdown \(front matter/ });

describe('Manifiesto del proyecto', () => {
  it('solo se ve con su catálogo y conserva el borrador al cambiar de catálogo', async () => {
    stubApi(routes());
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    await screen.findByRole('radio', { name: 'Por carpetas' });
    expect(screen.queryByRole('region', { name: 'Manifiesto de taxonomía' })).not.toBeInTheDocument();
    expect(screen.getByText(/Un dominio por cada carpeta/)).toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: 'Manifiesto del proyecto' }));
    await user.type(await editor(), 'hola');
    await user.click(screen.getByRole('radio', { name: 'Por carpetas' }));
    expect(screen.queryByRole('region', { name: 'Manifiesto de taxonomía' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('radio', { name: 'Manifiesto del proyecto' }));
    expect(await editor()).toHaveValue('hola');
  });

  it('con un borrador sin guardar no se construye con el manifiesto, pero sí con otro catálogo', async () => {
    stubApi(routes());
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    await user.click(await screen.findByRole('radio', { name: 'Manifiesto del proyecto' }));
    await user.type(await editor(), 'x');
    expect(screen.getByRole('button', { name: 'Siguiente: Construir' })).toBeDisabled();
    expect(
      screen.getByText(/cambios sin guardar en el manifiesto/, { ignore: '[hidden] *' }),
    ).toBeInTheDocument();
    // Entrando directamente en «Construir», tampoco.
    await user.click(screen.getByRole('link', { name: '2. Construir' }));
    expect(await screen.findByRole('button', { name: 'Construir' })).toBeDisabled();
    await user.click(screen.getByRole('link', { name: '1. Taxonomía' }));
    await user.click(await screen.findByRole('radio', { name: 'Por carpetas' }));
    await user.click(screen.getByRole('link', { name: 'Siguiente: Construir' }));
    expect(await screen.findByRole('button', { name: 'Construir' })).toBeEnabled();
  });

  it('«Personalizar para este proyecto» copia la plantilla sin guardar y se puede deshacer', async () => {
    const fetchMock = stubApi(routes());
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    await user.click(await screen.findByRole('radio', { name: 'Plantilla' }));
    expect(screen.queryByRole('button', { name: 'Personalizar para este proyecto' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Plantilla' }));
    await user.click(await screen.findByRole('option', { name: 'Calidad (calidad)', hidden: true }));
    await user.click(screen.getByRole('button', { name: 'Personalizar para este proyecto' }));

    expect(await editor()).toHaveValue(TEMPLATE_MD);
    await waitFor(() =>
      expect(screen.getByRole('textbox', { name: /^Markdown \(front matter/ })).toHaveFocus(),
    );
    expect(screen.getByRole('radio', { name: 'Manifiesto del proyecto' })).toBeChecked();
    expect(screen.getByText(/Copiado de la plantilla «calidad»/)).toBeInTheDocument();
    expect(callsTo(fetchMock, 'PUT', '/api/v1/projects/7/context/taxonomy-manifest')).toHaveLength(0);

    await user.click(screen.getByRole('button', { name: 'Deshacer' }));
    expect(screen.getByRole('radio', { name: 'Plantilla' })).toBeChecked();
    await user.click(screen.getByRole('radio', { name: 'Manifiesto del proyecto' }));
    expect(await editor()).toHaveValue('');
  });

  it('copiar sobre un manifiesto distinto pide confirmación y cancelar no cambia nada', async () => {
    stubApi(routes({}, WITH_MANIFEST));
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    await user.click(await screen.findByRole('radio', { name: 'Plantilla' }));
    await user.click(screen.getByRole('combobox', { name: 'Plantilla' }));
    await user.click(await screen.findByRole('option', { name: 'Calidad (calidad)', hidden: true }));
    await user.click(screen.getByRole('button', { name: 'Personalizar para este proyecto' }));

    const dialog = await screen.findByRole('dialog', { name: '¿Sustituir el texto del manifiesto?' });
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar' }));
    expect(screen.getByRole('radio', { name: 'Plantilla' })).toBeChecked();

    await user.click(screen.getByRole('button', { name: 'Personalizar para este proyecto' }));
    await user.click(await screen.findByRole('button', { name: 'Sustituir' }));
    expect(await editor()).toHaveValue(TEMPLATE_MD);
  });

  it('guardar envía If-Match y, si otro lo cambió, vuelve a leer sin perder el borrador', async () => {
    let gets = 0;
    const fetchMock = stubApi(
      routes({
        'GET /api/v1/projects/7/context/taxonomy-manifest': () => {
          gets += 1;
          return { body: { ...WITH_MANIFEST, etag: `etag-${gets}` } };
        },
        'PUT /api/v1/projects/7/context/taxonomy-manifest': {
          status: 409,
          body: {
            title: 'El manifiesto ha cambiado',
            status: 409,
            code: 'manifest_changed',
            detail: 'Otro usuario lo ha cambiado: recarga para ver su versión.',
          },
        },
      }),
    );
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    await user.click(await screen.findByRole('radio', { name: 'Manifiesto del proyecto' }));
    await user.type(await editor(), 'y');
    await user.click(screen.getByRole('button', { name: 'Guardar manifiesto' }));

    expect(await screen.findByText(/Otro usuario lo ha cambiado/)).toBeInTheDocument();
    const [put] = callsTo(fetchMock, 'PUT', '/api/v1/projects/7/context/taxonomy-manifest');
    expect(put?.headers.get('if-match')).toBe('etag-1');
    await waitFor(() => expect(gets).toBeGreaterThan(1));
    expect(screen.getByRole('textbox', { name: /^Markdown \(front matter/ })).toHaveValue(`${SAVED}y`);
  });

  it('restaura la versión anterior con confirmación y borra el manifiesto', async () => {
    const fetchMock = stubApi(
      routes(
        {
          'POST /api/v1/projects/7/context/taxonomy-manifest/versions/3/restore': { body: WITH_MANIFEST },
          'DELETE /api/v1/projects/7/context/taxonomy-manifest': { body: NO_MANIFEST },
        },
        WITH_MANIFEST,
        [VERSION],
      ),
    );
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    await user.click(await screen.findByRole('radio', { name: 'Manifiesto del proyecto' }));
    await user.click(await screen.findByRole('button', { name: 'Restaurar la versión anterior' }));
    const dialog = await screen.findByRole('dialog', { name: '¿Restaurar esta versión?' });
    expect(within(dialog).getByText(/antes de «Guardar» de Ana/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Restaurar' }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'POST', '/api/v1/projects/7/context/taxonomy-manifest/versions/3/restore'),
      ).toHaveLength(1),
    );
    const [restore] = callsTo(
      fetchMock,
      'POST',
      '/api/v1/projects/7/context/taxonomy-manifest/versions/3/restore',
    );
    expect(restore?.headers.get('if-match')).toBe('etag-1');

    await user.click(screen.getByRole('button', { name: 'Borrar manifiesto' }));
    const confirm = await screen.findByRole('dialog', { name: '¿Borrar el manifiesto?' });
    await user.click(within(confirm).getByRole('button', { name: 'Borrar manifiesto' }));
    await waitFor(() =>
      expect(callsTo(fetchMock, 'DELETE', '/api/v1/projects/7/context/taxonomy-manifest')).toHaveLength(1),
    );
  });

  it('un lector ve las versiones sin restaurar, y el bloque si el contexto se construyó con el manifiesto', async () => {
    stubApi(
      routes(
        {
          'GET /api/v1/projects/7': { body: { ...PROJECT, role: 'viewer' } },
          'GET /api/v1/projects/7/context': { body: CONTEXT },
          'GET /api/v1/projects/7/context/documents': { body: { items: [], total: 0 } },
        },
        WITH_MANIFEST,
        [VERSION],
      ),
    );
    const user = userEvent.setup();

    renderRoute('/projects/7/context?paso=taxonomia');

    expect(await editor()).toHaveAttribute('readonly');
    // Un lector no ve el paso «Construir».
    expect(screen.queryByRole('link', { name: '2. Construir' })).not.toBeInTheDocument();
    // Construido a las 9:00 con el manifiesto, cambiado a las 10:00: hay que reconstruir.
    expect(screen.getByText(/se construyó con el manifiesto anterior a este cambio/)).toBeInTheDocument();
    await user.click(await screen.findByRole('button', { name: 'Versiones (1)' }));
    expect(await screen.findByText('2 dominios · 1 tipos')).toBeInTheDocument();
    // El panel del acordeón tarda en ser accesible: se espera al botón, no solo al texto.
    expect(await screen.findByRole('button', { name: 'Ver' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Restaurar' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Restaurar la versión anterior' })).not.toBeInTheDocument();
  });
});
