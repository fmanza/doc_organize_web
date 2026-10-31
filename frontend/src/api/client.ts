import createClient from 'openapi-fetch';

import type { paths } from './schema';

// Cliente tipado generado desde openapi/openapi.json (npm run gen:api). Mismo origen: la cookie de sesión
// (Fase 1) viaja sola y no hace falta CORS.
// `fetch` se resuelve en cada llamada (no al crear el cliente) para que los tests puedan sustituirlo.
export const api = createClient<paths>({
  baseUrl: globalThis.location.origin,
  credentials: 'same-origin',
  fetch: (request) => globalThis.fetch(request),
});

export interface Problem {
  title: string;
  status: number;
  detail?: string;
  request_id?: string;
}

export class ApiError extends Error {
  readonly problem: Problem;

  constructor(problem: Problem) {
    super(problem.detail ?? problem.title);
    this.name = 'ApiError';
    this.problem = problem;
  }
}

/** Devuelve `data` o lanza `ApiError` con el *problem details* de la API (RFC 9457). */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.data !== undefined) {
    return result.data;
  }
  const problem = (result.error as Problem | undefined) ?? {
    title: result.response.statusText || 'Error',
    status: result.response.status,
  };
  throw new ApiError(problem);
}
