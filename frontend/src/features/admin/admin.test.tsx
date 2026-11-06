import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';

const ANA = {
  id: 2,
  username: 'ana',
  display_name: 'Ana',
  tenant_id: 1,
  role: { id: 2, name: 'Usuario', builtin: 'user' },
  is_instance_admin: false,
  is_active: true,
  locked_until: null,
  failed_attempts: 0,
  password_changed_at: '2026-10-20T08:00:00Z',
  created_at: '2026-10-20T08:00:00Z',
  updated_at: '2026-10-20T08:00:00Z',
};

describe('UsersPage', () => {
  it('lista usuarios con su estado', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': {
        body: { items: [ANA, { ...ANA, id: 3, username: 'luis', is_active: false }], total: 2 },
      },
    });

    renderRoute('/admin/users');

    expect(await screen.findByText('ana')).toBeInTheDocument();
    expect(screen.getByText('Desactivado')).toBeInTheDocument();
    expect(screen.getByText('Activo')).toBeInTheDocument();
  });

  it('muestra el estado vacío', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/users': { body: { items: [], total: 0 } } });

    renderRoute('/admin/users');

    expect(await screen.findByText('No hay usuarios que coincidan.')).toBeInTheDocument();
  });

  it('muestra el error de la API', async () => {
    stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { status: 500, body: { title: 'Error interno', status: 500 } },
    });

    renderRoute('/admin/users');

    expect(await screen.findByRole('alert')).toHaveTextContent('Error interno');
  });

  it('crea un usuario y valida el formulario', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [], total: 0 } },
      'POST /api/v1/users': { status: 201, body: { ...ANA, id: 9, username: 'luis' } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Nuevo usuario' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Crear usuario' }));
    expect(within(dialog).getByText('Debe tener al menos 12 caracteres')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', '/api/v1/users')).toHaveLength(0);

    await user.type(within(dialog).getByRole('textbox', { name: /^Usuario/ }), 'luis');
    await user.type(within(dialog).getByRole('textbox', { name: /Nombre visible/ }), 'Luis');
    await user.type(within(dialog).getByLabelText(/^Contraseña/), 'frase-de-paso-luis');
    await user.click(within(dialog).getByRole('button', { name: 'Crear usuario' }));

    await screen.findByRole('button', { name: 'Nuevo usuario' });
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/users');
    expect(await request?.json()).toEqual({
      username: 'luis',
      display_name: 'Luis',
      password: 'frase-de-paso-luis',
      role_id: null,
      is_instance_admin: false,
    });
  });

  it('desactiva un usuario enviando solo el cambio', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [ANA], total: 1 } },
      'PATCH /api/v1/users/2': { body: { ...ANA, is_active: false } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Editar ana' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('switch', { name: /Cuenta activa/ }));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await screen.findByRole('button', { name: 'Nuevo usuario' });
    const [request] = callsTo(fetchMock, 'PATCH', '/api/v1/users/2');
    expect(await request?.json()).toEqual({ unlock: false, is_active: false });
  });

  it('quita el bloqueo de un usuario bloqueado', async () => {
    const lockedUntil = new Date(Date.now() + 10 * 60_000).toISOString();
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [{ ...ANA, locked_until: lockedUntil }], total: 1 } },
      'PATCH /api/v1/users/2': { body: ANA },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    expect(await screen.findByText('Bloqueado')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Editar ana' }));
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Cuenta bloqueada por intentos fallidos')).toBeInTheDocument();
    await user.click(within(dialog).getByRole('switch', { name: 'Quitar el bloqueo ahora' }));
    await user.click(within(dialog).getByRole('button', { name: 'Guardar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'PATCH', '/api/v1/users/2')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'PATCH', '/api/v1/users/2');
    expect(await request?.json()).toEqual({ unlock: true });
  });

  it('valida el formulario de alta antes de enviarlo', async () => {
    const fetchMock = stubApi({ ...session(ADMIN), 'GET /api/v1/users': { body: { items: [], total: 0 } } });
    const user = userEvent.setup();

    renderRoute('/admin/users');
    await user.click(await screen.findByRole('button', { name: 'Nuevo usuario' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByRole('textbox', { name: /^Usuario/ }), 'a b');
    await user.type(within(dialog).getByLabelText(/^Contraseña/), 'corta');
    await user.click(within(dialog).getByRole('button', { name: 'Crear usuario' }));

    expect(await within(dialog).findByText('Debe tener al menos 12 caracteres')).toBeInTheDocument();
    expect(within(dialog).getByText('Campo obligatorio')).toBeInTheDocument();
    expect(callsTo(fetchMock, 'POST', '/api/v1/users')).toHaveLength(0);
  });
});

describe('SessionsPage', () => {
  it('revoca una sesión tras confirmar', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/sessions': {
        body: {
          items: [
            {
              id: 7,
              user_id: 2,
              username: 'ana',
              created_at: '2026-10-20T08:00:00Z',
              last_seen_at: '2026-10-20T08:05:00Z',
              expires_at: '2026-10-20T20:00:00Z',
              ip: '10.0.0.5',
              user_agent: 'Firefox',
              current: false,
            },
          ],
          total: 1,
        },
      },
      'DELETE /api/v1/sessions/7': { status: 204 },
    });
    const user = userEvent.setup();

    renderRoute('/admin/sessions');
    await user.click(await screen.findByRole('button', { name: 'Revocar sesión de ana' }));
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent('Se cerrará la sesión de ana desde 10.0.0.5.');
    await user.click(within(dialog).getByRole('button', { name: 'Revocar' }));

    await screen.findByText('Sesiones activas');
    expect(callsTo(fetchMock, 'DELETE', '/api/v1/sessions/7')).toHaveLength(1);
  });
});

