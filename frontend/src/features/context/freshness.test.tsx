import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { session, stubApi, USER } from '../../test/api';
import { PROJECT } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

// W4 (doc_organize 2.0, F4): aviso de frescura del contexto respecto a la caché del último escaneo. Datos sintéticos.
const CONTEXT = {
  output_folder_name: 'organizado',
  catalog_kind: 'discover',
  taxonomy_template_name: null,
  documents_count: 3,
  unclassified_count: 0,
  failed_count: 0,
  site_built: true,
  domains: [{ slug: 'facturas', name: 'Facturas', description: null, status: 'borrador', documents: 3 }],
  built_by_run_id: null,
  built_at: '2026-11-20T08:00:00Z',
};
const STALE = {
  checked_at: '2026-11-20T09:00:00Z',
  up_to_date: false,
  changed: 2,
  added: 1,
  removed: 0,
  unknown: 0,
  stale_site: true,
  examples: { changed: ['2024/a.pdf', '2024/b.pdf'], added: ['2025/c.pdf'], removed: [], unknown: [] },
};

function routes(freshness: unknown) {
  return {
    ...session(USER),
    'GET /api/v1/projects/7': { body: PROJECT },
    'GET /api/v1/projects/7/context': { body: { ...CONTEXT, freshness } },
    'GET /api/v1/projects/7/context/documents': { body: { items: [], total: 0 } },
    'GET /api/v1/projects/7/context/profile': { body: { markdown: null, sections: null, etag: 'none' } },
    'GET /api/v1/taxonomy-templates': { body: { items: [] } },
  };
}

describe('Frescura del contexto', () => {
  it('avisa con recuentos, ejemplos y el enlace para reconstruir', async () => {
    stubApi(routes(STALE));

    renderRoute('/projects/7/context');

    expect(await screen.findByText('El contexto está desactualizado')).toBeInTheDocument();
    expect(
      screen.getByText(
        '2 originales cambiados · 1 documento nuevo sin incluir · el sitio es anterior a la última construcción',
      ),
    ).toBeInTheDocument();
    expect(screen.getByText('Cambiado: 2024/a.pdf')).toBeInTheDocument();
    // El aviso va en la cabecera común y lleva al paso «Construir».
    expect(screen.getByRole('link', { name: 'Ir a reconstruir' })).toHaveAttribute(
      'href',
      '/projects/7/context?paso=construir',
    );
  });

  it('al día, sin aviso', async () => {
    stubApi(routes({ ...STALE, up_to_date: true, changed: 0, added: 0, stale_site: false }));

    renderRoute('/projects/7/context');

    expect((await screen.findAllByText('Facturas')).length).toBeGreaterThan(0);
    expect(screen.queryByText('El contexto está desactualizado')).not.toBeInTheDocument();
  });
});
