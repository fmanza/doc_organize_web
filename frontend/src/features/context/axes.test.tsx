import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

// W3 (doc_organize 2.0): filtros por eje con recuentos, insignias con quién asignó cada valor, evidencia y procedencia.
const CONTEXT = {
  output_folder_name: 'organizado',
  catalog_kind: 'template',
  taxonomy_template_name: 'normas',
  documents_count: 1,
  unclassified_count: 0,
  failed_count: 0,
  collisions_count: 0,
  site_built: false,
  domains: [{ slug: 'calidad', name: 'Calidad', description: null, status: 'borrador', documents: 1 }],
  taxonomy_axes: [
    {
      key: 'domains',
      name: 'Dominios',
      description: null,
      multiple: false,
      organizes: 'folder',
      values: [{ slug: 'calidad', name: 'Calidad', documents: 1 }],
    },
    {
      key: 'marcos',
      name: 'Marcos normativos',
      description: null,
      multiple: true,
      organizes: null,
      values: [
        { slug: 'marco-a', name: 'Marco A', documents: 1 },
        { slug: 'marco-b', name: 'Marco B', documents: 0 },
      ],
    },
  ],
  ai_provenance: [
    { task: 'classify', prompt_id: 'classify', version: '4', source: 'builtin', model: 'modelo-sintetico' },
  ],
  built_by_run_id: null,
  built_at: '2026-11-20T08:00:00Z',
};
const DOCUMENT = {
  title: 'Procedimiento sintético',
  domain_slug: 'calidad',
  document_type: 'pdf',
  material_type: null,
  material_type_name: null,
  folder: '2024',
  path: 'procedimiento.pdf',
  organized_path: null,
  failed: false,
  collision: false,
  output_path: null,
  keywords: [],
  ai_filled: [],
  axes: {
    domains: [{ slug: 'calidad', name: 'Calidad', confidence: 0.9, classified_by: 'rules' }],
    marcos: [
      {
        slug: 'marco-a',
        name: 'Marco A',
        confidence: 0.8,
        classified_by: 'ai',
        evidence: 'según el marco A sintético',
        evidence_verified: false,
      },
      { slug: 'marco-b', name: 'Marco B', confidence: 1, classified_by: 'human' },
    ],
  },
};

describe('ContextPage por ejes', () => {
  it('filtra por eje y muestra insignias, evidencia y procedencia', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': { body: CONTEXT },
      'GET /api/v1/projects/7/context/documents': { body: { items: [DOCUMENT], total: 1 } },
      'GET /api/v1/taxonomy-templates': { body: { items: [] } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    expect(await screen.findByText('Procedimiento sintético')).toBeInTheDocument();
    expect(screen.getByText('Marco A · IA')).toBeInTheDocument();
    expect(screen.getByText('Marco B · Persona')).toBeInTheDocument();
    expect(screen.queryByText(/Calidad · /)).not.toBeInTheDocument(); // el dominio ya se ve en la tabla
    expect(screen.getByText(/«según el marco A sintético»/)).toBeInTheDocument();
    expect(screen.getByText('Cita no encontrada en el texto')).toBeInTheDocument();
    expect(
      screen.getByText(
        /prompt classify \(versión 4, incluido en doc_organize\) y el modelo modelo-sintetico/,
      ),
    ).toBeInTheDocument();

    await user.click(screen.getByLabelText('Marcos normativos', { selector: 'input:not([type=hidden])' }));
    await user.click(await screen.findByRole('option', { name: 'Marco A (1)', hidden: true }));

    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/projects/7/context/documents').some(
          (request) => new URL(request.url).searchParams.getAll('axis').join() === 'marcos:marco-a',
        ),
      ).toBe(true),
    );
  });
});
