import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api/client';
import { formatCount, formatDateTime } from '../components/format';
import { problemTitle } from '../components/problem';
import i18n, { LANGUAGE_STORAGE_KEY, initialLanguage, setLanguage } from '../i18n';
import { ADMIN, callsTo, session, stubApi } from '../test/api';
import { renderRoute } from '../test/render';

const lang = () => document.documentElement.lang;

async function openLanguageGroup(menuName = 'Menú de usuario de Admin', groupName = 'Idioma') {
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: menuName }));
  return { user, group: await screen.findByRole('group', { name: groupName }) };
}

describe('idioma por usuario (2.6)', () => {
  it('el menú marca el idioma y elegir English cambia la interfaz, lang y la copia local', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'PUT /api/v1/auth/me/preferences': async (request) => ({
        body: { ...ADMIN, ...((await request.clone().json()) as object) },
      }),
    });
    renderRoute('/');

    const { user, group } = await openLanguageGroup();
    expect(within(group).getByRole('menuitem', { name: 'Español' })).toHaveAttribute('aria-current', 'true');
    const english = within(group).getByRole('menuitem', { name: 'English' });
    expect(english).toHaveAttribute('lang', 'en');

    await user.click(english);

    expect(await screen.findByRole('group', { name: 'Language' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'English' })).toHaveAttribute('aria-current', 'true');
    expect(lang()).toBe('en');
    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('en');
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/auth/me/preferences');
    expect(await request?.json()).toEqual({ language: 'en' });
    expect(request?.headers.get('Accept-Language')).toBe('es'); // la petición salió antes del cambio
  });

  it('aplica el idioma guardado en el usuario al llegar /me, aunque la copia local diga otro', async () => {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    stubApi(session({ ...ADMIN, language: 'en' } as never));

    renderRoute('/');

    expect(await screen.findByRole('button', { name: 'User menu for Admin' })).toBeInTheDocument();
    expect(lang()).toBe('en');
  });

  it('si no se puede guardar, vuelve al idioma anterior y lo avisa', async () => {
    stubApi({
      ...session(ADMIN),
      'PUT /api/v1/auth/me/preferences': { status: 500, body: { title: 'Error', status: 500 } },
    });
    renderRoute('/');

    const { user, group } = await openLanguageGroup();
    await user.click(within(group).getByRole('menuitem', { name: 'English' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo guardar el idioma');
    await waitFor(() => expect(lang()).toBe('es'));
    expect(screen.getByRole('menuitem', { name: 'Español' })).toHaveAttribute('aria-current', 'true');
  });

  it('elegir el idioma que ya tiene no llama a la API', async () => {
    const fetchMock = stubApi(session(ADMIN));
    renderRoute('/');

    const { user, group } = await openLanguageGroup();
    await user.click(within(group).getByRole('menuitem', { name: 'Español' }));

    expect(callsTo(fetchMock, 'PUT', '/api/v1/auth/me/preferences')).toHaveLength(0);
  });

  it('antes de iniciar sesión: copia local, después el navegador y, si no, español', () => {
    const languages = vi.spyOn(window.navigator, 'languages', 'get');

    languages.mockReturnValue(['en-US', 'es']);
    expect(initialLanguage()).toBe('en');
    languages.mockReturnValue(['fr-FR', 'de']);
    expect(initialLanguage()).toBe('es');
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');
    languages.mockReturnValue(['en-GB']);
    expect(initialLanguage()).toBe('es');

    languages.mockRestore();
  });

  it('fechas y números en en-GB y títulos de error por código o estado en inglés', async () => {
    await setLanguage('en');

    expect(formatCount(12345)).toBe('12,345');
    expect(formatDateTime('2026-11-25T08:05:00Z')).toMatch(/^25\/11\/2026, \d{2}:05:00$/);
    const t = i18n.t.bind(i18n);
    expect(problemTitle({ title: 'La ubicación está en uso', status: 409, code: 'location_in_use' }, t)).toBe(
      'The location is in use',
    );
    expect(problemTitle({ title: 'Datos de entrada no válidos', status: 422 }, t)).toBe('Invalid input data');
    expect(problemTitle({ title: '', status: 418 }, t)).toBe('Something went wrong');

    await setLanguage('es');
    expect(formatCount(12345)).toBe('12.345');
    expect(problemTitle(new ApiError({ title: 'La ubicación está en uso', status: 409 }).problem, t)).toBe(
      'La ubicación está en uso',
    );
  });
});
