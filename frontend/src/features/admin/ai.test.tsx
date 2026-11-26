import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';

function field(name: string, overrides: Record<string, unknown> = {}) {
  const secret = name.startsWith('virtual_key') || name === 'pat';
  return {
    name,
    env_var: `DOC_ORGANIZE_X_${name.toUpperCase()}`,
    secret,
    required: ['base_url', 'virtual_key', 'username', 'pat'].includes(name),
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

// doc_organize 2.0 (W2): una familia `litellm` con modelo y clave por tarea.
const LITELLM = [
  'base_url',
  'virtual_key',
  'model_classify',
  'model_enrich',
  'virtual_key_enrich',
  'budget_enrich',
];
const SETTINGS = {
  encryption_configured: true,
  families: [
    family(
      'litellm',
      LITELLM,
      {
        base_url: { source: 'db', value: 'https://litellm.example.internal' },
        virtual_key: { source: 'db', hint: '…ab12' },
        virtual_key_enrich: { source: 'env', hint: '***' },
      },
      true,
    ),
    family('litellm_usage', ['base_url', 'virtual_key']),
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

    renderRoute('/admin/ai-settings'); // URL de 1.5: redirige a /admin/ai/settings (W1)

    const models = await screen.findByRole('region', { name: 'Conexión con LiteLLM' });
    expect(within(models).getByText('Configurada')).toBeInTheDocument();
    expect(within(models).getByText('Guardada: …ab12')).toBeInTheDocument();
    expect(within(models).getByLabelText(/Clave virtual/, { selector: 'input' })).toHaveValue('');
    // 2.0: modelo, clave y presupuesto por tarea en la misma tarjeta.
    expect(within(models).getByText('Variable del servidor')).toBeInTheDocument();
    expect(
      within(models).getByLabelText(/Clave propia para describir/, { selector: 'input' }),
    ).toBeInTheDocument();
    expect(
      within(models).getByLabelText(/Máximo de documentos a describir/, { selector: 'input' }),
    ).toBeInTheDocument();

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

  it('solo las familias con modelo lo prueban, y sin obligatorios no se prueba (1.7)', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/admin/ai-settings': { body: SETTINGS } });

    renderRoute('/admin/ai/settings');

    const usage = await screen.findByRole('region', { name: 'Uso de LiteLLM' });
    expect(within(usage).queryByRole('button', { name: /Probar el modelo/ })).not.toBeInTheDocument();
    expect(
      within(usage).getByRole('button', { name: 'Probar la conexión de Uso de LiteLLM' }),
    ).toBeDisabled();
  });

  // 2.2: la familia `litellm` real lleva campos por tarea: conexión arriba y una fila por funcionalidad.
  const TASKS_FAMILY = family(
    'litellm',
    [
      'base_url',
      'virtual_key',
      'model_classify',
      'model_enrich',
      'virtual_key_enrich',
      'budget_enrich',
      'model_dedup',
      'virtual_key_dedup',
    ],
    {
      base_url: { source: 'db', value: 'https://litellm.example.internal' },
      virtual_key: { source: 'db', hint: '…ab12' },
      model_classify: { task: 'classify' },
      model_enrich: { task: 'enrich', source: 'db', value: 'descriptor' },
      virtual_key_enrich: { task: 'enrich' },
      budget_enrich: { task: 'enrich', env_var: null },
      model_dedup: { task: 'dedup' },
      virtual_key_dedup: { task: 'dedup' },
    },
    true,
  );
  const TESTED = {
    ok: true,
    error: null,
    model_access: 'unknown',
    model_checked: true,
    elapsed_ms: 300,
    tested_at: '2026-11-22T09:00:00Z',
  };

  it('prueba la conexión sin guardar y lo dice en un aviso flotante (2.2)', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { body: { ...SETTINGS, families: [TASKS_FAMILY] } },
      'POST /api/v1/admin/ai-settings/litellm/test': {
        body: { ...TESTED, model_access: 'denied', model_checked: false, elapsed_ms: 412 },
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai/settings');
    const connection = await screen.findByRole('region', { name: 'Conexión con LiteLLM' });
    await user.click(
      within(connection).getByRole('button', { name: 'Probar la conexión de Conexión con LiteLLM' }),
    );

    expect(await screen.findByText('Conexión con LiteLLM: conexión correcta')).toBeInTheDocument();
    expect(screen.getByText(/412 ms/)).toBeInTheDocument();
    expect(screen.getByText(/esta clave no tiene acceso al modelo/)).toBeInTheDocument();
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/admin/ai-settings/litellm/test');
    expect(await request?.clone().json()).toEqual({ fields: {}, model_check: false, task: 'classify' });
    expect(callsTo(fetchMock, 'PUT', '/api/v1/admin/ai-settings/litellm')).toHaveLength(0);
  });

  it('una fila por funcionalidad: modelo, alias recomendado y desactivada sin modelo propio (2.2)', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': {
        body: {
          ...SETTINGS,
          families: [TASKS_FAMILY],
        },
      },
    });

    renderRoute('/admin/ai/settings');

    const table = await screen.findByRole('region', { name: 'Modelos por funcionalidad' });
    const rows = within(table).getAllByRole('row');
    const row = (name: RegExp) => rows.find((item) => name.test(item.textContent ?? '')) as HTMLElement;
    expect(
      within(row(/^Clasificar/)).getByText(/doc-organize-classify \(alias recomendado\)/),
    ).toBeInTheDocument();
    expect(within(row(/^Describir/)).getByText('descriptor')).toBeInTheDocument();
    expect(within(row(/^Describir/)).getByText(/Se usa en: construir el contexto/)).toBeInTheDocument();
    const dedup = row(/^Duplicados por contenido/);
    expect(within(dedup).getByText('Desactivada: sin modelo')).toBeInTheDocument();
    expect(
      within(dedup).getByRole('button', { name: 'Probar el modelo de la tarea Duplicados por contenido' }),
    ).toBeDisabled();
  });

  it('edita una funcionalidad en el panel lateral y el aviso dice qué modelo respondió (2.2)', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { body: { ...SETTINGS, families: [TASKS_FAMILY] } },
      'POST /api/v1/admin/ai-settings/litellm/test': {
        body: {
          ...TESTED,
          task: 'dedup',
          model: 'bge-local',
          served_model: 'ollama/bge-m3',
          dimension: 1024,
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai/settings');
    const table = await screen.findByRole('region', { name: 'Modelos por funcionalidad' });
    await user.click(within(table).getByRole('button', { name: 'Editar Duplicados por contenido' }));
    const drawer = await screen.findByRole('dialog', { name: 'Duplicados por contenido' });
    expect(within(drawer).getByText('Necesita su propio modelo')).toBeInTheDocument();
    await user.type(
      within(drawer).getByLabelText(/Modelo de embeddings de duplicados/, { selector: 'input' }),
      'bge-local',
    );
    await user.click(
      within(drawer).getByRole('button', { name: 'Probar el modelo de la tarea Duplicados por contenido' }),
    );

    expect(await screen.findByText('Duplicados por contenido: el modelo responde')).toBeInTheDocument();
    expect(screen.getByText('Modelo: bge-local → ollama/bge-m3')).toBeInTheDocument();
    expect(screen.getByText(/1024 dimensiones · 300 ms/)).toBeInTheDocument();
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/admin/ai-settings/litellm/test');
    expect(await request?.clone().json()).toEqual({
      fields: { model_dedup: 'bge-local' },
      model_check: true,
      task: 'dedup',
    });
    expect(callsTo(fetchMock, 'PUT', '/api/v1/admin/ai-settings/litellm')).toHaveLength(0);
  });

  it('un fallo del modelo se queda en un aviso hasta cerrarlo y la fila lo dice (2.2)', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { body: { ...SETTINGS, families: [TASKS_FAMILY] } },
      'POST /api/v1/admin/ai-settings/litellm/test': {
        body: {
          ...TESTED,
          ok: false,
          error: 'ai_model',
          task: 'enrich',
          model: 'descriptor',
          elapsed_ms: 900,
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai/settings');
    const table = await screen.findByRole('region', { name: 'Modelos por funcionalidad' });
    await user.click(
      within(table).getByRole('button', {
        name: 'Probar el modelo de la tarea Describir (descripción y palabras clave)',
      }),
    );

    const alert = await screen.findByRole('alert');
    expect(within(alert).getByText(/la prueba falló/)).toBeInTheDocument();
    expect(within(alert).getByText(/El modelo no respondió/)).toBeInTheDocument();
    expect(within(alert).getByText('Modelo: descriptor')).toBeInTheDocument();
    expect(within(table).getByText('Falló')).toBeInTheDocument();
    await user.click(within(alert).getByRole('button', { name: 'Cerrar' }));
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('«Probar todos los modelos» prueba una tras otra las que tienen modelo (2.2)', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { body: { ...SETTINGS, families: [TASKS_FAMILY] } },
      'POST /api/v1/admin/ai-settings/litellm/test': async (request) => {
        const body = (await request.clone().json()) as { task: string };
        return { body: { ...TESTED, task: body.task, model: `modelo-${body.task}` } };
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai/settings');
    const table = await screen.findByRole('region', { name: 'Modelos por funcionalidad' });
    await user.click(within(table).getByRole('button', { name: 'Probar todos los modelos' }));

    await waitFor(() => expect(within(table).getAllByText('Correcta · 300 ms')).toHaveLength(2));
    const tasks = await Promise.all(
      callsTo(fetchMock, 'POST', '/api/v1/admin/ai-settings/litellm/test').map(
        async (call) => ((await call.clone().json()) as { task: string }).task,
      ),
    );
    expect(tasks).toEqual(['classify', 'enrich']); // dedup no: sin modelo propio
  });

  it('borra un valor guardado', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { body: SETTINGS },
      'PUT /api/v1/admin/ai-settings/litellm': { body: SETTINGS.families[0] },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai/settings');

    await user.click(
      await screen.findByRole('button', { name: 'Borrar el valor guardado de Clave virtual' }),
    );

    await waitFor(() =>
      expect(callsTo(fetchMock, 'PUT', '/api/v1/admin/ai-settings/litellm')).toHaveLength(1),
    );
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/admin/ai-settings/litellm');
    expect(await request?.clone().json()).toEqual({ fields: { virtual_key: null } });
  });

  it('sin cifrado avisa y no deja guardar claves', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { body: { ...SETTINGS, encryption_configured: false } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai/settings');

    expect(await screen.findByText('Cifrado no configurado')).toBeInTheDocument();
    const usage = screen.getByRole('region', { name: 'Uso de LiteLLM' });
    await user.type(within(usage).getByLabelText(/Clave virtual/, { selector: 'input' }), 'sk-x');
    expect(within(usage).getByRole('button', { name: 'Guardar Uso de LiteLLM' })).toBeDisabled();
    expect(within(usage).getByText(/hace falta el cifrado/)).toBeInTheDocument();
    // 2.1: sin GitHub Copilot.
    expect(screen.queryByRole('region', { name: 'Uso de GitHub Copilot' })).not.toBeInTheDocument();
  });

  it('muestra el error de la API', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-settings': { status: 500, body: { title: 'Error interno', status: 500 } },
    });

    renderRoute('/admin/ai/settings');

    expect(await screen.findByRole('alert')).toHaveTextContent('Error interno');
  });

  it('un usuario sin rol admin no la ve', async () => {
    stubApi({ ...session(USER) });

    renderRoute('/admin/ai/settings');

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
  });
});

