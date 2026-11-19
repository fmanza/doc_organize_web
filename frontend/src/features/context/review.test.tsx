import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT } from '../../test/fixtures';
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
