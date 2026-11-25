import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

const LOCATIONS = {
  items: [
    {
      id: 1,
      name: 'Origen',
      display_path: null,
      kind: 'local',
      usage: 'source',
      access: 'ro',
      status: 'ok',
      status_reasons: [],
      probed_at: null,
    },
    {
      id: 2,
      name: 'Salidas',
      display_path: null,
      kind: 'local',
      usage: 'destination',
      access: 'rw',
      status: 'ok',
      status_reasons: [],
      probed_at: null,
    },
  ],
  total: 2,
};

function folders(locationId: number, names: string[]) {
  return {
    body: {
      location_id: locationId,
      path: '',
      parent: null,
      items: names.map((name) => ({ name, path: name })),
      total: names.length,
    },
  };
}

const MEMBERS = {
  items: [
    { user_id: 2, username: 'ana', display_name: 'Ana', role: 'owner', added_at: '2026-11-01T08:00:00Z' },
  ],
};

function detailRoutes(project: Record<string, unknown> = PROJECT) {
  return {
    ...session(USER),
    'GET /api/v1/projects/7': { body: project },
    'GET /api/v1/runs': { body: { items: [], total: 0 } },
    'GET /api/v1/projects/7/members': { body: MEMBERS },
    'GET /api/v1/locations': { body: LOCATIONS },
  };
}

/** Elige `option` en el `Select` de Mantine `name` (las opciones viven en un portal con transición). */
async function choose(user: ReturnType<typeof userEvent.setup>, name: string | RegExp, option: string) {
  const box = screen.getByRole('combobox', {
    name: typeof name === 'string' ? new RegExp(`^${name}`) : name,
  });
  await user.click(box);
  const listbox = await waitFor(() => {
    const element = document.getElementById(box.getAttribute('aria-controls') ?? '');
    expect(element).not.toBeNull();
    return element as HTMLElement;
  });
  await user.click(within(listbox).getByRole('option', { name: option, hidden: true }));
}

