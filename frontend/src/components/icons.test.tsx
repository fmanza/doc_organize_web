import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, session, stubApi } from '../test/api';
import { PROJECT } from '../test/fixtures';
import { renderRoute } from '../test/render';

/** Código de la app (sin tests) y textos: nada de emojis ni flechas Unicode haciendo de icono (2026-11-17). */
const SOURCES = import.meta.glob(
  ['../**/*.{ts,tsx}', '../i18n/**/*.json', '!../**/*.test.{ts,tsx}', '!../api/**'],
  {
    query: '?raw',
    import: 'default',
    eager: true,
  },
) as Record<string, string>;
// Flechas (← ↑ ↓ ↕), formas (● ▲ ■ ▶), ✓ ✕ y emojis. «→», «›», «·» y «…» son puntuación de los textos y se permiten.
const ICON_LIKE = /[←↑↓↕■-◿✓✕\u{1F300}-\u{1FAFF}]/u;

describe('iconos', () => {
  it('ningún emoji ni símbolo Unicode hace de icono: se usan los de components/icons', () => {
    const offenders = Object.entries(SOURCES)
      .filter(([, text]) => ICON_LIKE.test(text))
      .map(([path, text]) => `${path}: ${text.match(ICON_LIKE)?.[0]}`);

    expect(Object.keys(SOURCES).length).toBeGreaterThan(50);
    expect(offenders).toEqual([]);
  });

  it('cada entrada del menú lleva su icono decorativo, también dentro de los grupos', async () => {
    stubApi({ ...session(ADMIN), 'GET /api/v1/projects/7': { body: PROJECT } });

    const user = userEvent.setup();

    renderRoute('/projects/7/scan');
    await screen.findByRole('link', { name: 'Escaneo' });
    await user.click(screen.getByRole('button', { name: 'Acceso' }));
    await user.click(screen.getByRole('button', { name: 'IA' }));

    const nav = screen.getByRole('navigation', { name: 'Navegación principal' });
    const entries = Array.from(nav.querySelectorAll('a, button'));
    const withoutIcon = entries
      .filter((entry) => !entry.querySelector('svg[aria-hidden="true"]'))
      .map((entry) => entry.textContent);

    // Inicio, Proyectos, el proyecto abierto y sus 4 secciones (2.1.1), Ejecuciones, Ubicaciones y las 14 de
    // administración (2 grupos y sus 7; W4: Diagnóstico).
    expect(entries).toHaveLength(23);
    expect(withoutIcon).toEqual([]);
  });
});
