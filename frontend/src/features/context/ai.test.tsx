import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

const RUN_ID = '66666666-6666-4666-8666-666666666666';
const NO_MANIFEST = {
  markdown: null,
  error: null,
  domains: [],
  material_types: [],
  etag: 'none',
  last_changed_at: null,
};
const NOT_BUILT = {
  status: 404,
  body: { title: 'Contexto no encontrado', status: 404, code: 'context_not_found' },
};
const BASE = {
  ...session(USER),
  'GET /api/v1/projects/7': { body: PROJECT },
  'GET /api/v1/projects/7/context': NOT_BUILT,
  'GET /api/v1/projects/7/context/taxonomy-manifest': { body: NO_MANIFEST },
  'GET /api/v1/projects/7/context/taxonomy-manifest/versions': { body: { items: [], limit: 5 } },
  'GET /api/v1/taxonomy-templates': { body: { items: [] } },
};

/** Estado de la IA de doc_organize 2.0: una familia (`litellm`) y lo que se puede usar por tarea. */
function status(tasks: Record<string, boolean>) {
  const configured = Object.values(tasks).some(Boolean);
  return {
    'GET /api/v1/ai/status': {
      body: {
        families: { litellm: configured, litellm_usage: false, github_copilot_usage: false },
        tasks: {
          classify: false,
          enrich: false,
          taxonomy_design: false,
          agent: false,
          embed: false,
          ...tasks,
        },
      },
    },
  };
}

describe('ContextPage con IA', () => {
  it('sin configurar, la IA está desactivada y explica por qué', async () => {
    stubApi({ ...BASE, ...status({}) });
    const user = userEvent.setup();

    renderRoute('/projects/7/context?paso=construir');

    const toggle = await screen.findByRole('switch', { name: /Clasificar con IA/ });
    expect(toggle).toBeDisabled();
    expect(screen.getAllByText(/configurar los «Modelos de IA»/).length).toBeGreaterThan(0);
    // «Pedir borrador» está con el manifiesto, en el paso Taxonomía y solo con su catálogo (A5).
    expect(screen.queryByRole('button', { name: 'Pedir borrador' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: '1. Taxonomía' }));
    await user.click(await screen.findByRole('radio', { name: 'Manifiesto del proyecto' }));
    expect(await screen.findByRole('button', { name: 'Pedir borrador' })).toBeDisabled();
  });

  it('con IA avisa de la salida de datos y la pide al construir', async () => {
    const fetchMock = stubApi({
      ...BASE,
      ...status({ classify: true }),
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'context_build' }),
      },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: runOut({ id: RUN_ID, operation: 'context_build' }) },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context?paso=construir');

    const toggle = await screen.findByRole('switch', { name: /Clasificar con IA/ });
    await waitFor(() => expect(toggle).toBeEnabled());
    await user.click(toggle);
    expect(screen.getByText('El contenido sale de la aplicación')).toBeInTheDocument();
    // doc_organize 2.0: con plantilla clasifica la misma tarea (`classify`): sigue disponible. Cambiar de paso no
    // pierde lo elegido en «Construir».
    await user.click(screen.getByRole('link', { name: '1. Taxonomía' }));
    await user.click(await screen.findByRole('radio', { name: 'Plantilla' }));
    await user.click(screen.getByRole('link', { name: '2. Construir' }));
    expect(await screen.findByRole('switch', { name: /Clasificar con IA/ })).toBeEnabled();
    expect(screen.getByRole('switch', { name: /Clasificar con IA/ })).toBeChecked();
    await user.click(screen.getByRole('link', { name: '1. Taxonomía' }));
    await user.click(await screen.findByRole('radio', { name: 'Por carpetas' }));
    await user.click(screen.getByRole('link', { name: '2. Construir' }));
    await user.click(await screen.findByRole('button', { name: 'Construir' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toMatchObject({
      operation: 'context_build',
      catalog: 'discover',
      ai_classification: true,
    });
  });

  it('completar descripciones con IA va aparte de clasificar (1.5.0)', async () => {
    const fetchMock = stubApi({
      ...BASE,
      ...status({ enrich: true }),
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'context_build' }),
      },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: runOut({ id: RUN_ID, operation: 'context_build' }) },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context?paso=construir');

    const enrich = await screen.findByRole('switch', { name: /Completar descripción y palabras clave/ });
    await waitFor(() => expect(enrich).toBeEnabled());
    expect(screen.getByRole('switch', { name: /Clasificar con IA/ })).toBeDisabled();
    await user.click(enrich);
    expect(screen.getByText(/sin descripción o sin palabras clave se enviarán/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Construir' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toMatchObject({
      operation: 'context_build',
      ai_classification: false,
      ai_enrichment: true,
    });
  });

  it('sin configurar, completar descripciones explica por qué', async () => {
    stubApi({ ...BASE, ...status({}) });

    renderRoute('/projects/7/context?paso=construir');

    expect(
      await screen.findByRole('switch', { name: /Completar descripción y palabras clave/ }),
    ).toBeDisabled();
    expect(screen.getAllByText(/configurar los «Modelos de IA»/).length).toBeGreaterThan(0);
  });

  it('el borrador se carga en el editor sin guardarse', async () => {
    let polls = 0;
    const markdown = '---\ndomains:\n- slug: facturas\n  name: Facturas\n---\n';
    const fetchMock = stubApi({
      ...BASE,
      ...status({ taxonomy_design: true }),
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'taxonomy_draft' }),
      },
      [`GET /api/v1/runs/${RUN_ID}`]: () => {
        polls += 1;
        return {
          body:
            polls < 2
              ? runOut({ id: RUN_ID, operation: 'taxonomy_draft', status: 'running' })
              : runOut({
                  id: RUN_ID,
                  operation: 'taxonomy_draft',
                  status: 'succeeded',
                  result: {
                    manifest_markdown: markdown,
                    reasoning: 'Muestra sintética',
                    sample_documents: 3,
                    total_documents: 4,
                  },
                }),
        };
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    await user.click(await screen.findByRole('radio', { name: 'Manifiesto del proyecto' }));
    const sample = await screen.findByRole('textbox', { name: 'Documentos de muestra' });
    await user.clear(sample);
    await user.type(sample, '10');
    await user.click(screen.getByRole('button', { name: 'Pedir borrador' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toEqual({ operation: 'taxonomy_draft', sample_size: 10 });
    expect(
      await screen.findByText('Borrador cargado en el editor', {}, { timeout: 5000 }),
    ).toBeInTheDocument();
    expect(screen.getByText('Muestra sintética')).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: /^Markdown \(front matter/ })).toHaveValue(markdown);
    expect(callsTo(fetchMock, 'PUT', '/api/v1/projects/7/context/taxonomy-manifest')).toHaveLength(0);
    expect(screen.getByRole('button', { name: 'Guardar manifiesto' })).toBeEnabled();
  });

  it('si el borrador falla, muestra el motivo', async () => {
    stubApi({
      ...BASE,
      ...status({ taxonomy_design: true }),
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'taxonomy_draft' }),
      },
      [`GET /api/v1/runs/${RUN_ID}`]: {
        body: runOut({
          id: RUN_ID,
          operation: 'taxonomy_draft',
          status: 'failed',
          error_code: 'ai_auth',
          error_message: 'El servicio de IA rechazó la clave del borrador de manifiesto.',
        }),
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    await user.click(await screen.findByRole('radio', { name: 'Manifiesto del proyecto' }));
    await user.click(await screen.findByRole('button', { name: 'Pedir borrador' }));

    expect(await screen.findByText(/rechazó la clave del borrador/)).toBeInTheDocument();
  });
});