const TOTALS = {
  runs: 2,
  calls: 6,
  cached: 2,
  failed: 0,
  prompt_tokens: 12000,
  completion_tokens: 800,
  tokens_estimated: false,
};
const LOCAL = {
  period: '30d',
  timezone: 'Europe/Madrid',
  start: '2026-10-24T22:00:00Z',
  end: '2026-11-22T12:00:00Z',
  totals: TOTALS,
  by_task: [{ key: 'classify', label: null, project_id: null, ...TOTALS }],
  by_model: [{ key: 'modelo-sintetico', label: null, project_id: null, ...TOTALS }],
  by_project: [{ key: '7', label: 'Proyecto A', project_id: 7, ...TOTALS }],
  by_day: [
    { day: '2026-11-21', ...TOTALS, prompt_tokens: 5000, completion_tokens: 300 },
    { day: '2026-11-22', ...TOTALS, prompt_tokens: 7000, completion_tokens: 500 },
  ],
  top_runs: [
    {
      run_id: '55555555-5555-4555-8555-555555555555',
      created_at: '2026-11-22T09:00:00Z',
      operation: 'context_build',
      project_id: 7,
      project_name: 'Proyecto A',
      ...TOTALS,
    },
  ],
};
const KEY_SOURCE = {
  source: 'litellm',
  configured: true,
  fetched_at: '2026-11-02T08:00:00Z',
  cached: true,
  period_start: '2026-11-02',
  period_end: '2026-11-02',
  total_cost_usd: 1.25,
  items: [],
  budget: { spend: 1.25, max_budget: 10, remaining: 8.75, budget_reset_at: null },
  error: null,
};

