import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, session, stubApi, USER } from '../test/api';
import { PROJECT } from '../test/fixtures';
import { renderRoute } from '../test/render';

describe('Menú «Proyectos» (2.1.1)', () => {
  it('con un proyecto abierto, «Proyectos» sigue llevando a la lista', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects': { body: { items: [PROJECT], total: 1 } },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7');
    const group = await screen.findByRole('group', { name: 'Proyecto abierto: Proyecto A' });
    expect(within(group).getByRole('link', { name: /Duplicados/ })).toHaveAttribute(
      'href',
      '/projects/7/duplicates',
    );
    const navbar = document.getElementById('app-navbar');
    expect(navbar).not.toBeNull();
    const projects = within(navbar as HTMLElement).getByRole('link', { name: 'Proyectos' });
    expect(projects).toHaveAttribute('href', '/projects');

    await user.click(projects);

    await waitFor(() =>
      expect(screen.queryByRole('group', { name: /Proyecto abierto/ })).not.toBeInTheDocument(),
    );
  });

  it('un proyecto borrado o inexistente no deja secciones huérfanas en el menú', async () => {
    stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { status: 404, body: { title: 'Proyecto no encontrado', status: 404 } },
    });

    renderRoute('/projects/7/duplicates');

    await waitFor(() => expect(screen.queryAllByText('Proyecto no encontrado').length).toBeGreaterThan(0));
    const navbar = document.getElementById('app-navbar') as HTMLElement;
    expect(within(navbar).getByRole('link', { name: 'Proyectos' })).toHaveAttribute('href', '/projects');
    expect(within(navbar).queryByRole('group', { name: /Proyecto abierto/ })).not.toBeInTheDocument();
    expect(within(navbar).queryByRole('link', { name: /Escaneo/ })).not.toBeInTheDocument();
  });
});

describe('Layout en pantallas estrechas', () => {
  it('el botón abre el menú, que se pliega al navegar', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/runs': { body: { items: [], total: 0 } } });
    const user = userEvent.setup();

    renderRoute('/');
    const open = await screen.findByRole('button', { name: 'Abrir el menú' });
    expect(open).toHaveAttribute('aria-expanded', 'false');
    expect(open).toHaveAttribute('aria-controls', 'app-navbar');
    expect(document.getElementById('app-navbar')).toHaveAccessibleName('Navegación principal');

    await user.click(open);
    expect(screen.getByRole('button', { name: 'Cerrar el menú' })).toHaveAttribute('aria-expanded', 'true');

    await user.click(screen.getByRole('link', { name: 'Ejecuciones' }));
    expect(await screen.findByRole('button', { name: 'Abrir el menú' })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
  });
});