describe('Mis sesiones', () => {
  it('un usuario sin rol admin ve sus sesiones', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/sessions': { body: { items: [], total: 0 } },
    });

    renderRoute('/account/sessions');

    expect(await screen.findByRole('heading', { name: 'Mis sesiones' })).toBeInTheDocument();
    expect(await screen.findByText('No hay sesiones activas.')).toBeInTheDocument();
  });
});

describe('AuditPage', () => {
  it('muestra eventos traducidos y filtra por tipo', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/audit': {
        body: {
          items: [
            {
              id: 1,
              ts: '2026-10-20T08:00:00Z',
              actor_user_id: null,
              actor_username: null,
              action: 'auth.login',
              outcome: 'failure',
              target_type: null,
              target_id: null,
              ip: '10.0.0.9',
              details: { reason: 'unknown_user' },
            },
          ],
          total: 1,
        },
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/audit');

    expect(await screen.findByText('Inicio de sesión')).toBeInTheDocument();
    expect(screen.getByText('Fallido')).toBeInTheDocument();
    expect(screen.getByText('Sistema')).toBeInTheDocument();

    await user.click(screen.getByRole('radio', { name: 'Autenticación' }));

    await waitFor(() => {
      const last = callsTo(fetchMock, 'GET', '/api/v1/audit').at(-1);
      expect(new URL(last?.url ?? '').searchParams.get('action')).toBe('auth.');
    });

    await user.type(screen.getByLabelText('Usuario que actuó'), 'admin');

    await waitFor(() => {
      const last = callsTo(fetchMock, 'GET', '/api/v1/audit').at(-1);
      expect(new URL(last?.url ?? '').searchParams.get('actor')).toBe('admin');
    });
  });
});

describe('Listados con orden y búsqueda (1.2.0)', () => {
  it('Usuarios manda la búsqueda y el orden a la API y vuelve a la página 1', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/users': { body: { items: [ANA], total: 60 } },
    });
    const user = userEvent.setup();

    renderRoute('/admin/users?page=2');

    expect(await screen.findByText('26–50 de 60')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Elementos por página' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^Alta/ }));
    await user.click(screen.getByRole('button', { name: /^Alta/ }));
    await user.type(screen.getByRole('textbox', { name: 'Buscar por usuario o nombre' }), 'an');

    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', '/api/v1/users').some((request) => {
          const params = new URL(request.url).searchParams;
          return (
            params.get('q') === 'an' &&
            params.get('sort') === 'created_at' &&
            params.get('order') === 'desc' &&
            params.get('offset') === '0' &&
            params.get('limit') === '25'
          );
        }),
      ).toBe(true),
    );
    expect(screen.getByRole('columnheader', { name: /^Alta/ })).toHaveAttribute('aria-sort', 'descending');
  });
});

describe('Eliminar auditoría por fechas (1.2.0)', () => {
  const AUDIT = { items: [], total: 0 };

  it('solo el admin de instancia ve el botón', async () => {
    const auditor = { ...USER, permissions: ['audit.read'] };
    stubApi({ ...session(auditor as never), 'GET /api/v1/audit': { body: AUDIT } });

    renderRoute('/admin/audit');

    expect(await screen.findByRole('heading', { name: 'Auditoría' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Eliminar por fechas' })).not.toBeInTheDocument();
  });

  it('comprueba, pide teclear el número y borra', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/audit': { body: AUDIT },
      'POST /api/v1/audit/purge': async (request) => {
        const body = (await request.clone().json()) as { dry_run: boolean };
        return { body: body.dry_run ? { matched: 3, deleted: 0 } : { matched: 3, deleted: 3 } };
      },
    });
    const user = userEvent.setup();

    renderRoute('/admin/audit');

    await user.click(await screen.findByRole('button', { name: 'Eliminar por fechas' }));
    const dialog = await screen.findByRole('dialog');
    await user.type(within(dialog).getByLabelText('Desde (incluido)'), '2026-01-01');
    await user.type(within(dialog).getByLabelText(/Hasta \(sin incluir\)/), '2026-02-01');
    await user.click(within(dialog).getByRole('button', { name: 'Comprobar' }));

    expect(await within(dialog).findByText('Se eliminarán 3 entradas de auditoría.')).toBeInTheDocument();
    const remove = within(dialog).getByRole('button', { name: 'Eliminar 3 entradas' });
    expect(remove).toBeDisabled();
    await user.type(within(dialog).getByRole('textbox', { name: /escribe el número de entradas/ }), '3');
    expect(remove).toBeEnabled();
    await user.click(remove);

    expect(await within(dialog).findByText('Se han eliminado 3 entradas.')).toBeInTheDocument();
    const [preview, real] = callsTo(fetchMock, 'POST', '/api/v1/audit/purge');
    expect(await preview?.json()).toEqual({
      since: '2026-01-01T00:00:00Z',
      until: '2026-02-01T00:00:00Z',
      dry_run: true,
    });
    expect(await real?.json()).toEqual({
      since: '2026-01-01T00:00:00Z',
      until: '2026-02-01T00:00:00Z',
      dry_run: false,
      confirm_count: 3,
    });
  });
});
