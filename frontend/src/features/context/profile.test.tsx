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

const TEMPLATES = {
  items: [{ name: 'calidad', title: 'Calidad', description: null, builtin: true, updated_at: null }],
};
const NO_PROFILE = { markdown: null, sections: null, etag: 'none' };
const PROFILE = {
  markdown: '## Glosario\n- POB: plan de obra sintético.',
  sections: { glossary: '- POB: plan de obra sintético.', examples: [] },
  etag: 'p1',
};
const NO_AI = {
  'GET /api/v1/ai/status': {
    body: {
      families: { litellm: false },
      tasks: { classify: false, enrich: false, taxonomy_design: false, agent: false, embed: false },
    },
  },
};

function routes(profile: object, extra: Record<string, unknown> = {}) {
  return {
    ...session(USER),
    ...NO_AI,
    'GET /api/v1/projects/7': { body: PROJECT },
    'GET /api/v1/projects/7/context': NOT_BUILT,
    'GET /api/v1/projects/7/context/taxonomy-manifest': { body: MANIFEST },
    'GET /api/v1/projects/7/context/taxonomy-manifest/versions': { body: { items: [], limit: 5 } },
    'GET /api/v1/taxonomy-templates': { body: TEMPLATES },
    'GET /api/v1/projects/7/context/profile': { body: profile },
    ...extra,
  } as Parameters<typeof stubApi>[0];
}

describe('Perfil del proyecto', () => {
  it('con plantilla, guarda el perfil con If-Match y muestra la vista previa del borrador', async () => {
    const fetchMock = stubApi(
      routes(NO_PROFILE, {
        'PUT /api/v1/projects/7/context/profile': {
          body: { markdown: '## Glosario\n- POB', sections: { glossary: '- POB', examples: [] }, etag: 'p1' },
        },
        'POST /api/v1/projects/7/context/prompt-preview': { body: PREVIEW },
      }),
    );
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    // Por carpetas, sin IA y sin perfil guardado: no se ve (D1).
    await screen.findByRole('radio', { name: 'Por carpetas' });
    await waitFor(() =>
      expect(callsTo(fetchMock, 'GET', '/api/v1/projects/7/context/profile')).toHaveLength(1),
    );
    expect(screen.queryByRole('region', { name: 'Perfil del proyecto' })).not.toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: 'Plantilla' }));
    const card = await screen.findByRole('region', { name: 'Perfil del proyecto' });
    expect(within(card).getByRole('button', { name: 'Vista previa del prompt' })).toBeDisabled();
    await user.click(screen.getByRole('combobox', { name: 'Plantilla' }));
    await user.click(await screen.findByRole('option', { name: 'Calidad (calidad)', hidden: true }));
    await user.type(within(card).getByRole('textbox', { name: /^Perfil/ }), '## Glosario{enter}- POB');
    await user.click(within(card).getByRole('button', { name: 'Vista previa del prompt' }));

    expect(await within(card).findByText(/POB: plan de obra sintético/)).toBeInTheDocument();
    expect(within(card).getByText('Con perfil del proyecto')).toBeInTheDocument();
    const [previewRequest] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/context/prompt-preview');
    expect(await previewRequest?.clone().json()).toEqual({
      catalog: 'template',
      template_name: 'calidad',
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

  it('por carpetas se ve si ya existe, aunque no haya IA: la librería lo sigue usando', async () => {
    stubApi(routes(PROFILE));

    renderRoute('/projects/7/context');

    const card = await screen.findByRole('region', { name: 'Perfil del proyecto' });
    expect(within(card).getByRole('textbox', { name: /^Perfil/ })).toHaveValue(PROFILE.markdown);
    expect(within(card).getByText(/no hay perfil de taxonomía/)).toBeInTheDocument();
  });

  it('con el manifiesto, un perfil aparte sale como aviso y se copia al cuerpo sin guardar', async () => {
    const fetchMock = stubApi(routes(PROFILE));
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    await user.click(await screen.findByRole('radio', { name: 'Manifiesto del proyecto' }));
    const notice = await screen.findByRole('region', { name: 'Perfil del proyecto' });
    expect(within(notice).getByText('Este proyecto tiene además un perfil aparte')).toBeInTheDocument();
    expect(within(notice).queryByRole('textbox')).not.toBeInTheDocument();
    await user.click(within(notice).getByRole('button', { name: 'Copiar al cuerpo del manifiesto' }));

    const editor = await screen.findByRole('textbox', { name: /^Markdown \(front matter/ });
    expect(editor).toHaveValue(`${MANIFEST.markdown.trimEnd()}\n\n${PROFILE.markdown}\n`);
    expect(callsTo(fetchMock, 'PUT', '/api/v1/projects/7/context/taxonomy-manifest')).toHaveLength(0);
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/projects/7/context/profile')).toHaveLength(0);

    await user.click(screen.getByRole('button', { name: 'Ver el perfil' }));
    expect(
      await within(screen.getByRole('region', { name: 'Perfil del proyecto' })).findByRole('textbox', {
        name: /^Perfil/,
      }),
    ).toHaveValue(PROFILE.markdown);
  });

  it('con el manifiesto y sin perfil aparte, no se ve', async () => {
    const fetchMock = stubApi(routes(NO_PROFILE));
    const user = userEvent.setup();

    renderRoute('/projects/7/context');

    await user.click(await screen.findByRole('radio', { name: 'Manifiesto del proyecto' }));
    await screen.findByRole('textbox', { name: /^Markdown \(front matter/ });
    await waitFor(() =>
      expect(callsTo(fetchMock, 'GET', '/api/v1/projects/7/context/profile')).toHaveLength(1),
    );
    expect(screen.queryByRole('region', { name: 'Perfil del proyecto' })).not.toBeInTheDocument();
  });
});
