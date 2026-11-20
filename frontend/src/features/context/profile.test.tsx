import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

// W3 (D11): perfil propio del proyecto y vista previa del prompt sin llamar al modelo. Datos sintéticos.
const NOT_BUILT = {
  status: 404,
  body: { title: 'Contexto no encontrado', status: 404, code: 'context_not_found' },
};
const MANIFEST = {
  markdown: '---\nschema: 2\naxes: []\n---\n',
  error: null,
  domains: [],
  material_types: [],
  etag: 'm1',
  last_changed_at: null,
};
const PREVIEW = {
  messages: [
    { role: 'system', content: 'Instrucciones sintéticas\n## Glosario\n- POB: plan de obra sintético.' },
    { role: 'user', content: '<<<DOCUMENTO\n(aquí va el extracto de cada documento)\nDOCUMENTO>>>' },
  ],
  template_profile: null,
  project_profile: {
    context: null,
    tie_breakers: null,
    glossary: '- POB: plan de obra sintético.',
    examples: [],
  },
  profile: { context: null, tie_breakers: null, glossary: '- POB: plan de obra sintético.', examples: [] },
};

describe('Perfil del proyecto', () => {
  it('guarda el perfil con If-Match y muestra la vista previa del borrador', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': NOT_BUILT,
      'GET /api/v1/projects/7/context/taxonomy-manifest': { body: MANIFEST },
      'GET /api/v1/projects/7/context/taxonomy-manifest/versions': { body: { items: [], limit: 5 } },
      'GET /api/v1/taxonomy-templates': { body: { items: [] } },
      'GET /api/v1/projects/7/context/profile': { body: { markdown: null, sections: null, etag: 'none' } },
      'PUT /api/v1/projects/7/context/profile': {
        body: { markdown: '## Glosario\n- POB', sections: { glossary: '- POB', examples: [] }, etag: 'p1' },
      },
      'POST /api/v1/projects/7/context/prompt-preview': { body: PREVIEW },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    const card = await screen.findByRole('region', { name: 'Perfil del proyecto' });
    const preview = within(card).getByRole('button', { name: 'Vista previa del prompt' });
    expect(preview).toBeDisabled(); // «Descubrir dominios» no tiene catálogo de ejes
    await user.click(screen.getByText('Manifiesto del proyecto', { exact: true }));
    await user.type(within(card).getByRole('textbox', { name: /^Perfil/ }), '## Glosario{enter}- POB');
    await user.click(within(card).getByRole('button', { name: 'Vista previa del prompt' }));

    expect(await within(card).findByText(/POB: plan de obra sintético/)).toBeInTheDocument();
    expect(within(card).getByText('Con perfil del proyecto')).toBeInTheDocument();
    const [previewRequest] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/context/prompt-preview');
    expect(await previewRequest?.clone().json()).toEqual({
      catalog: 'manifest',
      template_name: null,
      profile_markdown: '## Glosario\n- POB',
    });

    await user.click(within(card).getByRole('button', { name: 'Guardar perfil' }));
    await waitFor(() =>
      expect(callsTo(fetchMock, 'PUT', '/api/v1/projects/7/context/profile')).toHaveLength(1),
    );
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/projects/7/context/profile');
    expect(request?.headers.get('if-match')).toBe('none');
    expect(await within(card).findByText('Perfil guardado.')).toBeInTheDocument();
  });
});
