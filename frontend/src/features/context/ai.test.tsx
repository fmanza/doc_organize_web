import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

const RUN_ID = '66666666-6666-4666-8666-666666666666';
const NO_MANIFEST = { markdown: null, error: null, domains: [], material_types: [] };
const NOT_BUILT = {
  status: 404,
  body: { title: 'Contexto no encontrado', status: 404, code: 'context_not_found' },
};
const BASE = {
  ...session(USER),
  'GET /api/v1/projects/7': { body: PROJECT },
  'GET /api/v1/projects/7/context': NOT_BUILT,
  'GET /api/v1/projects/7/context/taxonomy-manifest': { body: NO_MANIFEST },
  'GET /api/v1/taxonomy-templates': { body: { items: [] } },
};

function status(families: Record<string, boolean>) {
  return {
    'GET /api/v1/ai/status': {
      body: {
        families: {
          litellm_classification: false,
          litellm_taxonomy_classification: false,
          litellm_taxonomy_manifest_draft: false,
          litellm_usage: false,
          github_copilot_usage: false,
          ...families,
        },
      },
    },
  };
}

describe('ContextPage con IA', () => {
  it('sin configurar, la IA está desactivada y explica por qué', async () => {
    stubApi({ ...BASE, ...status({}) });

    renderRoute('/projects/7/context');

    const toggle = await screen.findByRole('switch', { name: /Clasificar con IA/ });
    expect(toggle).toBeDisabled();
    expect(screen.getByText(/configurar la «Clasificación de dominios»/)).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Pedir borrador' })).toBeDisabled();
  });

  it('con IA avisa de la salida de datos y la pide al construir', async () => {
    const fetchMock = stubApi({
      ...BASE,
      ...status({ litellm_classification: true }),
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'context_build' }),
      },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: runOut({ id: RUN_ID, operation: 'context_build' }) },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    const toggle = await screen.findByRole('switch', { name: /Clasificar con IA/ });
    await waitFor(() => expect(toggle).toBeEnabled());
    await user.click(toggle);
    expect(screen.getByText('El contenido sale de la aplicación')).toBeInTheDocument();
    // Con plantilla se usaría otra familia (sin configurar): se desactiva.
    await user.click(screen.getByRole('radio', { name: 'Plantilla' }));
    expect(screen.getByRole('switch', { name: /Clasificar con IA/ })).toBeDisabled();
    await user.click(screen.getByRole('radio', { name: 'Descubrir dominios' }));
    await user.click(screen.getByRole('button', { name: 'Construir' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toMatchObject({
      operation: 'context_build',
      catalog: 'discover',
      ai_classification: true,
    });
  });

  it('el borrador se carga en el editor sin guardarse', async () => {
    let polls = 0;
    const markdown = '---\ndomains:\n- slug: facturas\n  name: Facturas\n---\n';
    const fetchMock = stubApi({
      ...BASE,
      ...status({ litellm_taxonomy_manifest_draft: true }),
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
      ...status({ litellm_taxonomy_manifest_draft: true }),
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

    await user.click(await screen.findByRole('button', { name: 'Pedir borrador' }));

    expect(await screen.findByText(/rechazó la clave del borrador/)).toBeInTheDocument();
  });
});
