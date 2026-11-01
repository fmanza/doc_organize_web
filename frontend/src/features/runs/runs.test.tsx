import { act, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { runOut } from '../../test/fixtures';
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
