import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

// W6 (F5): versiones de un documento. Datos sintéticos.
const CONTEXT = {
  output_folder_name: 'organizado',
  catalog_kind: 'template',
  taxonomy_template_name: 'ejes',
  documents_count: 2,
  unclassified_count: 0,
  failed_count: 0,
  collisions_count: 0,
  site_built: false,
  domains: [{ slug: 'obras', name: 'Obras', description: null, status: 'borrador', documents: 2 }],
  versions_mode: 'mark',
  version_groups: [
    {
      key: 'Origen/2024/plan.txt',
      members: ['2024/plan v1.txt', '2024/plan v2.txt'],
      versions: ['1', '2'],
      current: '2024/plan v2.txt',
      confirmed: false,
    },
  ],
  superseded: [],
  superseded_count: 0,
  built_by_run_id: null,
  built_at: '2026-11-20T08:00:00Z',
};
const doc = (path: string, isCurrent: boolean, version: string) => ({
  title: `Plan sintético ${version}`,
  domain_slug: 'obras',
  document_type: 'txt',
  material_type: null,
  material_type_name: null,
  folder: '2024',
  path,
  organized_path: null,
  failed: false,
  collision: false,
  output_path: null,
  keywords: [],
  ai_filled: [],
  version,
  version_group: 'Origen/2024/plan.txt',
  is_current: isCurrent,
});

describe('Versiones de un documento', () => {
  it('muestra el grupo, marca la antigua, filtra las vigentes y decide la vigente', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': { body: CONTEXT },
      'GET /api/v1/projects/7/context/documents': {
        body: { items: [doc('plan v1.txt', false, '1'), doc('plan v2.txt', true, '2')], total: 2 },
      },
      'GET /api/v1/projects/7/context/profile': { body: { markdown: null, sections: null, etag: 'none' } },
      'GET /api/v1/taxonomy-templates': { body: { items: [] } },
      'POST /api/v1/projects/7/context/decisions': {
        status: 201,
        body: {
          id: 'd1',
          document_key: '2024/plan v1.txt',
          action: 'set_current_version',
          axes: {},
          decided_at: '2026-11-20T09:00:00+00:00',
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    const card = await screen.findByRole('region', { name: 'Versiones de un documento' });
    expect(within(card).getByText('Vigente · propuesta')).toBeInTheDocument();
    expect(await screen.findByText('Versión antigua · v1')).toBeInTheDocument();

    await user.click(screen.getByRole('switch', { name: 'Solo vigentes' }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/projects/7/context/documents').some(
          (request) => new URL(request.url).searchParams.get('current') === 'true',
        ),
      ).toBe(true),
    );

    await user.click(within(card).getByRole('button', { name: 'Marcar 2024/plan v1.txt como vigente' }));
    await waitFor(() =>
      expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/context/decisions')).toHaveLength(1),
    );
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/context/decisions');
    expect(await request?.clone().json()).toEqual({
      document_key: '2024/plan v1.txt',
      action: 'set_current_version',
    });
    expect(await within(card).findByText('Decidido: se aplica al reconstruir.')).toBeInTheDocument();
  });
});
