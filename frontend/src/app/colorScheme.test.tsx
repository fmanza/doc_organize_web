import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi } from '../test/api';
import { renderRoute } from '../test/render';
import indexHtml from '../../index.html?raw';
import preReactScript from '../../public/color-scheme.js?raw';
import { COLOR_SCHEME_STORAGE_KEY } from './colorScheme';

const scheme = () => document.documentElement.getAttribute('data-mantine-color-scheme');

async function openThemeGroup() {
  const user = userEvent.setup();
  await user.click(await screen.findByRole('button', { name: 'Menú de usuario de Admin' }));
  return { user, group: await screen.findByRole('group', { name: 'Tema' }) };
}

describe('tema por usuario (2.3)', () => {
  it('el script previo a React lee la misma clave que el gestor de Mantine', () => {
    expect(preReactScript).toContain(`'${COLOR_SCHEME_STORAGE_KEY}'`);
    expect(indexHtml).toContain('<script src="/color-scheme.js"></script>');
  });

  it('aplica el tema guardado en el usuario al llegar /me', async () => {
    stubApi(session({ ...ADMIN, color_scheme: 'dark' } as never));

    renderRoute('/');

    await waitFor(() => expect(scheme()).toBe('dark'));
  });

  it('el menú marca el tema elegido y guardar otro lo aplica al momento', async () => {
    const fetchMock = stubApi({
      ...session(ADMIN),
      'PUT /api/v1/auth/me/preferences': async (request) => ({
        body: { ...ADMIN, ...((await request.clone().json()) as object) },
      }),
    });
    renderRoute('/');

    const { user, group } = await openThemeGroup();
    expect(within(group).getByRole('menuitem', { name: 'Como el sistema' })).toHaveAttribute(
      'aria-current',
      'true',
    );
    expect(within(group).getByRole('menuitem', { name: 'Oscuro' })).not.toHaveAttribute('aria-current');

    await user.click(within(group).getByRole('menuitem', { name: 'Oscuro' }));

    await waitFor(() => expect(scheme()).toBe('dark'));
    // El menú sigue abierto para ver el cambio, con la opción nueva marcada.
    expect(screen.getByRole('menuitem', { name: 'Oscuro' })).toHaveAttribute('aria-current', 'true');
    const [request] = callsTo(fetchMock, 'PUT', '/api/v1/auth/me/preferences');
    expect(await request?.json()).toEqual({ color_scheme: 'dark' });
  });

  it('si no se puede guardar, vuelve al tema anterior y lo avisa', async () => {
    stubApi({
      ...session({ ...ADMIN, color_scheme: 'light' } as never),
      'PUT /api/v1/auth/me/preferences': { status: 500, body: { title: 'Error', status: 500 } },
    });
    renderRoute('/');
    await waitFor(() => expect(scheme()).toBe('light'));

    const { user, group } = await openThemeGroup();
    await user.click(within(group).getByRole('menuitem', { name: 'Oscuro' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo guardar el tema');
    await waitFor(() => expect(scheme()).toBe('light'));
    expect(screen.getByRole('menuitem', { name: 'Claro' })).toHaveAttribute('aria-current', 'true');
  });

  it('elegir el tema que ya tiene no llama a la API', async () => {
    const fetchMock = stubApi(session(ADMIN));
    renderRoute('/');

    const { user, group } = await openThemeGroup();
    await user.click(within(group).getByRole('menuitem', { name: 'Como el sistema' }));

    expect(callsTo(fetchMock, 'PUT', '/api/v1/auth/me/preferences')).toHaveLength(0);
  });
});
