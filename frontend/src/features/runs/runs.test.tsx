import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

type Listener = (event: MessageEvent<string>) => void;

/** `EventSource` simulado: los tests emiten los eventos del SSE a mano. */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readonly url: string;
  closed = false;
  private readonly listeners = new Map<string, Listener[]>();

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: Listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  emit(type: string, data: unknown, id: string) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(new MessageEvent(type, { data: JSON.stringify(data), lastEventId: id }));
    }
  }

  close() {
    this.closed = true;
  }
}

const RUN_ID = '11111111-1111-4111-8111-111111111111';

describe('RunsPage', () => {
  it('lista el historial agrupado por ejecución y filtra por estado', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/runs': {
        body: {
          items: [
            runOut({
              status: 'failed',
              started_at: '2026-11-01T08:00:00Z',
              finished_at: '2026-11-01T08:01:05Z',
            }),
          ],
          total: 1,
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/runs');

    expect(await screen.findByRole('link', { name: /Prueba del motor/ })).toHaveAttribute(
      'href',
      `/runs/${RUN_ID}`,
    );
    expect(within(screen.getByRole('table')).getByText('Fallida')).toBeInTheDocument();
    expect(screen.getByText('1 min 5 s')).toBeInTheDocument();
    await user.click(screen.getByRole('combobox', { name: 'Estado' }));
    await user.click(await screen.findByRole('option', { name: 'Cancelada', hidden: true }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/runs').some(
          (request) => new URL(request.url).searchParams.get('status') === 'cancelled',
        ),
      ).toBe(true),
    );
  });
});

