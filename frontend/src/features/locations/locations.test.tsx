import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';

const PUBLIC = {
  id: 1,
  name: 'Expedientes',
  display_path: '\\\\nas.example.internal\\expedientes',
  kind: 'network',
  usage: 'source',
  access: 'ro',
  status: 'degraded',
  status_reasons: ['slow'],
  probed_at: '2026-10-31T08:00:00Z',
};
const ADMIN_VIEW = {
  ...PUBLIC,
  container_path: '/mnt/expedientes',
  latency_ms: 820,
  free_bytes: 50 * 1024 ** 3,
  writable: null,
  created_at: '2026-10-31T08:00:00Z',
  updated_at: '2026-10-31T08:00:00Z',
};

function folders(path: string, names: string[], parent: string | null = path ? '' : null) {
  return {
    body: {
      location_id: 1,
      path,
      parent,
      items: names.map((name) => ({ name, path: path ? `${path}/${name}` : name })),
      total: names.length,
    },
  };
}

describe('LocationsPage', () => {
  it('un usuario ve las ubicaciones con su estado y sin acciones de administración', async () => {
    stubApi({ ...session(USER), 'GET /api/v1/locations': { body: { items: [PUBLIC], total: 1 } } });

    renderRoute('/locations');

    expect(await screen.findByRole('link', { name: 'Expedientes' })).toBeInTheDocument();
    expect(screen.getByText('Degradada')).toBeInTheDocument();
    expect(screen.getByText('(responde lento)', { exact: false })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Nueva ubicación' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Comprobar Expedientes' })).not.toBeInTheDocument();
  });

  it('el admin registra una ubicación eligiendo la carpeta en /mnt', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/locations': { body: { items: [], total: 0 } },
      'GET /api/v1/admin/mounts': (request) => {
        const path = new URL(request.url).searchParams.get('path') ?? '';
        return path === 'expedientes'
          ? folders('expedientes', ['2024'])
          : { body: { ...folders('', ['expedientes', 'salidas']).body, location_id: null } };
      },
      'POST /api/v1/locations': { status: 201, body: ADMIN_VIEW },
    });
    const user = userEvent.setup();

    renderRoute('/locations');
    await user.click(await screen.findByRole('button', { name: 'Nueva ubicación' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Nombre/ }), 'Expedientes');
    await user.click(await within(dialog).findByRole('button', { name: /expedientes/ }));
    await within(dialog).findByRole('button', { name: /2024/ });
    await user.click(within(dialog).getByRole('button', { name: 'Elegir esta carpeta' }));
    await user.click(within(dialog).getByRole('radio', { name: 'Lectura y escritura' }));
    await user.click(within(dialog).getByRole('button', { name: 'Registrar ubicación' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/locations')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/locations');
    expect(await request?.json()).toEqual({
      name: 'Expedientes',
      path: 'expedientes',
      display_path: null,
      kind: 'local',
      usage: 'source',
      access: 'rw',
    });
  });

  it('no deja registrar sin elegir carpeta', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/locations': { body: { items: [], total: 0 } },
      'GET /api/v1/admin/mounts': { body: { ...folders('', ['expedientes']).body, location_id: null } },
    });
    const user = userEvent.setup();

    renderRoute('/locations');
    await user.click(await screen.findByRole('button', { name: 'Nueva ubicación' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Nombre/ }), 'Sin carpeta');
    await user.click(within(dialog).getByRole('button', { name: 'Registrar ubicación' }));

    expect(await within(dialog).findByText('Elige una subcarpeta de /mnt')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', '/api/v1/locations')).toHaveLength(0);
  });

  it('el admin borra una ubicación solo tras escribir su nombre', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/locations': { body: { items: [ADMIN_VIEW], total: 1 } },
      'DELETE /api/v1/locations/1': { status: 204 },
    });
    const user = userEvent.setup();

    renderRoute('/locations');
    await user.click(await screen.findByRole('button', { name: 'Borrar Expedientes' }));
    const dialog = await screen.findByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: 'Borrar' });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByRole('textbox'), 'Expedientes');
    await user.click(confirm);

    await waitFor(() => expect(callsTo(fetchMock, 'DELETE', '/api/v1/locations/1')).toHaveLength(1));
  });
});

