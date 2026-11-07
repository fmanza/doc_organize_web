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
      ignore_patterns: [],
    });
  });

  it('el admin pone los patrones de nombre al registrar una ubicación de origen (1.4.1)', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/locations': { body: { items: [], total: 0 } },
      'GET /api/v1/admin/mounts': { body: { ...folders('', ['expedientes']).body, location_id: null } },
      'POST /api/v1/locations': { status: 201, body: ADMIN_VIEW },
    });
    const user = userEvent.setup();

    renderRoute('/locations');
    await user.click(await screen.findByRole('button', { name: 'Nueva ubicación' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Nombre/ }), 'Expedientes');
    await user.click(await within(dialog).findByRole('button', { name: /expedientes/ }));
    await user.click(within(dialog).getByRole('button', { name: 'Elegir esta carpeta' }));
    const patterns = within(dialog).getByRole('textbox', { name: /Patrones \(uno por línea\)/ });
    expect(within(dialog).getByText(/Afecta a todos los proyectos de la ubicación/)).toBeInTheDocument();
    await user.type(patterns, '~$*{Enter}  @eaDir {Enter}');
    await user.click(within(dialog).getByRole('button', { name: 'Registrar ubicación' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/locations')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/locations');
    expect(await request?.json()).toMatchObject({ usage: 'source', ignore_patterns: ['~$*', '@eaDir'] });
  });

  it('en una ubicación de destino no se piden ni se envían patrones', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/locations': { body: { items: [], total: 0 } },
      'GET /api/v1/admin/mounts': { body: { ...folders('', ['salidas']).body, location_id: null } },
      'POST /api/v1/locations': { status: 201, body: { ...ADMIN_VIEW, usage: 'destination' } },
    });
    const user = userEvent.setup();

    renderRoute('/locations');
    await user.click(await screen.findByRole('button', { name: 'Nueva ubicación' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Nombre/ }), 'Salidas');
    await user.click(await within(dialog).findByRole('button', { name: /salidas/ }));
    await user.click(within(dialog).getByRole('button', { name: 'Elegir esta carpeta' }));
    await user.click(within(dialog).getByRole('radio', { name: 'Destino' }));
    expect(within(dialog).queryByRole('textbox', { name: /Patrones/ })).not.toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Registrar ubicación' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/locations')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/locations');
    expect(await request?.json()).not.toHaveProperty('ignore_patterns');
  });

  it('al editar se ven y se cambian los patrones guardados', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/locations': { body: { items: [{ ...ADMIN_VIEW, ignore_patterns: ['~$*'] }], total: 1 } },
      'PATCH /api/v1/locations/1': { body: { ...ADMIN_VIEW, ignore_patterns: [] } },
    });
    const user = userEvent.setup();

    renderRoute('/locations');
    await user.click(await screen.findByRole('button', { name: 'Editar Expedientes' }));
    const dialog = await screen.findByRole('dialog');
    const patterns = within(dialog).getByRole('textbox', { name: /Patrones/ });
    expect(patterns).toHaveValue('~$*');
    await user.clear(patterns);
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/locations/1')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PATCH', '/api/v1/locations/1');
    expect(await request?.json()).toMatchObject({ ignore_patterns: [] });
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

  it('explica cómo montar carpetas si /mnt está vacía', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/locations': { body: { items: [], total: 0 } },
      'GET /api/v1/admin/mounts': { body: { ...folders('', []).body, location_id: null } },
    });
    const user = userEvent.setup();

    renderRoute('/locations');
    await user.click(await screen.findByRole('button', { name: 'Nueva ubicación' }));
    const dialog = await screen.findByRole('dialog');

    expect(await within(dialog).findByText(/No hay carpetas montadas en \/mnt/)).toBeInTheDocument();
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
          queues: ['cpu', 'gpu'],
          // 1.0.1: la suma de los workers vivos; la GPU solo la tiene el de la cola gpu.
          capability_queues: { gpu_ready: ['gpu'], gpu_active: ['gpu'], ffmpeg_installed: ['cpu', 'gpu'] },
          doc_organize_version: '0.10.0',
          capabilities: {
            gpu_support_installed: true,
            gpu_active: true,
            asr_installed: false,
            ffmpeg_installed: true,
            av_ready: false,
            libreoffice_installed: false,
            models_ready: true,
            picture_description_ready: false,
            gpu_ready: true,
          },
          scan_options: { use_gpu: true, include_audio_video: false, use_picture_description: false },
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
              running: 0,
            },
            {
              id: 'worker-gpu:9',
              queues: ['gpu'],
              version: '1.0.0',
              doc_organize_version: '1.0.0',
              started_at: '2026-10-31T08:00:00Z',
              heartbeat_at: '2026-10-31T08:00:00Z',
              alive: true,
              capabilities_at: '2026-10-31T08:00:00Z',
              gpu_ready: true,
              running: 1,
              resources: {
                memory_limit_bytes: 8 * 1024 ** 3,
                memory_peak_bytes: 6 * 1024 ** 3,
                memory_current_bytes: 2 * 1024 ** 3,
                oom_kills: 2,
                slots: 1,
                scan_recycle_documents: 200,
                scan_document_timeout_seconds: 1800,
                scan_io_retries: 2,
                scan_reuse_hashes: true,
              },
            },
          ],
        },
      },
    });

    renderRoute('/admin/settings');

    const gpu = (await screen.findByText('OCR con GPU (EasyOCR)')).parentElement as HTMLElement;
    expect(within(gpu).getByText('Sí')).toBeInTheDocument();
    expect(within(gpu).getByText('cola gpu')).toBeInTheDocument();
    const ffmpeg = screen.getByText('ffmpeg').parentElement as HTMLElement;
    expect(within(ffmpeg).getByText('Sí')).toBeInTheDocument();
    expect(within(ffmpeg).queryByText(/^colas? /)).not.toBeInTheDocument(); // la tienen todas las colas
    const libreoffice = screen.getByText('LibreOffice (.xls antiguos)').parentElement as HTMLElement;
    expect(within(libreoffice).getByText('No')).toBeInTheDocument();
    expect(screen.getByText(/^Comprobado .* · doc_organize 0.10.0$/)).toBeInTheDocument();
    expect(screen.getByText('Colas atendidas: cpu, gpu')).toBeInTheDocument();
    // 1.1.0: «Libre» o «Trabajando», no «En marcha» (que solo decía que el proceso tenía latido).
    const cpuRow = (await screen.findByText('worker-1:7')).closest('tr') as HTMLElement;
    expect(within(cpuRow).getByText('Libre')).toBeInTheDocument();
    expect(within(cpuRow).getByText('web 0.4.0 · doc_organize 0.10.0')).toBeInTheDocument();
    const gpuRow = screen.getByText('worker-gpu:9').closest('tr') as HTMLElement;
    expect(within(gpuRow).getByText('Trabajando (1 de 1)')).toBeInTheDocument();
    expect(screen.queryByText('En marcha')).not.toBeInTheDocument();
    // M3 (Fase 10) y 1.1.0: uso actual, pico desde el arranque, OOM y los ajustes del escaneo.
    expect(within(gpuRow).getByText('Ahora 2 GB')).toBeInTheDocument();
    expect(within(gpuRow).getByText('Pico 6 GB · límite 8 GB')).toBeInTheDocument();
    expect(within(gpuRow).getByText('2 veces sin memoria')).toBeInTheDocument();
    expect(within(gpuRow).getByText('Tramos de 200 documentos')).toBeInTheDocument();
    expect(within(gpuRow).getByText('Máximo 30 min 0 s por documento')).toBeInTheDocument();
    expect(within(gpuRow).getByText('2 reintentos de lectura')).toBeInTheDocument();
    expect(within(gpuRow).getByText('Reutiliza los hashes sin cambios')).toBeInTheDocument();
  });
});

