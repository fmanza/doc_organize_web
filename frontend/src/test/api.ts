import { vi } from 'vitest';

export interface StubResponse {
  status?: number;
  body?: unknown;
}

type Handler = StubResponse | ((request: Request) => StubResponse | Promise<StubResponse>);

export const ADMIN = { id: 1, username: 'admin', display_name: 'Admin', role: 'admin' } as const;
export const USER = { id: 2, username: 'ana', display_name: 'Ana', role: 'user' } as const;

/**
 * Sustituye `fetch` por un enrutador `"MÉTODO /ruta" → respuesta`. Las rutas sin handler responden 404 con
 * *problem details*. Devuelve el mock para inspeccionar las peticiones.
 */
export function stubApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (request: Request) => {
    const key = `${request.method} ${new URL(request.url).pathname}`;
    const handler = routes[key];
    const { status = 200, body } = handler
      ? typeof handler === 'function'
        ? await handler(request)
        : handler
      : { status: 404, body: { title: 'Not Found', status: 404 } };
    if (status === 204) {
      return new Response(null, { status });
    }
    return new Response(JSON.stringify(body ?? {}), {
      status,
      headers: { 'Content-Type': status < 400 ? 'application/json' : 'application/problem+json' },
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

export const HEALTH = {
  'GET /api/health': {
    body: {
      status: 'ok',
      version: '0.3.0',
      doc_organize_version: '0.9.3',
      database: 'ok',
      locations: 'none',
      worker: 'ok',
    },
  },
};

/** Rutas base con sesión iniciada como `me` (o sin sesión con `null`). */
export function session(me: typeof ADMIN | typeof USER | null): Record<string, Handler> {
  return {
    ...HEALTH,
    'GET /api/v1/auth/me': me
      ? { body: me }
      : { status: 401, body: { title: 'No autenticado', status: 401 } },
  };
}

/** Peticiones hechas a `METHOD /ruta`. */
export function callsTo(fetchMock: ReturnType<typeof stubApi>, method: string, path: string): Request[] {
  return fetchMock.mock.calls
    .map(([request]) => request)
    .filter((request) => request.method === method && new URL(request.url).pathname === path);
}
