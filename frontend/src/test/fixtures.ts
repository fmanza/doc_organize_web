/** Respuestas de la API de ejemplo para los tests de proyectos y ejecuciones (datos sintéticos). */

const LOCATION_REF = { id: 1, name: 'Origen', access: 'ro', status: 'ok' } as const;
const DEST_REF = { id: 2, name: 'Salidas', access: 'rw', status: 'ok' } as const;

export const PROJECT = {
  id: 7,
  name: 'Proyecto A',
  description: null,
  source_location: LOCATION_REF,
  source_subpaths: ['2024'],
  destination_location: DEST_REF,
  destination_subpath: 'Proyecto A',
  role: 'owner',
  created_at: '2026-11-01T08:00:00Z',
  updated_at: '2026-11-01T08:00:00Z',
  last_run: null,
  active_run: false,
};

export function runOut(overrides: Record<string, unknown> = {}) {
  return {
    id: '11111111-1111-4111-8111-111111111111',
    project_id: 7,
    project_name: 'Proyecto A',
    operation: 'noop',
    queue: 'cpu',
    status: 'queued',
    is_write: false,
    params: { operation: 'noop' },
    progress: null,
    result: null,
    error_code: null,
    error_message: null,
    cancel_requested: false,
    created_by_username: 'ana',
    created_at: '2026-11-01T08:00:00Z',
    started_at: null,
    finished_at: null,
    workspace_purged: false,
    artifacts: [],
    can_cancel: true,
    ...overrides,
  };
}
