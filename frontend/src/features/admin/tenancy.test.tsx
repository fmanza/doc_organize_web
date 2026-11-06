import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';

const OBRAS = { id: 2, slug: 'obras', name: 'Obras' };
const TENANTS = {
  items: [
    {
      id: 1,
      slug: 'default',
      name: 'Predeterminado',
      created_at: '2026-11-01T08:00:00Z',
      users: 3,
      projects: 2,
      locations: 2,
      empty: false,
    },
    { ...OBRAS, created_at: '2026-11-03T08:00:00Z', users: 0, projects: 0, locations: 0, empty: true },
  ],
  total: 2,
};
const ROLES = {
  items: [
    {
      id: 1,
      name: 'Administrador',
      builtin: 'admin',
      permissions: [
        'users.manage',
        'roles.manage',
        'audit.read',
        'templates.manage',
        'projects.create',
        'projects.all',
      ],
      users: 1,
      created_at: '2026-11-01T08:00:00Z',
      updated_at: '2026-11-01T08:00:00Z',
    },
    {
      id: 3,
      name: 'Auditoría',
      builtin: null,
      permissions: ['audit.read'],
      users: 0,
      created_at: '2026-11-03T08:00:00Z',
      updated_at: '2026-11-03T08:00:00Z',
    },
  ],
};
/** Auditora: solo `audit.read`. */
const AUDITOR = { ...USER, role: { id: 3, name: 'Auditoría', builtin: null }, permissions: ['audit.read'] };

describe('Guardas por permiso', () => {
  it('el menú solo enseña lo que el rol permite', async () => {
    stubApi({ ...session(AUDITOR as never), 'GET /api/v1/audit': { body: { items: [], total: 0 } } });

    renderRoute('/admin/audit');

    expect(await screen.findByRole('link', { name: 'Auditoría' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Usuarios' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Tenants' })).not.toBeInTheDocument();
  });

  it('sin el permiso, la página dice «sin permiso»', async () => {
    stubApi({ ...session(AUDITOR as never) });

    renderRoute('/admin/users');

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
  });

  it('un administrador del tenant no ve lo que es de la instancia', async () => {
    const tenantAdmin = { ...ADMIN, is_instance_admin: false };
    stubApi({ ...session(tenantAdmin as never) });

    renderRoute('/admin/tenants');

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Usuarios' })).toBeInTheDocument();
  });
});