describe('AiUsagePage', () => {
  it('muestra indicadores, el presupuesto de la clave, los tokens por día y las tablas', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-usage': (request) => {
        const period = new URL(request.url).searchParams.get('period');
        return {
          body: {
            sources: [{ ...KEY_SOURCE, cached: new URL(request.url).searchParams.get('refresh') !== 'true' }],
            local: { ...LOCAL, period },
          },
        };
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai/usage');

    const key = await screen.findByRole('region', { name: 'Clave de LiteLLM' });
    expect(within(key).getByText('Gasto acumulado').nextSibling).toHaveTextContent('1,25');
    expect(within(key).getByText('Queda').nextSibling).toHaveTextContent('8,75');
    expect(
      within(key).getByRole('progressbar', { name: '13 % del presupuesto gastado' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Tokens de entrada', { selector: 'dt' }).nextSibling).toHaveTextContent('12.000');
    expect(screen.getByText('25 % sin llamar al modelo')).toBeInTheDocument();
    expect(screen.getByText('Días en hora local (Europe/Madrid)')).toBeInTheDocument();
    expect(
      screen.getByRole('img', { name: /Tokens de entrada y de salida por día, 2 días/ }),
    ).toBeInTheDocument();
    const byTask = screen.getByRole('region', { name: 'Por tarea' });
    expect(within(byTask).getByText('Clasificar')).toBeInTheDocument();
    expect(
      within(screen.getByRole('region', { name: 'Por proyecto' })).getByRole('link', { name: 'Proyecto A' }),
    ).toHaveAttribute('href', '/projects/7');
    const top = screen.getByRole('region', { name: 'Ejecuciones que más tokens gastaron' });
    expect(within(top).getByRole('link')).toHaveAttribute(
      'href',
      '/runs/55555555-5555-4555-8555-555555555555',
    );
    expect(screen.queryByText(/Copilot/)).not.toBeInTheDocument();

    // El periodo y la zona del navegador van a la API.
    await user.click(screen.getByRole('radio', { name: '7 días' }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/admin/ai-usage').some((request) => {
          const query = new URL(request.url).searchParams;
          return query.get('period') === '7d' && query.has('tz');
        }),
      ).toBe(true),
    );
    await user.click(screen.getByRole('button', { name: 'Actualizar' }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/admin/ai-usage').some(
          (request) => new URL(request.url).searchParams.get('refresh') === 'true',
        ),
      ).toBe(true),
    );
  });

  it('sin consumo lo dice; con error de la clave lo avisa sin ocultar el resto', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-usage': {
        body: {
          sources: [{ ...KEY_SOURCE, budget: null, total_cost_usd: null, error: 'ai_auth' }],
          local: {
            ...LOCAL,
            totals: { ...TOTALS, runs: 0, calls: 0, cached: 0, prompt_tokens: 0, completion_tokens: 0 },
            by_task: [],
            by_model: [],
            by_project: [],
            by_day: [],
            top_runs: [],
          },
        },
      },
    });

    renderRoute('/admin/ai/usage');

    const key = await screen.findByRole('region', { name: 'Clave de LiteLLM' });
    expect(within(key).getByRole('alert')).toHaveTextContent(/rechazó la clave/);
    expect(screen.getByText('Todavía no hay consumo de IA registrado en este periodo.')).toBeInTheDocument();
  });

  it('sin configurar enlaza a la configuración', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/ai-usage': {
        body: {
          sources: [
            {
              source: 'litellm',
              configured: false,
              fetched_at: null,
              cached: false,
              period_start: null,
              period_end: null,
              total_cost_usd: null,
              items: [],
              budget: null,
              error: null,
            },
          ],
          local: null,
        },
      },
    });

    renderRoute('/admin/ai-usage'); // URL de 1.5: redirige a /admin/ai/usage (W1)

    expect(await screen.findByRole('link', { name: 'Configurar' })).toHaveAttribute(
      'href',
      '/admin/ai/settings',
    );
    expect(screen.getByRole('link', { name: 'IA › Parámetros' })).toHaveAttribute(
      'href',
      '/admin/ai/parameters',
    );
    // La redirección deja abierto el grupo «IA» con la página actual.
    expect(screen.getByRole('link', { name: 'Uso' })).toHaveAttribute('aria-current', 'page');
  });
});

