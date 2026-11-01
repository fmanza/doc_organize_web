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
});