describe('RunDetailPage', () => {
  it('muestra el progreso en vivo por SSE y cierra la conexión al terminar', async () => {
    vi.stubGlobal('EventSource', FakeEventSource);
    FakeEventSource.instances = [];
    let current = runOut({ status: 'running', started_at: '2026-11-01T08:00:00Z' });
    stubApi({ ...session(USER), [`GET /api/v1/runs/${RUN_ID}`]: () => ({ body: current }) });

    renderRoute(`/runs/${RUN_ID}`);
    expect(await screen.findByText('En marcha')).toBeInTheDocument();
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const source = FakeEventSource.instances[0] as FakeEventSource;
    expect(source.url).toBe(`/api/v1/runs/${RUN_ID}/events`);

    act(() => source.emit('progress', { phase: 'noop', processed: 3, total: 10, current: 'Paso 3' }, '4'));
    expect(await screen.findByText('3 de 10')).toBeInTheDocument();
    expect(screen.getByText('Prueba: 30 %')).toBeInTheDocument(); // anuncio aria-live
    act(() =>
      source.emit('log', { level: 'info', message: 'Cancelación solicitada.', ts: current.created_at }, '5'),
    );
    expect(await screen.findByText(/Cancelación solicitada\./)).toBeInTheDocument();

    current = runOut({
      status: 'succeeded',
      started_at: '2026-11-01T08:00:00Z',
      finished_at: '2026-11-01T08:00:10Z',
      result: { steps: 10 },
      can_cancel: false,
      artifacts: [
        {
          id: 4,
          name: 'noop.txt',
          kind: 'output',
          size_bytes: 30,
          content_type: 'text/plain',
          created_at: '',
        },
      ],
    });
    act(() => source.emit('end', { status: 'succeeded' }, '9'));

    expect(await screen.findByText('Terminada')).toBeInTheDocument();
    expect(source.closed).toBe(true);
    expect(screen.getByRole('link', { name: 'noop.txt' })).toHaveAttribute(
      'href',
      `/api/v1/runs/${RUN_ID}/artifacts/4`,
    );
  });

  it('cancela tras confirmar', async () => {
    vi.stubGlobal('EventSource', FakeEventSource);
    const fetchMock = stubApi({
      ...session(USER),
      [`GET /api/v1/runs/${RUN_ID}`]: { body: runOut({ status: 'running' }) },
      [`POST /api/v1/runs/${RUN_ID}/cancel`]: {
        status: 202,
        body: runOut({ status: 'running', cancel_requested: true }),
      },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${RUN_ID}`);
    await user.click(await screen.findByRole('button', { name: 'Cancelar ejecución' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Cancelar ejecución' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', `/api/v1/runs/${RUN_ID}/cancel`)).toHaveLength(1));
    expect(await screen.findByRole('button', { name: 'Cancelación pedida' })).toBeDisabled();
  });

  it('muestra el error de una ejecución fallida', async () => {
    stubApi({
      ...session(USER),
      [`GET /api/v1/runs/${RUN_ID}`]: {
        body: runOut({ status: 'failed', error_code: 'timeout', error_message: null, can_cancel: false }),
      },
    });

    renderRoute(`/runs/${RUN_ID}`);

    expect(
      await screen.findByText('Superó el tiempo máximo; se guardó lo hecho hasta parar.'),
    ).toBeInTheDocument();
  });
});

describe('Fase 10', () => {
  const FAILED_SCAN = runOut({
    operation: 'scan',
    status: 'failed',
    params: { operation: 'scan', force: true, use_ocr: true, folders: ['2024'] },
    error_code: 'out_of_memory',
    error_message: 'El worker se quedó sin memoria.',
    result: { converted: 200, segments: 3 },
    can_cancel: false,
  });

  it('un escaneo que se quedó sin memoria se continúa con sus opciones y sin forzar', async () => {
    vi.stubGlobal('EventSource', FakeEventSource);
    const NEXT = '22222222-2222-4222-8222-222222222222';
    const fetchMock = stubApi({
      ...session(USER),
      [`GET /api/v1/runs/${RUN_ID}`]: { body: FAILED_SCAN },
      'GET /api/v1/projects/7': { body: PROJECT },
      'POST /api/v1/projects/7/runs': { status: 202, body: runOut({ id: NEXT, operation: 'scan' }) },
      [`GET /api/v1/runs/${NEXT}`]: { body: runOut({ id: NEXT, operation: 'scan' }) },
    });
    const user = userEvent.setup();

    renderRoute(`/runs/${RUN_ID}`);

    expect(await screen.findByText(/3 tramos/)).toBeInTheDocument();
    await user.click(await screen.findByRole('button', { name: 'Continuar el escaneo' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const body: unknown = await callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')[0]?.json();
    expect(body).toEqual({ operation: 'scan', use_ocr: true, folders: ['2024'] });
  });

  it('un lector no puede continuarlo', async () => {
    vi.stubGlobal('EventSource', FakeEventSource);
    stubApi({
      ...session(USER),
      [`GET /api/v1/runs/${RUN_ID}`]: { body: FAILED_SCAN },
      'GET /api/v1/projects/7': { body: { ...PROJECT, role: 'viewer' } },
    });

    renderRoute(`/runs/${RUN_ID}`);

    expect(await screen.findByText('El worker se quedó sin memoria.')).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Continuar el escaneo' })).toBeNull());
  });

  it('el log enseña los últimos 200 avisos y el resto a petición', async () => {
    vi.stubGlobal('EventSource', FakeEventSource);
    FakeEventSource.instances = [];
    stubApi({ ...session(USER), [`GET /api/v1/runs/${RUN_ID}`]: { body: runOut({ status: 'running' }) } });
    const user = userEvent.setup();

    renderRoute(`/runs/${RUN_ID}`);

    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const source = FakeEventSource.instances[0] as FakeEventSource;
    act(() => {
      for (let index = 1; index <= 205; index += 1) {
        source.emit(
          'log',
          { ts: '2026-11-05T08:00:00Z', level: 'info', message: `aviso ${index}` },
          String(index),
        );
      }
    });

    expect(await screen.findByText(/aviso 205/)).toBeInTheDocument();
    expect(screen.queryByText(/aviso 5$/)).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Ver los 5 avisos anteriores' }));
    expect(screen.getByText(/aviso 5$/)).toBeInTheDocument();
  });

  it('avisa cuando termina una ejecución propia', async () => {
    let running = true;
    stubApi({
      ...session(USER),
      'GET /api/v1/projects': { body: { items: [], total: 0 } },
      'GET /api/v1/runs': () => ({
        body: {
          items: [
            running
              ? runOut({ status: 'running', operation: 'scan' })
              : runOut({ status: 'succeeded', operation: 'scan', finished_at: '2026-11-05T08:00:00Z' }),
          ],
          total: 1,
        },
      }),
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderRoute('/projects');
      await screen.findByRole('heading', { name: 'Proyectos' });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(100);
      });
      running = false;
      await act(async () => {
        await vi.advanceTimersByTimeAsync(16_000);
      });

      expect(await screen.findByText('Escaneo ha terminado')).toBeInTheDocument();
      expect(screen.getByText(/Terminó bien en «Proyecto A»/)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('Fase 10: aviso de una ejecución corta', () => {
  it('avisa aunque empiece y acabe entre dos consultas, pero no de las antiguas', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects': { body: { items: [], total: 0 } },
      'GET /api/v1/runs': {
        body: {
          items: [
            runOut({ id: 'vieja', status: 'failed', operation: 'scan', finished_at: '2026-01-01T00:00:00Z' }),
            runOut({
              status: 'succeeded',
              operation: 'export_zip',
              finished_at: new Date(Date.now() + 1000).toISOString(),
            }),
          ],
          total: 2,
        },
      },
    });

    renderRoute('/projects');

    expect(await screen.findByText(/^Exportar ZIP ha terminado$|ha terminado$/)).toBeInTheDocument();
    expect(screen.queryByText(/Falló en/)).not.toBeInTheDocument();
  });
});
