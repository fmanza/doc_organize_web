import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

// W7: diseñar la taxonomía con IA (agente) y comprobar por reglas. Datos sintéticos.
const RUN_ID = '77777777-7777-4777-8777-777777777777';
const SAVED = '---\nschema: 2\naxes: []\n---\n';
const PROPOSAL = '---\nschema: 2\ntitle: Propuesta sintética\naxes: []\n---\n';
const report = (coverage: number, conflicts: number) => ({
  axes: [{ axis: 'domains', documents: 4, covered: 3, conflicts, empty_entries: [], unused_keywords: {} }],
  documents: 4,
  coverage: { domains: coverage },
  markdown: '| Eje |',
});
const RESULT = {
  stop_reason: 'finished',
  finished: true,
  steps: 3,
  tool_calls: 3,
  prompt_tokens: 900,
  completion_tokens: 100,
  max_steps: 30,
  documents: 4,
  improves: true,
  rationale: 'Añado una entrada sintética.',
  edits: 1,
  markdown: PROPOSAL,
  draft_markdown: null,
  best_markdown: null,
  base_report: report(0.5, 1),
  report: report(0.75, 0),
  best_report: null,
};

describe('Diseñar taxonomía con IA', () => {
  it('lanza el agente, enseña la propuesta y la carga en el editor sin guardarla', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': {
        status: 404,
        body: { title: 'Contexto no encontrado', status: 404, code: 'context_not_found' },
      },
      'GET /api/v1/projects/7/context/taxonomy-manifest': {
        body: {
          markdown: SAVED,
          error: null,
          domains: [],
          material_types: [],
          etag: 'e1',
          last_changed_at: null,
        },
      },
      'GET /api/v1/projects/7/context/taxonomy-manifest/versions': { body: { items: [], limit: 5 } },
      'GET /api/v1/projects/7/context/profile': { body: { markdown: null, sections: null, etag: 'none' } },
      'GET /api/v1/taxonomy-templates': { body: { items: [] } },
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'taxonomy_agent' }),
      },
      [`GET /api/v1/runs/${RUN_ID}`]: {
        body: runOut({ id: RUN_ID, operation: 'taxonomy_agent', status: 'succeeded', result: RESULT }),
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');
    await user.click(await screen.findByRole('radio', { name: 'Manifiesto del proyecto' }));
    const panel = await screen.findByRole('region', { name: 'Diseñar taxonomía con IA (agente)' });
    await user.type(within(panel).getByRole('textbox', { name: /Indicaciones/ }), 'Separa obras');
    await user.click(within(panel).getByRole('button', { name: 'Diseñar con IA' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toEqual({
      operation: 'taxonomy_agent',
      catalog: 'manifest',
      template_name: null,
      instructions: 'Separa obras',
      max_steps: 30,
    });
    expect(await within(panel).findByText('Mejora el de partida')).toBeInTheDocument();
    expect(within(panel).getByText('Añado una entrada sintética.')).toBeInTheDocument();
    expect(within(panel).getByText('75 %')).toBeInTheDocument();

    await user.click(within(panel).getByRole('button', { name: 'Cargar la propuesta en el editor' }));
    const dialog = screen.queryByRole('dialog');
    if (dialog) {
      await user.click(within(dialog).getByRole('button', { name: /Sustituir|Continuar|Aceptar/ }));
    }
    expect(await screen.findByRole('textbox', { name: /^Markdown \(front matter/ })).toHaveValue(PROPOSAL);
    expect(callsTo(fetchMock, 'PUT', '/api/v1/projects/7/context/taxonomy-manifest')).toHaveLength(0);
  });
});
