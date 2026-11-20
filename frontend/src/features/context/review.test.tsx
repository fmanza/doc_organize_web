import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

// W5 (F6): cola de revisión y decisiones de personas. Datos sintéticos.
const CONTEXT = {
  output_folder_name: 'organizado',
  catalog_kind: 'template',
  taxonomy_template_name: 'ejes',
  documents_count: 1,
  unclassified_count: 1,
  failed_count: 0,
  collisions_count: 0,
  site_built: false,
  domains: [{ slug: 'facturas', name: 'Facturas', description: null, status: 'borrador', documents: 1 }],
  taxonomy_axes: [
    {
      key: 'domains',
      name: 'Dominios',
      description: null,
      multiple: false,
      organizes: 'folder',
      values: [
        { slug: 'facturas', name: 'Facturas', documents: 1 },
        { slug: 'informes', name: 'Informes', documents: 0 },
      ],
    },
  ],
  ai_provenance: [],
  built_by_run_id: null,
  built_at: '2026-11-20T08:00:00Z',
};
const ITEM = {
  id: 1,
  document_key: '2025/receta.txt',
  reason: 'unclassified',
  priority: 1,
  axis: 'domains',
  value: null,
  confidence: null,
  detail: 'below_threshold',
  document: {
    seq: 3,
    title: 'Receta sintética',
    folder: '2025',
    path: 'receta.txt',
    domain_slug: null,
    output_path: null,
    version: null,
    version_group: null,
    is_current: null,
    axes: {},
  },
  decision: null,
};
const DECISION = {
  id: 'd1',
  document_key: '2025/receta.txt',
  action: 'set_axis',
  axes: { domains: ['informes'] },
  author: 'ana',
  decided_at: '2026-11-20T09:00:00+00:00',
  reason: null,
};

describe('Revisar clasificación', () => {
  it('fija el eje de un documento y revoca una decisión', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': { body: CONTEXT },
      'GET /api/v1/projects/7/context/review': {
        body: { items: [ITEM], total: 1, counts: { unclassified: 1 } },
      },
      'GET /api/v1/projects/7/context/decisions': {
        body: { decisions: [DECISION], revoked: [], stale: [], orphan: [], applied: 0 },
      },
      'POST /api/v1/projects/7/context/decisions': { status: 201, body: DECISION },
      'POST /api/v1/projects/7/context/decisions/d1/revoke': { status: 204, body: null },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context/review');

    expect(await screen.findByText('Receta sintética')).toBeInTheDocument();
    expect(screen.getByText('Sin clasificar')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Cambiar…' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('combobox', { name: 'Valor' }));
    await user.click(await screen.findByRole('option', { name: 'Informes', hidden: true }));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() =>
      expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/context/decisions')).toHaveLength(1),
    );
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/context/decisions');
    expect(await request?.clone().json()).toEqual({
      document_key: '2025/receta.txt',
      action: 'set_axis',
      axes: { domains: ['informes'] },
      reason: null,
    });

    const decisions = screen.getByRole('region', { name: 'Decisiones' });
    await user.click(
      within(decisions).getByRole('button', { name: 'Revocar la decisión de 2025/receta.txt' }),
    );
    await waitFor(() =>
      expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/context/decisions/d1/revoke')).toHaveLength(1),
    );
  });
});

// W7 (M9): propuestas del revisor; se guardan sin aplicarse y una persona las acepta o descarta.
const RUN_ID = '88888888-8888-4888-8888-888888888888';
const PROPOSAL = {
  id: 5,
  document_key: '2025/receta.txt',
  action: 'set_axis',
  axes: { domains: ['informes'] },
  rationale: 'Habla de un informe sintético.',
  evidence: 'informe',
  created_at: '2026-11-20T10:00:00Z',
  run_id: RUN_ID,
  document: ITEM.document,
};
const AGENT_RESULT = {
  stop_reason: 'finished',
  finished: true,
  steps: 3,
  tool_calls: 3,
  prompt_tokens: 500,
  completion_tokens: 50,
  max_steps: 40,
  reviewed: 1,
  summary: 'Propongo lo que veo claro.',
  proposals: 1,
};

describe('Propuestas del revisor', () => {
  it('pide propuestas, acepta una y descarta otra', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': { body: CONTEXT },
      'GET /api/v1/projects/7/context/review': {
        body: { items: [], total: 0, counts: { reviewer_proposal: 2 } },
      },
      'GET /api/v1/projects/7/context/review/proposals': {
        body: {
          items: [
            PROPOSAL,
            {
              ...PROPOSAL,
              id: 6,
              document_key: '2024/otro.txt',
              action: 'exclude',
              axes: {},
              rationale: 'Sobra.',
              evidence: null,
              document: null,
            },
          ],
        },
      },
      'GET /api/v1/projects/7/context/decisions': {
        body: { decisions: [], revoked: [], stale: [], orphan: [], applied: 0 },
      },
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'context_review_agent' }),
      },
      [`GET /api/v1/runs/${RUN_ID}`]: {
        body: runOut({
          id: RUN_ID,
          operation: 'context_review_agent',
          status: 'succeeded',
          result: AGENT_RESULT,
        }),
      },
      'POST /api/v1/projects/7/context/review/proposals/5/accept': { body: DECISION },
      'POST /api/v1/projects/7/context/review/proposals/6/discard': { status: 204, body: null },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context/review');
    const card = await screen.findByRole('region', { name: 'Propuestas del revisor (IA)' });
    expect(await within(card).findByText('Habla de un informe sintético.')).toBeInTheDocument();
    expect(within(card).getByText('Cambiar eje · Dominios: informes')).toBeInTheDocument();
    expect(within(card).getByText('El documento ya no está en el contexto.')).toBeInTheDocument();

    await user.click(within(card).getByRole('button', { name: 'Pedir propuestas' }));
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toEqual({
      operation: 'context_review_agent',
      max_items: 20,
      max_steps: 40,
      instructions: '',
    });
    expect(await within(card).findByText('Propongo lo que veo claro.')).toBeInTheDocument();

    await user.click(within(card).getByRole('button', { name: 'Aceptar la propuesta para 2025/receta.txt' }));
    await waitFor(() =>
      expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/context/review/proposals/5/accept')).toHaveLength(
        1,
      ),
    );
    await user.click(within(card).getByRole('button', { name: 'Descartar la propuesta para 2024/otro.txt' }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'POST', '/api/v1/projects/7/context/review/proposals/6/discard'),
      ).toHaveLength(1),
    );
  });
});
