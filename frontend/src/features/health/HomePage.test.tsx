import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../../test/api';
import { renderRoute } from '../../test/render';

describe('HomePage', () => {
  it('muestra el estado y las versiones cuando la API responde', async () => {
    const fetchMock = stubApi(session(ADMIN));

    renderRoute('/');

    expect(await screen.findByText('Servicio operativo')).toBeInTheDocument();
    expect(screen.getByText('0.9.3')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'GET', '/api/health')).toHaveLength(1);
  });

  it('muestra el servicio degradado con un 503', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/health': {
        status: 503,
        body: { status: 'degraded', version: '0.2.0', doc_organize_version: null, database: 'error' },
      },
    });

    renderRoute('/');

    expect(await screen.findByText('Servicio degradado')).toBeInTheDocument();
    expect(screen.getByText('no instalada')).toBeInTheDocument();
    expect(screen.getByText('sin respuesta')).toBeInTheDocument();
  });

  it('avisa si la API no responde', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/health': { status: 500, body: { title: 'Error interno', status: 500 } },
    });

    renderRoute('/');

    expect(await screen.findByText('No se puede contactar con la API')).toBeInTheDocument();
  });

  it('muestra la página 404 de la SPA en rutas desconocidas', async () => {
    stubApi(session(ADMIN));

    renderRoute('/no-existe');

    expect(await screen.findByText('Página no encontrada')).toBeInTheDocument();
  });
});
