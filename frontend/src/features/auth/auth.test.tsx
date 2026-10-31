import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';
import { safeNext } from './useAuth';

function clearCookies() {
  for (const cookie of document.cookie.split('; ')) {
    const name = cookie.split('=')[0];
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  }
}

afterEach(clearCookies);

describe('guardas de ruta', () => {
  it('sin sesión redirige al login', async () => {
    stubApi(session(null));

    renderRoute('/');

    expect(await screen.findByRole('button', { name: 'Iniciar sesión' })).toBeInTheDocument();
  });

  it('un usuario sin rol admin ve «sin permiso» en administración', async () => {
    stubApi(session(USER));

    renderRoute('/admin/users');

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Usuarios' })).not.toBeInTheDocument();
  });

  it('el admin ve la sección de administración en la navegación', async () => {
    stubApi(session(ADMIN));

    renderRoute('/');

    expect(await screen.findByRole('link', { name: 'Usuarios' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Auditoría' })).toBeInTheDocument();
  });
});

describe('LoginPage', () => {
  it('inicia sesión con el token CSRF y vuelve a la ruta pedida', async () => {
    let loggedIn = false;
    const fetchMock = stubApi({
      ...session(null),
      'GET /api/v1/auth/me': () =>
        loggedIn ? { body: ADMIN } : { status: 401, body: { title: 'No autenticado', status: 401 } },
      'GET /api/v1/auth/csrf': { body: { csrf_token: 'tok-123' } },
      'POST /api/v1/auth/login': () => {
        loggedIn = true;
        return { body: ADMIN };
      },
      'GET /api/v1/users': { body: { items: [], total: 0 } },
    });
    const user = userEvent.setup();

    renderRoute('/login?next=%2Fadmin%2Fusers');
    await user.type(await screen.findByLabelText(/Usuario/), 'admin');
    await user.type(screen.getByLabelText(/Contraseña/), 'frase-de-paso-larga');
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }));

    expect(await screen.findByRole('heading', { name: 'Usuarios' })).toBeInTheDocument();
    const [login] = callsTo(fetchMock, 'POST', '/api/v1/auth/login');
    expect(login?.headers.get('X-CSRF-Token')).toBe('tok-123');
    expect(await login?.json()).toEqual({ username: 'admin', password: 'frase-de-paso-larga' });
  });

  it('muestra el error genérico con credenciales incorrectas y vacía la contraseña', async () => {
    stubApi({
      ...session(null),
      'GET /api/v1/auth/csrf': { body: { csrf_token: 'tok' } },
      'POST /api/v1/auth/login': {
        status: 401,
        body: { title: 'Credenciales no válidas', status: 401, detail: 'Usuario o contraseña incorrectos.' },
      },
    });
    const user = userEvent.setup();

    renderRoute('/login');
    await user.type(await screen.findByLabelText(/Usuario/), 'ana');
    await user.type(screen.getByLabelText(/Contraseña/), 'mala');
    await user.click(screen.getByRole('button', { name: 'Iniciar sesión' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Credenciales no válidas');
    expect(screen.getByLabelText(/Contraseña/)).toHaveValue('');
  });

  it('valida campos obligatorios sin llamar a la API', async () => {
    const fetchMock = stubApi(session(null));
    const user = userEvent.setup();

    renderRoute('/login');
    await user.click(await screen.findByRole('button', { name: 'Iniciar sesión' }));

    expect(screen.getAllByText('Campo obligatorio')).toHaveLength(2);
    expect(callsTo(fetchMock, 'POST', '/api/v1/auth/login')).toHaveLength(0);
  });
});

describe('menú de usuario', () => {
  it('cierra sesión con la cabecera CSRF de la cookie', async () => {
    document.cookie = 'dow_csrf=desde-cookie; path=/';
    let loggedIn = true;
    const fetchMock = stubApi({
      ...session(ADMIN),
      'GET /api/v1/auth/me': () =>
        loggedIn ? { body: ADMIN } : { status: 401, body: { title: 'No autenticado', status: 401 } },
      'POST /api/v1/auth/logout': () => {
        loggedIn = false;
        return { status: 204 };
      },
    });
    const user = userEvent.setup();

    renderRoute('/');
    await user.click(await screen.findByRole('button', { name: /Menú de usuario de Admin/ }));
    await user.click(await screen.findByRole('menuitem', { name: 'Cerrar sesión' }));

    expect(await screen.findByRole('button', { name: 'Iniciar sesión' })).toBeInTheDocument();
    const [logout] = callsTo(fetchMock, 'POST', '/api/v1/auth/logout');
    expect(logout?.headers.get('X-CSRF-Token')).toBe('desde-cookie');
  });
});

describe('ChangePasswordPage', () => {
  it('valida y cambia la contraseña', async () => {
    const fetchMock = stubApi({ ...session(USER), 'POST /api/v1/auth/password': { status: 204 } });
    const user = userEvent.setup();

    renderRoute('/account/password');
    await user.type(await screen.findByLabelText(/Contraseña actual/), 'vieja');
    await user.type(screen.getByLabelText(/^Contraseña nueva/), 'corta');
    await user.click(screen.getByRole('button', { name: 'Cambiar contraseña' }));
    expect(screen.getByText('Debe tener al menos 12 caracteres')).toBeInTheDocument();
    expect(screen.getByText('Las contraseñas no coinciden')).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/^Contraseña nueva/));
    await user.type(screen.getByLabelText(/^Contraseña nueva/), 'una-frase-larga');
    await user.type(screen.getByLabelText(/Repite/), 'una-frase-larga');
    await user.click(screen.getByRole('button', { name: 'Cambiar contraseña' }));

    expect(await screen.findByText('Contraseña cambiada')).toBeInTheDocument();
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/auth/password')).toHaveLength(1));
  });
});

describe('safeNext', () => {
  it('solo admite rutas internas', () => {
    expect(safeNext('/admin/users')).toBe('/admin/users');
    expect(safeNext('//evil.example')).toBe('/');
    expect(safeNext('https://evil.example')).toBe('/');
    expect(safeNext('/login')).toBe('/');
    expect(safeNext(null)).toBe('/');
  });
});