describe('ProjectsPage', () => {
  it('lista los proyectos con el rol y la última ejecución', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects': {
        body: {
          items: [{ ...PROJECT, role: 'viewer', last_run: { ...runOut(), status: 'succeeded' } }],
          total: 1,
        },
      },
    });

    renderRoute('/projects');

    expect(await screen.findByRole('link', { name: 'Proyecto A' })).toHaveAttribute('href', '/projects/7');
    expect(screen.getByText('Lector')).toBeInTheDocument();
    expect(screen.getByText('Terminada')).toBeInTheDocument();
  });

  it('muestra el estado vacío', async () => {
    stubApi({ ...session(USER), 'GET /api/v1/projects': { body: { items: [], total: 0 } } });

    renderRoute('/projects');

    expect(await screen.findByText(/Todavía no participas en ningún proyecto/)).toBeInTheDocument();
  });

  it('crea un proyecto con carpeta de salidas nueva', async () => {
    const fetchMock = stubApi({
      ...detailRoutes(),
      'GET /api/v1/projects': { body: { items: [], total: 0 } },
      'GET /api/v1/fs/browse': (request) => {
        const id = Number(new URL(request.url).searchParams.get('location_id'));
        return id === 1 ? folders(1, ['2024', '2025']) : folders(2, ['archivo']);
      },
      'POST /api/v1/projects': { status: 201, body: PROJECT },
    });
    const user = userEvent.setup();

    renderRoute('/projects');
    await user.click(await screen.findByRole('button', { name: 'Nuevo proyecto' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Nombre/ }), 'Proyecto A');
    await choose(user, 'Ubicación de origen', 'Origen');
    await user.click(await within(dialog).findByRole('button', { name: /2024/ }));
    await user.click(
      within(dialog).getAllByRole('button', { name: 'Elegir esta carpeta' })[0] as HTMLElement,
    );
    await choose(user, 'Ubicación de destino', 'Salidas');
    await user.type(
      within(dialog).getByRole('textbox', { name: /Nombre de la carpeta nueva/ }),
      'Proyecto A',
    );
    await user.click(within(dialog).getByRole('button', { name: 'Crear proyecto' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects');
    expect(await request?.json()).toEqual({
      name: 'Proyecto A',
      description: null,
      source_location_id: 1,
      source_subpaths: ['2024'],
      destination_location_id: 2,
      destination_parent: '',
      new_folder: 'Proyecto A',
    });
    expect(await screen.findByRole('heading', { name: 'Proyecto A' })).toBeInTheDocument();
  });

  it('con el destino vacío explica la raíz y deja crear una carpeta nueva en ella', async () => {
    stubApi({
      ...detailRoutes(),
      'GET /api/v1/projects': { body: { items: [], total: 0 } },
      'GET /api/v1/fs/browse': (request) => {
        const id = Number(new URL(request.url).searchParams.get('location_id'));
        return id === 1 ? folders(1, ['2024']) : folders(2, []);
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects');
    await user.click(await screen.findByRole('button', { name: 'Nuevo proyecto' }));
    const dialog = await screen.findByRole('dialog');
    await choose(user, 'Ubicación de destino', 'Salidas');
    await user.click(within(dialog).getByRole('radio', { name: 'Usar una carpeta vacía' }));

    expect(await within(dialog).findByText('Esta carpeta no tiene subcarpetas.')).toBeInTheDocument();
    const select = within(dialog).getByRole('button', { name: 'Elegir esta carpeta' });
    expect(select).toBeDisabled();
    expect(within(dialog).getByText(/no puede ser la carpeta del proyecto/)).toBeInTheDocument();

    await user.click(within(dialog).getByRole('radio', { name: 'Crear carpeta nueva' }));
    await user.click(within(dialog).getByRole('button', { name: 'Elegir esta carpeta' }));
    expect(within(dialog).getByText('Carpeta elegida: la raíz de «Salidas»')).toBeInTheDocument();
  });

  it('no deja crear sin carpetas de origen', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects': { body: { items: [], total: 0 } },
      'GET /api/v1/locations': { body: LOCATIONS },
      'GET /api/v1/fs/browse': folders(1, ['2024']),
    });
    const user = userEvent.setup();

    renderRoute('/projects');
    await user.click(await screen.findByRole('button', { name: 'Nuevo proyecto' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Nombre/ }), 'X');
    await choose(user, 'Ubicación de origen', 'Origen');
    await user.click(within(dialog).getByRole('button', { name: 'Crear proyecto' }));

    expect(await within(dialog).findByText('Añade al menos una carpeta de origen')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', '/api/v1/projects')).toHaveLength(0);
  });
});

describe('ProjectDetailPage', () => {
  it('un lector no ve acciones de propietario ni la prueba del motor', async () => {
    stubApi(detailRoutes({ ...PROJECT, role: 'viewer' }));

    renderRoute('/projects/7');

    expect(await screen.findByRole('heading', { name: 'Proyecto A' })).toBeInTheDocument();
    expect(screen.queryByText('Zona de peligro')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Probar el motor' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Añadir' })).not.toBeInTheDocument();
  });

  it('vaciar el histórico exige vista previa y escribir el nombre', async () => {
    const preview = runOut({
      id: '22222222-2222-4222-8222-222222222222',
      operation: 'history_clear',
      status: 'succeeded',
      params: { operation: 'history_clear', dry_run: true },
      result: { output_files: 3, output_bytes: 2048, state_files: 1, state_bytes: 10 },
      can_cancel: false,
    });
    const real = runOut({
      id: '33333333-3333-4333-8333-333333333333',
      operation: 'history_clear',
      is_write: true,
    });
    const fetchMock = stubApi({
      ...detailRoutes(),
      'POST /api/v1/projects/7/runs': async (request) => {
        const body = (await request.clone().json()) as { dry_run: boolean };
        return { status: 202, body: body.dry_run ? preview : real };
      },
      [`GET /api/v1/runs/${preview.id}`]: { body: preview },
      [`GET /api/v1/runs/${real.id}`]: { body: real },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7');
    await user.click(await screen.findByRole('button', { name: 'Vaciar histórico' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Ver vista previa' }));
    expect(await within(dialog).findByText('2 KB')).toBeInTheDocument();
    const confirm = within(dialog).getByRole('button', { name: 'Vaciar histórico' });
    expect(confirm).toBeDisabled();
    await user.type(within(dialog).getByRole('textbox', { name: /Escribe/ }), 'Proyecto A');
    await user.click(confirm);

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(2));
    const [first, second] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await first?.json()).toEqual({ operation: 'history_clear', dry_run: true });
    expect(await second?.json()).toEqual({
      operation: 'history_clear',
      dry_run: false,
      preview_run_id: preview.id,
      confirm_name: 'Proyecto A',
    });
    expect(await screen.findByRole('heading', { name: 'Vaciar histórico' })).toBeInTheDocument();
  });

  it('el propietario invita a un usuario buscándolo', async () => {
    const fetchMock = stubApi({
      ...detailRoutes(),
      'GET /api/v1/users/lookup': {
        body: { items: [{ id: 3, username: 'bea', display_name: 'Bea' }] },
      },
      'POST /api/v1/projects/7/members': {
        status: 201,
        body: {
          user_id: 3,
          username: 'bea',
          display_name: 'Bea',
          role: 'editor',
          added_at: '2026-11-01T09:00:00Z',
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7');
    await user.type(await screen.findByRole('combobox', { name: /Invitar a/ }), 'be');
    await choose(user, /Invitar a/, 'Bea (bea)');
    await choose(user, /^Rol$/, 'Editor');
    await user.click(screen.getByRole('button', { name: 'Añadir' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/members')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/members');
    expect(await request?.json()).toEqual({ user_id: 3, role: 'editor' });
  });

  it('el propietario activa guardar el propietario de los ficheros (web 1.5.0)', async () => {
    const fetchMock = stubApi({
      ...detailRoutes(),
      'PATCH /api/v1/projects/7': { body: { ...PROJECT, capture_owner: true } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7');
    await user.click(await screen.findByRole('button', { name: 'Editar' }));
    const dialog = await screen.findByRole('dialog');
    const checkbox = within(dialog).getByRole('checkbox', { name: /propietario de cada fichero/ });
    expect(checkbox).not.toBeChecked();
    expect(within(dialog).getByText(/dato personal/)).toBeInTheDocument();
    await user.click(checkbox);
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/projects/7')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PATCH', '/api/v1/projects/7');
    expect(await request?.json()).toEqual({ name: 'Proyecto A', description: '', capture_owner: true });
  });
});

describe('2.7: exclusiones del proyecto', () => {
  const EXCLUSIONS = {
    excluded: [{ path: '2024/borradores', exists: true }],
    ignore_patterns: ['*.tmp'],
    exclude_system_folders: true,
    system_patterns: ['#recycle', 'Thumbs.db'],
    location_patterns: ['~$*'],
  };

  it('el propietario las ve y las cambia: patrones y preset de carpetas de sistema', async () => {
    const fetchMock = stubApi({
      ...detailRoutes(),
      'GET /api/v1/projects/7/exclusions': { body: EXCLUSIONS },
      'GET /api/v1/fs/browse': folders(1, ['2024']),
      'PUT /api/v1/projects/7/exclusions': { body: { ...EXCLUSIONS, exclude_system_folders: false } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7');

    expect(await screen.findByText('/2024/borradores')).toBeInTheDocument();
    expect(screen.getByText('La ubicación de origen excluye además estos patrones')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Editar las exclusiones del proyecto' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(
      within(dialog).getByLabelText(/Patrones de nombre/, { selector: 'input:not([type=hidden])' }),
      'old_*{enter}',
    );
    await user.click(within(dialog).getByRole('switch', { name: /Excluir carpetas de sistema/ }));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PUT', '/api/v1/projects/7/exclusions')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/projects/7/exclusions');
    expect(await request?.json()).toEqual({
      excluded: ['2024/borradores'],
      ignore_patterns: ['*.tmp', 'old_*'],
      exclude_system_folders: false,
    });
  });

  it('un lector las ve sin poder cambiarlas', async () => {
    stubApi({
      ...detailRoutes({ ...PROJECT, role: 'viewer' }),
      'GET /api/v1/projects/7/exclusions': { body: EXCLUSIONS },
    });

    renderRoute('/projects/7');

    expect(await screen.findByText('/2024/borradores')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Editar las exclusiones del proyecto' }),
    ).not.toBeInTheDocument();
  });
});

describe('W4: IA del proyecto', () => {
  it('desactivar la redacción pide confirmación y la guarda', async () => {
    const fetchMock = stubApi({
      ...detailRoutes(),
      'PUT /api/v1/projects/7/ai-settings': { body: { ...PROJECT, ai_redact_credentials: false } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7');
    const card = await screen.findByRole('region', { name: 'Contexto e IA del proyecto' });
    const toggle = within(card).getByRole('switch', { name: /Redactar credenciales/ });
    expect(toggle).toBeChecked();
    await user.click(toggle);
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText(/se enviarán tal cual/)).toBeInTheDocument();
    await user.click(within(dialog).getByRole('button', { name: 'Desactivar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PUT', '/api/v1/projects/7/ai-settings')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/projects/7/ai-settings');
    expect(await request?.json()).toEqual({ ai_redact_credentials: false });
  });
});

describe('W6: semántica del proyecto', () => {
  it('con la semántica activada avisa si falta la IA y se puede desactivar', async () => {
    const fetchMock = stubApi({
      ...detailRoutes({ ...PROJECT, context_semantic: true }),
      'GET /api/v1/ai/status': {
        body: {
          families: { litellm: false, litellm_usage: false },
          tasks: { classify: false, enrich: false, taxonomy_design: false, agent: false, embed: false },
        },
      },
      'PUT /api/v1/projects/7/ai-settings': { body: PROJECT },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7');
    const card = await screen.findByRole('region', { name: 'Contexto e IA del proyecto' });
    expect(
      await within(card).findByText(
        /no está configurada para «Embeddings \(semántica\)»: la construcción se hará sin semántica/,
      ),
    ).toBeInTheDocument();
    expect(within(card).getByRole('textbox', { name: /Similitud mínima/ })).toHaveValue('0.75');
    await user.click(within(card).getByRole('switch', { name: /Clasificación semántica/ }));

    await waitFor(() => expect(callsTo(fetchMock, 'PUT', '/api/v1/projects/7/ai-settings')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/projects/7/ai-settings');
    expect(await request?.json()).toEqual({ context_semantic: false });
  });
});

describe('2.5.0: versiones entre formatos', () => {
  it('la casilla solo aparece si se usan versiones y se guarda al pulsarla', async () => {
    const fetchMock = stubApi({
      ...detailRoutes({ ...PROJECT, context_versions: 'mark' }),
      'PUT /api/v1/projects/7/ai-settings': { body: PROJECT },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7');
    const card = await screen.findByRole('region', { name: 'Contexto e IA del proyecto' });
    await user.click(
      within(card).getByRole('switch', { name: /Agrupar versiones aunque cambie el formato/ }),
    );

    await waitFor(() => expect(callsTo(fetchMock, 'PUT', '/api/v1/projects/7/ai-settings')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/projects/7/ai-settings');
    expect(await request?.json()).toEqual({ context_versions_across_extensions: true });
  });

  it('con «todas» no hay grupos de versiones y la casilla no aparece', async () => {
    stubApi(detailRoutes({ ...PROJECT, context_versions: 'all' }));

    renderRoute('/projects/7');
    const card = await screen.findByRole('region', { name: 'Contexto e IA del proyecto' });

    expect(within(card).queryByRole('switch', { name: /Agrupar versiones/ })).not.toBeInTheDocument();
  });
});

describe('Fase 10: menú del proyecto', () => {
  it('con un proyecto abierto, Duplicados va la primera', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/members': { body: { items: [], total: 0 } },
      'GET /api/v1/runs': { body: { items: [], total: 0 } },
    });

    renderRoute('/projects/7');

    const nav = await screen.findByRole('navigation', { name: 'Navegación principal' });
    await within(nav).findByRole('link', { name: 'Duplicados' });
    // 2.1.1: las secciones van en el bloque del proyecto abierto, tras el enlace al propio proyecto.
    const group = within(nav).getByRole('group', { name: 'Proyecto abierto: Proyecto A' });
    const names = within(group)
      .getAllByRole('link')
      .map((link) => link.textContent);
    expect(names.slice(1)).toEqual(['Duplicados', 'Escaneo', 'Documentos', 'Contexto']);
    const buttons = screen.getAllByRole('link').filter((link) => link.closest('nav') === null);
    const order = buttons
      .map((link) => link.textContent)
      .filter((text) => ['Duplicados', 'Documentos'].includes(text ?? ''));
    expect(order[0]).toBe('Duplicados');
  });
});
