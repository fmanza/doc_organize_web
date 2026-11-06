import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';
import { joinRelative, renderMarkdown } from './renderMarkdown';
import { snippetParts } from './useDocuments';

const PROJECT_ROUTES = { 'GET /api/v1/projects/7': { body: PROJECT } };

/** `fetch` de la API más `/outputs`, que devuelve texto (no JSON) como el visor real. */
function stubWithOutput(routes: Parameters<typeof stubApi>[0], text: string) {
  const base = stubApi(routes);
  const fetchMock = vi.fn(async (request: Request) =>
    new URL(request.url).pathname.endsWith('/outputs')
      ? new Response(text, { headers: { 'Content-Type': 'text/markdown; charset=utf-8' } })
      : base(request),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('renderMarkdown', () => {
  it('quita todo lo ejecutable y las peticiones a otros sitios', () => {
    const html = renderMarkdown(
      [
        '# Título',
        '<script>alert(1)</script>',
        '<img src="x" onerror="alert(1)">',
        '[malo](javascript:alert(1)) [web](https://example.org) [local](otro.md)',
        '![externa](https://tracker.example.org/p.png) ![dato](data:image/png;base64,AAAA)',
        '![página](img/factura/p1.png)',
        '<iframe src="https://example.org"></iframe><form><input></form><p style="color:red">texto</p>',
      ].join('\n\n'),
      (relative) => `/visor?path=${relative}`,
    );
    const doc = new DOMParser().parseFromString(`<div>${html}</div>`, 'text/html');

    expect(doc.querySelector('script, iframe, form, input, [style], [onerror]')).toBeNull();
    expect(html).not.toContain('javascript:');
    expect(doc.querySelector('a[href="https://example.org"]')?.getAttribute('rel')).toBe(
      'noopener noreferrer',
    );
    expect(doc.querySelectorAll('a[href]')).toHaveLength(1);
    expect(Array.from(doc.querySelectorAll('img')).map((img) => img.getAttribute('src'))).toEqual([
      '/visor?path=x',
      '/visor?path=img/factura/p1.png',
    ]);
    expect(doc.body.textContent).toContain('externa');
  });

  it('resuelve rutas relativas sin salir de Conversión/', () => {
    expect(joinRelative('2024/facturas/enero.md', 'img/enero/p1.png')).toBe('2024/facturas/img/enero/p1.png');
    expect(joinRelative('2024/a.md', './img/../img/a/p.png')).toBe('2024/img/a/p.png');
    expect(joinRelative('2024/a.md', '../../fuera.png')).toBeNull();
  });

  it('separa las coincidencias de la búsqueda sin interpretar HTML', () => {
    expect(snippetParts('…la \u0002luz\u0003 de <b>enero</b>')).toEqual([
      { text: '…la ', match: false },
      { text: 'luz', match: true },
      { text: ' de <b>enero</b>', match: false },
    ]);
  });
});

describe('DocumentsPage', () => {
  it('muestra el total y lanza una exportación como ejecución', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      ...PROJECT_ROUTES,
      'GET /api/v1/projects/7/documents': {
        body: {
          items: [
            {
              folder: '2024',
              path: 'factura.pdf',
              status: 'new',
              conversion_status: 'success',
              error_message: null,
              error_retry_count: 0,
              updated_at: '2026-11-01T08:00:00Z',
              output_path: '2024/factura.md',
            },
          ],
          total: 1,
        },
      },
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ operation: 'export_xlsx', params: { operation: 'export_xlsx', kind: 'errors' } }),
      },
      'GET /api/v1/runs/11111111-1111-4111-8111-111111111111': {
        body: runOut({ operation: 'export_xlsx' }),
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/documents');

    expect(await screen.findByText('1 documento.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Excel de errores' }));
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const body: unknown = await callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')[0]?.json();
    expect(body).toEqual({ operation: 'export_xlsx', kind: 'errors' });
  });

  it('busca por nombre en el servidor', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      ...PROJECT_ROUTES,
      'GET /api/v1/projects/7/documents': { body: { items: [], total: 0 } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/documents');

    expect(await screen.findByText(/Aún no hay documentos/)).toBeInTheDocument();
    await user.type(screen.getByRole('textbox', { name: 'Buscar por nombre o subcarpeta' }), 'enero');
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/projects/7/documents').some(
          (request) => new URL(request.url).searchParams.get('search') === 'enero',
        ),
      ).toBe(true),
    );
    expect(await screen.findByText('Ningún documento coincide con la búsqueda.')).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Estado' }));
    await user.click(await screen.findByRole('option', { name: 'Error', hidden: true }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/projects/7/documents').some(
          (request) => new URL(request.url).searchParams.get('conversion_status') === 'error',
        ),
      ).toBe(true),
    );
  });
});

