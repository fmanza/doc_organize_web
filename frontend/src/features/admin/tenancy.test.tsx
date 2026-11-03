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
  it('los base son de solo lectura y un rol propio se edita', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/roles': { body: ROLES },
      'PATCH /api/v1/roles/3': { body: { ...ROLES.items[1], permissions: ['audit.read', 'users.manage'] } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/roles');

    const builtin = await screen.findByRole('region', { name: 'Administrador' });
    expect(within(builtin).getByRole('checkbox', { name: /Gestionar usuarios/ })).toBeDisabled();
    expect(within(builtin).queryByRole('button', { name: /Borrar/ })).not.toBeInTheDocument();
    const custom = screen.getByRole('region', { name: 'Auditoría' });
    await user.click(within(custom).getByRole('checkbox', { name: /Gestionar usuarios/ }));
    await user.click(within(custom).getByRole('button', { name: 'Guardar el rol Auditoría' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/roles/3')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PATCH', '/api/v1/roles/3');
    expect(await request?.json()).toEqual({ name: 'Auditoría', permissions: ['audit.read', 'users.manage'] });
  });

  it('no deja marcar permisos que uno no tiene', async () => {
    const manager = { ...USER, permissions: ['roles.manage', 'audit.read'] };
    stubApi({ ...session(manager as never), 'GET /api/v1/roles': { body: ROLES } });

    renderRoute('/admin/roles');

    const create = await screen.findByRole('region', { name: 'Nuevo rol' });
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
