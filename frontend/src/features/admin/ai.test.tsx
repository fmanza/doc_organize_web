import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';

function field(name: string, overrides: Record<string, unknown> = {}) {
  const secret = name === 'virtual_key' || name === 'pat';
  return {
    name,
    env_var: `DOC_ORGANIZE_X_${name.toUpperCase()}`,
    secret,
    required: name !== 'model',
    source: 'none',
    value: null,
    hint: null,
    undecryptable: false,
    ...overrides,
  };
}

function family(
  key: string,
  names: string[],
  overrides: Record<string, Record<string, unknown>> = {},
  configured = false,
) {
  return { key, configured, fields: names.map((name) => field(name, overrides[name] ?? {})) };
}

const LITELLM = ['base_url', 'virtual_key', 'model'];
const SETTINGS = {
  encryption_configured: true,
  families: [
    family(
      'litellm_classification',
      LITELLM,
      {
        base_url: { source: 'db', value: 'https://litellm.example.internal' },
        virtual_key: { source: 'db', hint: '…ab12' },
      },
      true,
    ),
    family('litellm_taxonomy_classification', LITELLM, {
      virtual_key: { source: 'env', hint: '***' },
    }),
    family('litellm_taxonomy_manifest_draft', LITELLM),
    family('litellm_usage', ['base_url', 'virtual_key']),
    family('github_copilot_usage', ['username', 'pat']),
  ],
};

describe('AiSettingsPage', () => {
  it('muestra cada familia sin secretos y guarda solo lo cambiado', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { body: SETTINGS },
      'PUT /api/v1/admin/ai-settings/litellm_usage': {
        body: family('litellm_usage', ['base_url', 'virtual_key'], {
          base_url: { source: 'db', value: 'https://litellm.example.internal' },
          virtual_key: { source: 'db', hint: '…9999' },
        }),
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai-settings');

    const classification = await screen.findByRole('region', { name: 'Clasificación de dominios (un eje)' });
    expect(within(classification).getByText('Configurada')).toBeInTheDocument();
    expect(within(classification).getByText('Guardada: …ab12')).toBeInTheDocument();
    expect(within(classification).getByLabelText(/Clave virtual/, { selector: 'input' })).toHaveValue('');
    const taxonomy = screen.getByRole('region', { name: 'Clasificación por taxonomía (dos ejes)' });
    expect(within(taxonomy).getByText('Variable del servidor')).toBeInTheDocument();

    const usage = screen.getByRole('region', { name: 'Uso de LiteLLM' });
    const save = within(usage).getByRole('button', { name: 'Guardar Uso de LiteLLM' });
    expect(save).toBeDisabled();
    await user.type(
      within(usage).getByLabelText(/URL del servicio/, { selector: 'input' }),
      'https://litellm.example.internal',
    );
    await user.type(within(usage).getByLabelText(/Clave virtual/, { selector: 'input' }), 'sk-nueva-9999');
    await user.click(save);

    await waitFor(() =>
      expect(callsTo(fetchMock, 'PUT', '/api/v1/admin/ai-settings/litellm_usage')).toHaveLength(1),
    );
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/admin/ai-settings/litellm_usage');
    expect(await request?.clone().json()).toEqual({
      fields: { base_url: 'https://litellm.example.internal', virtual_key: 'sk-nueva-9999' },
    });
    expect(await within(usage).findByText('Guardada: …9999')).toBeInTheDocument();
    expect(within(usage).getByLabelText(/Clave virtual/, { selector: 'input' })).toHaveValue('');
  });

  it('borra un valor guardado', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { body: SETTINGS },
      'PUT /api/v1/admin/ai-settings/litellm_classification': { body: SETTINGS.families[0] },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai-settings');

    await user.click(
      await screen.findByRole('button', { name: 'Borrar el valor guardado de Clave virtual' }),
    );

    await waitFor(() =>
      expect(callsTo(fetchMock, 'PUT', '/api/v1/admin/ai-settings/litellm_classification')).toHaveLength(1),
    );
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/admin/ai-settings/litellm_classification');
    expect(await request?.clone().json()).toEqual({ fields: { virtual_key: null } });
  });

  it('sin cifrado avisa y no deja guardar claves', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { body: { ...SETTINGS, encryption_configured: false } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai-settings');

    expect(await screen.findByText('Cifrado no configurado')).toBeInTheDocument();
    const copilot = screen.getByRole('region', { name: 'Uso de GitHub Copilot' });
    await user.type(within(copilot).getByLabelText(/Token personal/, { selector: 'input' }), 'ghp_x');
    expect(within(copilot).getByRole('button', { name: 'Guardar Uso de GitHub Copilot' })).toBeDisabled();
    expect(within(copilot).getByText(/hace falta el cifrado/)).toBeInTheDocument();
  });

  it('muestra el error de la API', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { status: 500, body: { title: 'Error interno', status: 500 } },
    });

    renderRoute('/admin/ai-settings');

    expect(await screen.findByRole('alert')).toHaveTextContent('Error interno');
  });

  it('un usuario sin rol admin no la ve', async () => {
    stubApi({ ...session(USER) });

    renderRoute('/admin/ai-settings');

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
  });
});

describe('AiUsagePage', () => {
  it('muestra el coste, los errores y lo que falta configurar', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-usage': (request) => ({
        body: {
          sources: [
            {
              source: 'litellm',
              configured: true,
              fetched_at: '2026-11-02T08:00:00Z',
              cached: new URL(request.url).searchParams.get('refresh') !== 'true',
              period_start: '2026-11-02',
              period_end: '2026-11-02',
              total_cost_usd: 1.25,
              items: [
                {
                  date: '2026-11-02',
                  product: 'anthropic',
                  sku: 'equipo',
                  quantity: 1.25,
                  unit_type: 'usd',
                  cost_usd: 1.25,
                },
              ],
              error: null,
            },
            {
              source: 'github_copilot',
              configured: true,
              fetched_at: '2026-11-02T08:00:00Z',
              cached: false,
              period_start: null,
              period_end: null,
              total_cost_usd: null,
              items: [],
              error: 'ai_auth',
            },
          ],
        },
      }),
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai-usage');

    const litellm = await screen.findByRole('region', { name: 'LiteLLM' });
    expect(within(litellm).getByText(/Total:/)).toHaveTextContent('1,25');
    expect(within(litellm).getByText('equipo')).toBeInTheDocument();
    const copilot = screen.getByRole('region', { name: 'GitHub Copilot' });
    expect(within(copilot).getByRole('alert')).toHaveTextContent(/rechazó la clave/);

    await user.click(screen.getByRole('button', { name: 'Actualizar' }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/admin/ai-usage').some(
          (request) => new URL(request.url).searchParams.get('refresh') === 'true',
        ),
      ).toBe(true),
    );
  });

  it('sin configurar enlaza a la configuración', async () => {
    const empty = {
      configured: false,
      fetched_at: null,
      cached: false,
      period_start: null,
      period_end: null,
      total_cost_usd: null,
      items: [],
      error: null,
    };
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-usage': {
        body: {
          sources: [
            { source: 'litellm', ...empty },
            { source: 'github_copilot', ...empty },
          ],
        },
      },
    });

    renderRoute('/admin/ai-usage');

    expect(await screen.findAllByRole('link', { name: 'Configurar' })).toHaveLength(2);
  });
});