describe('AiParametersPage (W1)', () => {
  const SETTINGS = {
    items: [
      { key: 'login_max_attempts', value: 5, default: 5, source: 'default', group: 'security' },
      { key: 'ai_retries', value: 2, default: 2, source: 'default', group: 'ai' },
      { key: 'ai_max_documents_per_run', value: 0, default: 0, source: 'default', group: 'ai' },
    ],
  };

  it('muestra solo los ajustes de IA y los guarda con el PATCH de ajustes', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/admin/settings': { body: SETTINGS },
      'PATCH /api/v1/admin/settings': { body: SETTINGS },
    });
    const user = userEvent.setup();

    renderRoute('/admin/ai/parameters');

    const input = await screen.findByRole('textbox', { name: 'Reintentos de conexión con la IA' });
    expect(
      screen.queryByRole('textbox', { name: 'Intentos fallidos antes del bloqueo' }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'IA › Configuración' })).toHaveAttribute(
      'href',
      '/admin/ai/settings',
    );
    await user.clear(input);
    await user.type(input, '4');
    await user.click(screen.getByRole('button', { name: 'Guardar Reintentos de conexión con la IA' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/admin/settings')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PATCH', '/api/v1/admin/settings');
    expect(await request?.json()).toEqual({ values: { ai_retries: 4 } });
  });

  it('2.2: cada parámetro dice qué funcionalidades lo usan', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/admin/settings': { body: SETTINGS } });

    renderRoute('/admin/ai/parameters');

    const retries = await screen.findByLabelText('Funcionalidades que usan Reintentos de conexión con la IA');
    expect(within(retries).getByText('Duplicados por contenido')).toBeInTheDocument();
    expect(within(retries).getByText('Contexto semántico')).toBeInTheDocument();
    const budget = screen.getByLabelText('Funcionalidades que usan Documentos con IA por ejecución');
    expect(within(budget).getAllByText(/Clasificar|Describir/)).toHaveLength(2);
    expect(within(budget).queryByText('Duplicados por contenido')).not.toBeInTheDocument();
  });

  it('un administrador del tenant no entra', async () => {
    stubApi({ ...session({ ...ADMIN, is_instance_admin: false } as never) });

    renderRoute('/admin/ai/parameters');

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
  });
});
