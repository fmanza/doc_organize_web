import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderRoute } from '../../test/render';

function stubFetch(status: number, body: unknown, contentType = 'application/json') {
  const fetchMock = vi.fn(
    async (_request: Request) =>
      new Response(JSON.stringify(body), { status, headers: { 'Content-Type': contentType } }),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('HomePage', () => {
  it('muestra el estado y las versiones cuando la API responde', async () => {
    const fetchMock = stubFetch(200, {
      status: 'ok',
      version: '0.1.0',
      doc_organize_version: '0.9.3',
      database: 'ok',
    });

    renderRoute('/');

    expect(await screen.findByText('Servicio operativo')).toBeInTheDocument();
    expect(screen.getByText('0.9.3')).toBeInTheDocument();
    expect(fetchMock.mock.calls[0]?.[0].url).toMatch(/\/api\/health$/);
  });

  it('muestra el servicio degradado con un 503', async () => {
    stubFetch(503, { status: 'degraded', version: '0.1.0', doc_organize_version: null, database: 'error' });

    renderRoute('/');

    expect(await screen.findByText('Servicio degradado')).toBeInTheDocument();
    expect(screen.getByText('no instalada')).toBeInTheDocument();
    expect(screen.getByText('sin respuesta')).toBeInTheDocument();
  });

  it('avisa si la API no responde', async () => {
    stubFetch(500, { title: 'Error interno', status: 500 }, 'application/problem+json');

    renderRoute('/');

    expect(await screen.findByText('No se puede contactar con la API')).toBeInTheDocument();
  });

  it('muestra la página 404 de la SPA en rutas desconocidas', () => {
    stubFetch(200, {});

    renderRoute('/no-existe');

    expect(screen.getByText('Página no encontrada')).toBeInTheDocument();
  });
});
