import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

const RUN_ID = '44444444-4444-4444-8444-444444444444';

const FOLDERS = {
  location: PROJECT.source_location,
  items: [
    {
      subpath: '2024',
      used: true,
      added_at: '2026-11-01T08:00:00Z',
      last_scanned_at: '2026-11-01T09:00:00Z',
      last_run_id: RUN_ID,
      available: true,
    },
    {
      subpath: '2025',
      used: false,
      added_at: '2026-11-01T08:00:00Z',
      last_scanned_at: null,
      last_run_id: null,
      available: false,
    },
  ],
};

const CAPABILITIES = {
  status: 'ok',
  checked_at: '2026-11-01T08:00:00Z',
  capabilities: null,
  queues: ['cpu'],
  doc_organize_version: '0.10.0',
  scan_options: { use_gpu: false, include_audio_video: true, use_picture_description: false },
};

function scanRoutes(project: Record<string, unknown> = PROJECT) {
  return {
    ...session(USER),
    'GET /api/v1/projects/7': { body: { ...project, source_subpaths: ['2024', '2025'] } },
    'GET /api/v1/projects/7/scanned-folders': { body: FOLDERS },
    'GET /api/v1/instance/capabilities': { body: CAPABILITIES },
  };
}

describe('ScanPage', () => {
  it('lanza el escaneo de las carpetas marcadas con las opciones elegidas', async () => {
    const fetchMock = stubApi({
      ...scanRoutes(),
      'POST /api/v1/projects/7/runs': { status: 202, body: runOut({ id: RUN_ID, operation: 'scan' }) },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: runOut({ id: RUN_ID, operation: 'scan' }) },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/scan');
    // /2025 ya no existe: queda fuera y no se puede marcar.
    expect(await screen.findByRole('checkbox', { name: 'Incluir /2025 en el escaneo' })).toBeDisabled();
    await user.click(screen.getByRole('switch', { name: /Extraer imágenes/ }));
    await user.click(screen.getByRole('button', { name: 'Escanear 1 carpeta' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.json()).toEqual({
      operation: 'scan',
      folders: ['2024'],
      use_ocr: true,
      use_gpu: false,
      include_audio_video: false,
      extract_images: true,
      use_picture_description: false,
      force: false,
      dry_run: false,
    });
    expect(await screen.findByRole('heading', { name: 'Escaneo' })).toBeInTheDocument();
  });

  it('muestra el estado de las carpetas y desactiva las opciones que la instancia no admite', async () => {
    stubApi(scanRoutes());

    renderRoute('/projects/7/scan');

    expect(await screen.findByText('escaneada')).toBeInTheDocument();
    expect(screen.getByText('no existe')).toBeInTheDocument();
    expect(screen.getByText('Nunca')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: /Usar GPU/ })).toBeDisabled();
    expect(screen.getByText('No hay ningún worker con GPU y los modelos de EasyOCR.')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: /Incluir audio y vídeo/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Escanear 1 carpeta' })).toBeEnabled();
  });

  it('si no se pueden comprobar las capacidades lo dice y no envía opciones que dependen de ellas', async () => {
    stubApi({
      ...scanRoutes(),
      'GET /api/v1/instance/capabilities': { status: 500, body: { title: 'Error', status: 500 } },
    });

    renderRoute('/projects/7/scan');

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudieron comprobar las capacidades');
    expect(screen.getByRole('switch', { name: /Incluir audio y vídeo/ })).toBeDisabled();
    expect(screen.queryByText('La instancia no tiene Whisper y ffmpeg.')).not.toBeInTheDocument();
  });

  it('un lector ve las carpetas pero no puede escanear ni cambiarlas', async () => {
    stubApi(scanRoutes({ ...PROJECT, role: 'viewer' }));

    renderRoute('/projects/7/scan');

    expect(await screen.findByText(/hace falta el rol de editor/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Escanear/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Añadir carpeta' })).not.toBeInTheDocument();
    expect(screen.queryByText('Forzar reconversión', { selector: 'h3' })).not.toBeInTheDocument();
  });

  it('quitar una carpeta escaneada avisa de que sus salidas se quedan', async () => {
    const fetchMock = stubApi({
      ...scanRoutes(),
      'DELETE /api/v1/projects/7/scanned-folders': { body: { subpath: '2024', used: true } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/scan');
    await user.click(await screen.findByRole('button', { name: 'Quitar /2024' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Esta carpeta ya se escaneó')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Quitar' }));

    await waitFor(() =>
      expect(callsTo(fetchMock, 'DELETE', '/api/v1/projects/7/scanned-folders')).toHaveLength(1),
    );
    const [request] = callsTo(fetchMock, 'DELETE', '/api/v1/projects/7/scanned-folders');
    expect(new URL(request?.url ?? '').searchParams.get('subpath')).toBe('2024');
  });

  it('forzar la reconversión pasa por la vista previa con todas las carpetas', async () => {
    const preview = runOut({
      id: '55555555-5555-4555-8555-555555555555',
      operation: 'scan',
      status: 'succeeded',
      params: { operation: 'scan', force: true, dry_run: true },
      result: { cached: 10, orphaned: 2, output_files: 30, output_bytes: 4096 },
      can_cancel: false,
    });
    const fetchMock = stubApi({
      ...scanRoutes(),
      'POST /api/v1/projects/7/runs': { status: 202, body: preview },
      [`GET /api/v1/runs/${preview.id}`]: { body: preview },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/scan');
    await user.click(await screen.findByRole('button', { name: 'Forzar reconversión' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Ver vista previa' }));

    expect(
      await within(dialog).findByText('Salidas que se borrarán (el documento ya no está)'),
    ).toBeInTheDocument();
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.json()).toMatchObject({
      operation: 'scan',
      force: true,
      dry_run: true,
      folders: [],
    });
    expect(within(dialog).getByRole('button', { name: 'Forzar reconversión' })).toBeDisabled();
  });
});

describe('ScanErrorsPage', () => {
  it('muestra los errores del último escaneo paginados', async () => {
    const items = Array.from({ length: 50 }, (_, i) => ({
      id: i + 1,
      path: `2024/doc${String(i).padStart(3, '0')}.pdf`,
      message: 'No se pudo leer el PDF',
      retry_count: i === 0 ? 3 : 1,
      capped: i === 0,
    }));
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7/scan-errors': {
        body: {
          run: {
            id: RUN_ID,
            operation: 'scan',
            status: 'succeeded',
            created_at: '2026-11-01T08:00:00Z',
            finished_at: '2026-11-01T09:00:00Z',
          },
          items,
          total: 120,
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/scan-errors');

    expect(await screen.findByText('120 documentos no se pudieron convertir.')).toBeInTheDocument();
    expect(screen.getByText('2024/doc000.pdf')).toBeInTheDocument();
    expect(screen.getByText('no se reintenta')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '3' }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/projects/7/scan-errors').some(
          (r) => new URL(r.url).searchParams.get('offset') === '100',
        ),
      ).toBe(true),
    );
  });

  it('sin escaneos todavía lo dice', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7/scan-errors': { body: { run: null, items: [], total: 0 } },
    });

    renderRoute('/projects/7/scan-errors');

    expect(await screen.findByText('Aún no se ha escaneado este proyecto.')).toBeInTheDocument();
  });
});