describe('LocationDetailPage', () => {
  it('explora carpetas y sube de nivel', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/locations/1': { body: PUBLIC },
      'GET /api/v1/fs/browse': (request) =>
        new URL(request.url).searchParams.get('path') === '2024'
          ? folders('2024', ['enero'])
          : folders('', ['2024', '2025']),
    });
    const user = userEvent.setup();

    renderRoute('/locations/1');
    await user.click(await screen.findByRole('button', { name: /2024/ }));

    expect(await screen.findByRole('button', { name: /enero/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Subir un nivel/ }));
    expect(await screen.findByRole('button', { name: /2025/ })).toBeInTheDocument();
  });

  it('muestra el error de una ubicación no disponible (503)', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/locations/1': { body: { ...PUBLIC, status: 'unavailable', status_reasons: ['missing'] } },
      'GET /api/v1/fs/browse': {
        status: 503,
        body: {
          title: 'Ubicación no disponible',
          status: 503,
          detail: 'No se puede acceder a la ubicación.',
        },
      },
    });

    renderRoute('/locations/1');

    expect(await screen.findByRole('alert')).toHaveTextContent('Ubicación no disponible');
    expect(screen.getByText('No disponible')).toBeInTheDocument();
  });
});

describe('SettingsPage', () => {
  const SETTINGS = {
    items: [
      { key: 'login_max_attempts', value: 5, default: 5, source: 'default' },
      { key: 'password_min_length', value: 16, default: 12, source: 'db' },
    ],
  };

  it('guarda un ajuste y restablece otro', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/settings': { body: SETTINGS },
      'PATCH /api/v1/admin/settings': { body: SETTINGS },
      'GET /api/v1/instance/capabilities': {
        body: {
          status: 'pending',
          checked_at: null,
          capabilities: null,
          queues: ['cpu'],
          doc_organize_version: '0.10.0',
          scan_options: { use_gpu: false, include_audio_video: false, use_picture_description: false },
        },
      },
      'GET /api/v1/admin/workers': { body: { items: [] } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/settings');
    const input = await screen.findByRole('textbox', { name: 'Intentos fallidos antes del bloqueo' });
    await user.clear(input);
    await user.type(input, '3');
    await user.click(screen.getByRole('button', { name: 'Guardar Intentos fallidos antes del bloqueo' }));
    await user.click(screen.getByRole('button', { name: 'Restablecer Longitud mínima de contraseña' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/admin/settings')).toHaveLength(2));
    const [save, reset] = callsTo(fetchMock, 'PATCH', '/api/v1/admin/settings');
    expect(await save?.json()).toEqual({ values: { login_max_attempts: 3 } });
    expect(await reset?.json()).toEqual({ values: { password_min_length: null } });
    expect(screen.getByText('Comprobando… (el worker tarda un minuto la primera vez)')).toBeInTheDocument();
  });

  it('muestra la ficha de capacidades', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/settings': { body: { items: [] } },
      'GET /api/v1/instance/capabilities': {
        body: {
          status: 'ok',
          checked_at: '2026-10-31T08:00:00Z',
          queues: ['cpu'],
          doc_organize_version: '0.10.0',
          capabilities: {
            gpu_support_installed: true,
            gpu_active: false,
            asr_installed: false,
            ffmpeg_installed: true,
            av_ready: false,
            libreoffice_installed: false,
            models_ready: true,
            picture_description_ready: false,
            gpu_ready: false,
          },
          scan_options: { use_gpu: false, include_audio_video: false, use_picture_description: false },
        },
      },
      'GET /api/v1/admin/workers': {
        body: {
          items: [
            {
              id: 'worker-1:7',
              queues: ['cpu'],
              version: '0.4.0',
              doc_organize_version: '0.10.0',
              started_at: '2026-10-31T08:00:00Z',
              heartbeat_at: '2026-10-31T08:00:00Z',
              alive: true,
              capabilities_at: '2026-10-31T08:00:00Z',
            },
          ],
        },
      },
    });

    renderRoute('/admin/settings');

    const gpu = await screen.findByText('OCR con GPU (EasyOCR)');
    expect(within(gpu.parentElement as HTMLElement).getByText('No')).toBeInTheDocument();
    const ffmpeg = screen.getByText('ffmpeg');
    expect(within(ffmpeg.parentElement as HTMLElement).getByText('Sí')).toBeInTheDocument();
    expect(screen.getByText(/doc_organize 0\.10\.0/)).toBeInTheDocument();
    expect(screen.getByText('Colas atendidas: cpu')).toBeInTheDocument();
    expect(await screen.findByText('worker-1:7')).toBeInTheDocument();
    expect(screen.getByText('En marcha')).toBeInTheDocument();
  });
});