describe('Patrones de nombre de una ubicación de origen (1.4.0)', () => {
  it('el admin los edita, uno por línea, con el aviso de que afectan a todos los proyectos', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/locations/1': { body: { ...ADMIN_VIEW, ignore_patterns: ['~$*'] } },
      'GET /api/v1/fs/browse': folders('', []),
      'PATCH /api/v1/locations/1': { body: { ...ADMIN_VIEW, ignore_patterns: ['~$*', '@eaDir'] } },
    });
    const user = userEvent.setup();

    renderRoute('/locations/1');
    const field = await screen.findByRole('textbox', { name: /Patrones \(uno por línea\)/ });
    expect(field).toHaveValue('~$*');
    expect(screen.getByText(/Afecta a todos los proyectos de la ubicación/)).toBeInTheDocument();
    expect(screen.getByText(/System Volume Information/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Guardar patrones' })).toBeDisabled();
    await user.type(field, '{Enter}  @eaDir  {Enter}{Enter}');
    await user.click(screen.getByRole('button', { name: 'Guardar patrones' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/locations/1')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PATCH', '/api/v1/locations/1');
    expect(await request?.json()).toEqual({ ignore_patterns: ['~$*', '@eaDir'] });
  });

  it('muestra el error de un patrón no válido', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/locations/1': { body: { ...ADMIN_VIEW, ignore_patterns: [] } },
      'GET /api/v1/fs/browse': folders('', []),
      'PATCH /api/v1/locations/1': {
        status: 400,
        body: { title: 'Patrones no válidos', status: 400, code: 'invalid_ignore_patterns' },
      },
    });
    const user = userEvent.setup();

    renderRoute('/locations/1');
    await user.type(await screen.findByRole('textbox', { name: /Patrones/ }), 'fotos/*.jpg');
    await user.click(screen.getByRole('button', { name: 'Guardar patrones' }));

    expect(await screen.findByText('Patrones no válidos')).toBeInTheDocument();
  });

  it('un usuario solo los ve', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/locations/1': { body: { ...PUBLIC, ignore_patterns: ['@eaDir'] } },
      'GET /api/v1/fs/browse': folders('', []),
    });

    renderRoute('/locations/1');

    expect(await screen.findByText('@eaDir')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: /Patrones/ })).not.toBeInTheDocument();
  });

  it('en una ubicación de destino no aparecen', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/locations/1': { body: { ...ADMIN_VIEW, usage: 'destination' } },
      'GET /api/v1/fs/browse': folders('', []),
    });

    renderRoute('/locations/1');

    expect(await screen.findByRole('heading', { name: 'Expedientes' })).toBeInTheDocument();
    expect(screen.queryByText('Nombres que no se escanean')).not.toBeInTheDocument();
  });
});
