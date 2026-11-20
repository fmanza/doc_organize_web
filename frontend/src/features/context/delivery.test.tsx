import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { beforeAll, describe, expect, it } from 'vitest';

import { loadFeatureMessages } from '../../i18n';
import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { runOut } from '../../test/fixtures';
import { renderRoute, renderWithProviders } from '../../test/render';
import { DeliveryCard } from './DeliveryCard';

// W8: entregar el contexto (Excel, sitio sin conexión y paquete para IA). Datos sintéticos.
const RUN_ID = '99999999-9999-4999-8999-999999999999';
const SHA = 'a'.repeat(64);

function renderCard() {
  renderWithProviders(
    <MemoryRouter>
      <DeliveryCard projectId={7} />
    </MemoryRouter>,
  );
}

async function sent(fetchMock: ReturnType<typeof stubApi>) {
  await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
  const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
  return (await request?.clone().json()) as unknown;
}

describe('Entregar el contexto', () => {
  beforeAll(() => loadFeatureMessages());

  it('lanza el sitio sin conexión con llms.txt', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'POST /api/v1/projects/7/runs': { status: 202, body: runOut({ id: RUN_ID, operation: 'export_site' }) },
    });
    const user = userEvent.setup();
    renderCard();

    await user.click(await screen.findByRole('checkbox', { name: /llms.txt \(índice para IA\)/ }));
    await user.click(screen.getByRole('button', { name: 'Sitio sin conexión' }));

    expect(await sent(fetchMock)).toEqual({ operation: 'export_site', llms_txt: true });
  });

  it('el paquete para IA se redacta siempre si no eres administrador', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'export_ai_bundle' }),
      },
    });
    const user = userEvent.setup();
    renderCard();

    expect(await screen.findByText(/sale de la aplicación y puede ser confidencial/)).toBeInTheDocument();
    expect(screen.queryByRole('checkbox', { name: 'Redactar credenciales' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Paquete para IA' }));

    expect(await sent(fetchMock)).toEqual({
      operation: 'export_ai_bundle',
      include_text: true,
      current_only: true,
      redact: true,
      max_file_chars: null,
      max_full_chars: null,
    });
  });

  it('un administrador puede no redactar, con aviso', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'export_ai_bundle' }),
      },
    });
    const user = userEvent.setup();
    renderCard();

    await user.click(await screen.findByRole('checkbox', { name: /Redactar credenciales/ }));
    expect(screen.getByText(/Sin redactar, el paquete lleva/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Paquete para IA' }));

    expect(await sent(fetchMock)).toMatchObject({ operation: 'export_ai_bundle', redact: false });
  });

  it('el detalle de la entrega enseña la huella y el aviso', async () => {
    stubApi({
      ...session(USER),
      [`GET /api/v1/runs/${RUN_ID}`]: {
        body: runOut({
          id: RUN_ID,
          operation: 'export_site',
          status: 'succeeded',
          can_cancel: false,
          result: { sha256: SHA, zip_size_bytes: 2048, file_name: 'Proyecto_A-sitio.zip' },
          artifacts: [
            {
              id: 1,
              name: 'Proyecto_A-sitio.zip',
              kind: 'output',
              size_bytes: 2048,
              content_type: 'application/zip',
              created_at: '2026-11-20T10:00:00Z',
            },
          ],
        }),
      },
    });

    renderRoute(`/runs/${RUN_ID}`);

    expect(await screen.findByTestId('sha256')).toHaveTextContent(SHA);
    expect(screen.getByText(/contenido de terceros de las páginas está neutralizado/)).toBeInTheDocument();
  });
});
