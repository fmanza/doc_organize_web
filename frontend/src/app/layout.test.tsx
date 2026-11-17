import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, session, stubApi } from '../test/api';
import { renderRoute } from '../test/render';

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