describe('TenantsPage', () => {
  it('lista, crea y solo deja borrar los vacíos', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/tenants': { body: TENANTS },
      'POST /api/v1/tenants': { status: 201, body: TENANTS.items[1] },
    });
    const user = userEvent.setup();

    renderRoute('/admin/tenants');

    expect(await screen.findByText('Predeterminado', { selector: 'td' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Borrar Predeterminado' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Borrar Obras' })).toBeEnabled();
    await user.type(screen.getByRole('textbox', { name: /Identificador/ }), 'calidad');
    await user.type(screen.getByRole('textbox', { name: 'Nombre' }), 'Calidad');
    await user.click(screen.getByRole('button', { name: 'Crear tenant' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/tenants')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/tenants');
    expect(await request?.json()).toEqual({ slug: 'calidad', name: 'Calidad' });
  });

  it('actuar en otro tenant cambia el de la sesión', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/tenants': { body: TENANTS },
      'PUT /api/v1/auth/tenant': { body: { ...ADMIN, acting_tenant: OBRAS } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/tenants');

    await user.click(await screen.findByRole('button', { name: 'Actuar en Obras' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PUT', '/api/v1/auth/tenant')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/auth/tenant');
    expect(await request?.json()).toEqual({ tenant_id: 2 });
  });
});

describe('RolesPage', () => {
  // 1.2.0: listado como Usuarios (tabla, «Nuevo rol», «Editar»/«Ver» en cada fila), con orden y búsqueda.
  it('lista los roles e identifica los predeterminados', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/roles': { body: ROLES } });
    const user = userEvent.setup();

    renderRoute('/admin/roles');

    const admin = (await screen.findByRole('cell', { name: 'Administrador' })).closest('tr') as HTMLElement;
    expect(within(admin).getByText('Predeterminado')).toBeInTheDocument();
    expect(within(admin).getByText('6 permisos')).toBeInTheDocument();
    expect(within(admin).getByRole('button', { name: 'Ver el rol Administrador' })).toBeInTheDocument();
    const custom = screen.getByRole('cell', { name: 'Auditoría' }).closest('tr') as HTMLElement;
    expect(within(custom).getByText('Personalizado')).toBeInTheDocument();
    expect(within(custom).getByRole('button', { name: 'Editar el rol Auditoría' })).toBeInTheDocument();

    // Orden por usuarios, descendente: Administrador (1) antes que Auditoría (0).
    await user.click(screen.getByRole('button', { name: /^Usuarios/ }));
    await user.click(screen.getByRole('button', { name: /^Usuarios/ }));
    expect(screen.getByRole('columnheader', { name: /^Usuarios/ })).toHaveAttribute(
      'aria-sort',
      'descending',
    );
    const names = screen
      .getAllByRole('row')
      .slice(1)
      .map((row) => within(row).getAllByRole('cell')[0]?.textContent);
    expect(names).toEqual(['Administrador', 'Auditoría']);

    // Busca en el nombre y en los permisos: «plantillas» solo lo tiene Administrador.
    await user.type(screen.getByRole('textbox', { name: 'Buscar roles' }), 'plantillas');
    await waitFor(() => expect(screen.queryByRole('cell', { name: 'Auditoría' })).not.toBeInTheDocument());
    expect(screen.getByRole('cell', { name: 'Administrador' })).toBeInTheDocument();
  });

  it('los predeterminados se ven en solo lectura y uno propio se edita en el modal', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/roles': { body: ROLES },
      'PATCH /api/v1/roles/3': { body: { ...ROLES.items[1], permissions: ['audit.read', 'users.manage'] } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/roles');

    await user.click(await screen.findByRole('button', { name: 'Ver el rol Administrador' }));
    const view = await screen.findByRole('dialog');
    expect(within(view).getByRole('checkbox', { name: /Gestionar usuarios/ })).toBeDisabled();
    expect(within(view).queryByRole('button', { name: /Borrar/ })).not.toBeInTheDocument();
    expect(within(view).queryByRole('button', { name: 'Guardar' })).not.toBeInTheDocument();
    await user.click(within(view).getByRole('button', { name: 'Cerrar' }));

    await user.click(screen.getByRole('button', { name: 'Editar el rol Auditoría' }));
    const edit = await screen.findByRole('dialog');
    await user.click(within(edit).getByRole('checkbox', { name: /Gestionar usuarios/ }));
    await user.click(within(edit).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/roles/3')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PATCH', '/api/v1/roles/3');
    expect(await request?.json()).toEqual({ name: 'Auditoría', permissions: ['audit.read', 'users.manage'] });
  });

  it('borrar un rol propio pide confirmación', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/roles': { body: ROLES },
      'DELETE /api/v1/roles/3': { status: 204 },
    });
    const user = userEvent.setup();

    renderRoute('/admin/roles');

    await user.click(await screen.findByRole('button', { name: 'Editar el rol Auditoría' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Borrar el rol Auditoría' }));
    expect(within(dialog).getByText('¿Borrar el rol «Auditoría»? No se puede deshacer.')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/roles/3')).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: 'Borrar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'DELETE', '/api/v1/roles/3')).toHaveLength(1));
  });

  it('no deja marcar permisos que uno no tiene', async () => {
    const manager = { ...USER, permissions: ['roles.manage', 'audit.read'] };
    stubApi({ ...session(manager as never), 'GET /api/v1/roles': { body: ROLES } });
    const user = userEvent.setup();

    renderRoute('/admin/roles');

    await user.click(await screen.findByRole('button', { name: 'Nuevo rol' }));
    const create = await screen.findByRole('dialog');
    expect(within(create).getByRole('checkbox', { name: /Consultar la auditoría/ })).toBeEnabled();
    expect(within(create).getByRole('checkbox', { name: /Todos los proyectos/ })).toBeDisabled();
  });
});

describe('Selector de tenant', () => {
  it('el resto de usuarios ve el nombre de su tenant', async () => {
    stubApi({ ...session(USER), 'GET /api/v1/projects': { body: { items: [], total: 0 } } });

    renderRoute('/projects');

    expect(await screen.findByLabelText('Tenant: Predeterminado')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Tenant activo' })).not.toBeInTheDocument();
  });
});
