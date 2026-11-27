import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ADMIN, session, stubApi, USER } from '../test/api';
import { PROJECT } from '../test/fixtures';
import { renderRoute } from '../test/render';
import { NAV_RAIL_STORAGE_KEY } from './navRail';

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

/** Una pantalla ancha: el mock de `matchMedia` de los tests dice que no casa ninguna media query. */
function wideScreen() {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: true,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

describe('Layout: menú contraído a una barra de iconos', () => {
  it('se contrae y se despliega, conserva los nombres accesibles y se recuerda', async () => {
    wideScreen();
    stubApi({ ...session(ADMIN), 'GET /api/v1/runs': { body: { items: [], total: 0 } } });
    const user = userEvent.setup();

    renderRoute('/');
    const collapse = await screen.findByRole('button', { name: 'Contraer el menú a iconos' });
    expect(collapse).toHaveAttribute('aria-expanded', 'true');
    expect(collapse).toHaveAttribute('aria-controls', 'app-navbar');
    const navbar = document.getElementById('app-navbar') as HTMLElement;
    expect(within(navbar).getByRole('button', { name: 'Acceso' })).toBeInTheDocument();

    await user.click(collapse);

    const expand = screen.getByRole('button', { name: 'Desplegar el menú' });
    expect(expand).toHaveAttribute('aria-expanded', 'false');
    expect(window.localStorage.getItem(NAV_RAIL_STORAGE_KEY)).toBe('1');
    // Los textos siguen siendo el nombre de cada enlace; los grupos se muestran abiertos, con su nombre.
    expect(within(navbar).getByRole('link', { name: 'Ejecuciones' })).toHaveAttribute('href', '/runs');
    const access = within(navbar).getByRole('group', { name: 'Acceso' });
    expect(within(access).getByRole('link', { name: 'Usuarios' })).toHaveAttribute('href', '/admin/users');
    expect(within(navbar).queryByRole('button', { name: 'Acceso' })).not.toBeInTheDocument();

    await user.click(expand);

    expect(screen.getByRole('button', { name: 'Contraer el menú a iconos' })).toBeInTheDocument();
    expect(window.localStorage.getItem(NAV_RAIL_STORAGE_KEY)).toBeNull();
    expect(within(navbar).getByRole('button', { name: 'Acceso' })).toBeInTheDocument();
  });

  it('en una pantalla estrecha no se ofrece aunque estuviera contraído', async () => {
    window.localStorage.setItem(NAV_RAIL_STORAGE_KEY, '1');
    stubApi({ ...session(ADMIN), 'GET /api/v1/runs': { body: { items: [], total: 0 } } });

    renderRoute('/');

    expect(await screen.findByRole('button', { name: 'Acceso' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Desplegar el menú' })).not.toBeInTheDocument();
  });
});
