import { fireEvent, screen, waitFor, within } from '@testing-library/react';
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

// jsdom (31+) evalúa las media queries con un ancho fijo de 1024 px: el botón (`hiddenFrom="sm"`) queda oculto con
// `display: none` y, oculto, no tiene nombre accesible (ni con `aria-label`), así que no se encuentra por rol y nombre.
// Aquí solo el cableado ARIA y el estado del botón; que se vea, abra y pliegue el menú en una pantalla estrecha lo
// prueba Playwright (e2e/mobile-menu.spec.ts).
describe('Layout: botón del menú', () => {
  it('controla la navegación principal y se pliega al navegar', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/runs': { body: { items: [], total: 0 } } });
    const user = userEvent.setup();

    renderRoute('/');
    const toggle = await waitFor(() => {
      const button = document.querySelector<HTMLButtonElement>('button[aria-controls="app-navbar"]');
      expect(button).not.toBeNull();
      return button as HTMLButtonElement;
    });
    expect(toggle).toHaveAttribute('aria-label', 'Abrir el menú');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(document.getElementById('app-navbar')).toHaveAccessibleName('Navegación principal');

    // `fireEvent`: user-event no pulsa elementos con `display: none`.
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-label', 'Cerrar el menú');
    expect(toggle).toHaveAttribute('aria-expanded', 'true');

    await user.click(screen.getByRole('link', { name: 'Ejecuciones' }));
    await waitFor(() => expect(toggle).toHaveAttribute('aria-expanded', 'false'));
    expect(toggle).toHaveAttribute('aria-label', 'Abrir el menú');
  });
});