describe('DocumentViewerPage', () => {
  it('pinta el Markdown saneado con sus imágenes desde el visor', async () => {
    stubWithOutput(
      { ...session(USER), ...PROJECT_ROUTES },
      '# Factura de enero\n\n<script>window.hacked = true</script>\n\n![página](img/factura/p1.png)',
    );

    renderRoute(`/projects/7/documents/view?path=${encodeURIComponent('2024/factura.md')}`);

    expect(await screen.findByRole('heading', { name: 'Factura de enero' })).toBeInTheDocument();
    expect(document.querySelector('script:not([src])')).toBeNull();
    expect(screen.getByRole('img', { name: 'página' })).toHaveAttribute(
      'src',
      `/api/v1/projects/7/outputs?path=${encodeURIComponent('2024/img/factura/p1.png')}`,
    );
  });
});

describe('ContentSearchPage', () => {
  it('muestra los fragmentos con las coincidencias marcadas', async () => {
    stubApi({
      ...session(USER),
      ...PROJECT_ROUTES,
      'GET /api/v1/projects/7/search': {
        body: {
          items: [
            { output_path: '2024/factura.md', title: 'Factura', snippet: 'Importe de la \u0002luz\u0003.' },
          ],
          total: 1,
          indexed_at: '2026-11-01T08:00:00Z',
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/search');

    await user.type(await screen.findByRole('textbox', { name: /Palabras/ }), 'luz');
    expect(await screen.findByRole('link', { name: 'Factura' })).toHaveAttribute(
      'href',
      `/projects/7/documents/view?path=${encodeURIComponent('2024/factura.md')}`,
    );
    expect(screen.getByText('luz', { selector: 'mark' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Actualizar la búsqueda' })).toBeInTheDocument();
  });
});

describe('Fase 10: documentos por páginas', () => {
  it('pagina en el servidor, recuerda la página en la URL y vuelve a la 1 al buscar', async () => {
    const row = (index: number) => ({
      folder: '2024',
      path: `doc-${index}.pdf`,
      status: 'new',
      conversion_status: 'success',
      error_message: null,
      error_retry_count: 0,
      updated_at: '2026-11-01T08:00:00Z',
      output_path: `2024/doc-${index}.md`,
    });
    const fetchMock = stubApi({
      ...session(USER),
      ...PROJECT_ROUTES,
      'GET /api/v1/projects/7/documents': (request) => {
        const offset = Number(new URL(request.url).searchParams.get('offset'));
        return { body: { items: [row(offset)], total: 120 } };
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/documents?page=2');

    // 1.2.0: 25 filas por página.
    expect(await screen.findByText('doc-25.pdf')).toBeInTheDocument();
    expect(screen.getByText('26–50 de 120')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Página 3' }));
    expect(await screen.findByText('doc-50.pdf')).toBeInTheDocument();

    await user.type(screen.getByRole('textbox', { name: 'Buscar por nombre o subcarpeta' }), 'x');
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/projects/7/documents').some((request) => {
          const params = new URL(request.url).searchParams;
          return params.get('search') === 'x' && params.get('offset') === '0';
        }),
      ).toBe(true),
    );

    // web 1.3.0 (G40): «Ordenar por» manda el orden a la API; el botón cambia el sentido.
    await user.click(screen.getByRole('combobox', { name: 'Ordenar por' }));
    await user.click(await screen.findByRole('option', { name: 'Fallos seguidos', hidden: true }));
    await user.click(screen.getByRole('button', { name: /Orden ascendente/ }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/projects/7/documents').some((request) => {
          const params = new URL(request.url).searchParams;
          return params.get('sort') === 'error_retry_count' && params.get('order') === 'desc';
        }),
      ).toBe(true),
    );
  });
});

it('una página de la URL que ya no existe deja volver a la primera', async () => {
  stubApi({
    ...session(USER),
    ...PROJECT_ROUTES,
    'GET /api/v1/projects/7/documents': (request) => ({
      body: {
        items:
          new URL(request.url).searchParams.get('offset') === '0'
            ? [
                {
                  folder: '2024',
                  path: 'unico.pdf',
                  status: 'new',
                  conversion_status: 'success',
                  error_message: null,
                  error_retry_count: 0,
                  updated_at: '2026-11-01T08:00:00Z',
                  output_path: '2024/unico.md',
                },
              ]
            : [],
        total: 1,
      },
    }),
  });
  const user = userEvent.setup();

  renderRoute('/projects/7/documents?page=9');

  await user.click(await screen.findByRole('button', { name: 'Página 1' }));
  expect(await screen.findByText('unico.pdf')).toBeInTheDocument();
});
