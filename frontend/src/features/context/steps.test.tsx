import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { session, stubApi, USER } from '../../test/api';
import { PROJECT } from '../../test/fixtures';
import { renderRoute } from '../../test/render';
import { appendProfile, profileMode, resolveStep, selectionNotReady } from './useContext';

// Contexto en pasos (2026-11-22). Datos sintéticos.
const CONTEXT = {
  output_folder_name: 'organizado',
  catalog_kind: 'manifest',
  taxonomy_template_name: null,
  documents_count: 3,
  unclassified_count: 0,
  failed_count: 0,
  site_built: true,
  domains: [],
  built_by_run_id: null,
  built_at: '2026-11-22T09:00:00Z',
};
const MANIFEST = {
  markdown: '---\nschema: 2\naxes: []\n---\n',
  error: null,
  domains: [],
  material_types: [],
  etag: 'm1',
  last_changed_at: null,
};

describe('Pasos del contexto', () => {
  it('resuelve el paso de la URL con y sin contexto y sin permiso', () => {
    expect(resolveStep(null, false, true)).toBe('taxonomia');
    expect(resolveStep(null, true, true)).toBe('resultado');
    expect(resolveStep('entregar', false, true)).toBe('taxonomia');
    expect(resolveStep('entregar', true, true)).toBe('entregar');
    expect(resolveStep('construir', true, false)).toBe('resultado');
    expect(resolveStep('historial', false, false)).toBe('historial');
    expect(resolveStep('otro', true, true)).toBe('resultado');
  });

  it('explica por qué todavía no se puede construir', () => {
    expect(selectionNotReady({ catalog: 'domains', template: null }, [], false)).toBe('domains');
    expect(selectionNotReady({ catalog: 'domains', template: null }, ['obras'], false)).toBeNull();
    expect(selectionNotReady({ catalog: 'template', template: null }, [], false)).toBe('template');
    expect(selectionNotReady({ catalog: 'manifest', template: null }, [], true)).toBe('unsavedManifest');
    expect(selectionNotReady({ catalog: 'discover', template: null }, [], true)).toBeNull();
  });

  it('decide cómo se ve el perfil según el catálogo (D1)', () => {
    expect(profileMode('template', false, false)).toBe('full');
    expect(profileMode('discover', false, false)).toBe('hidden');
    expect(profileMode('discover', true, false)).toBe('full');
    expect(profileMode('domains', false, true)).toBe('full');
    expect(profileMode('manifest', true, false)).toBe('hidden');
    expect(profileMode('manifest', false, true)).toBe('manifestNotice');
    expect(appendProfile('a\n\n', '  b  ')).toBe('a\n\nb\n');
  });

  it('avisa al salir con el manifiesto sin guardar; cambiar de paso no avisa', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context': { body: CONTEXT },
      'GET /api/v1/projects/7/context/documents': { body: { items: [], total: 0 } },
      'GET /api/v1/projects/7/context/taxonomy-manifest': { body: MANIFEST },
      'GET /api/v1/projects/7/context/taxonomy-manifest/versions': { body: { items: [], limit: 5 } },
      'GET /api/v1/projects/7/context/profile': { body: { markdown: null, sections: null, etag: 'none' } },
      'GET /api/v1/taxonomy-templates': { body: { items: [] } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context?paso=taxonomia');

    const editor = await screen.findByRole('textbox', { name: /^Markdown \(front matter/ });
    await user.type(editor, 'z');
    // Otro paso de la misma página: sin aviso y sin perder el borrador.
    await user.click(screen.getByRole('link', { name: '3. Resultado' }));
    expect(screen.queryByRole('dialog', { name: 'Cambios sin guardar' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('link', { name: '1. Taxonomía' }));
    expect(await screen.findByRole('textbox', { name: /^Markdown \(front matter/ })).toHaveValue(
      `${MANIFEST.markdown}z`,
    );

    // Otra página: avisa; «Seguir editando» se queda.
    await user.click(screen.getByRole('link', { name: '4. Revisar' }));
    const dialog = await screen.findByRole('dialog', { name: 'Cambios sin guardar' });
    await user.click(within(dialog).getByRole('button', { name: 'Seguir editando' }));
    expect(screen.getByRole('textbox', { name: /^Markdown \(front matter/ })).toHaveValue(
      `${MANIFEST.markdown}z`,
    );

    // «Salir sin guardar» sale.
    await user.click(screen.getByRole('link', { name: '4. Revisar' }));
    await user.click(
      within(await screen.findByRole('dialog', { name: 'Cambios sin guardar' })).getByRole('button', {
        name: 'Salir sin guardar',
      }),
    );
    expect(await screen.findByRole('heading', { name: 'Revisar clasificación' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '4. Revisar' })).toHaveAttribute('aria-current', 'page');
  });
});
