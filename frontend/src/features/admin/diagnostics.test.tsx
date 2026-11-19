import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { ADMIN, callsTo, session, stubApi, USER } from '../../test/api';
import { renderRoute } from '../../test/render';

// W4: diagnóstico del entorno (check_environment). Datos sintéticos.
const REPORT = {
  ok: false,
  checked_at: '2026-11-20T08:00:00Z',
  checks: [
    { name: 'python', status: 'ok', detail: 'Python 3.12', remedy: null },
    { name: 'gpu', status: 'warning', detail: 'Sin GPU CUDA', remedy: 'El OCR irá por CPU' },
    { name: 'ai:classify', status: 'error', detail: 'El modelo no responde', remedy: 'Revisa el alias' },
  ],
};

describe('DiagnosticsPage', () => {
  it('ejecuta el diagnóstico con la IA y muestra cada comprobación', async () => {
    const fetchMock = stubApi({ ...session(ADMIN), 'POST /api/v1/admin/diagnostics': { body: REPORT } });
    const user = userEvent.setup();

    renderRoute('/admin/diagnostics');

    await user.click(await screen.findByRole('checkbox', { name: /Probar también los modelos de IA/ }));
    await user.click(screen.getByRole('button', { name: 'Ejecutar diagnóstico' }));

    expect(await screen.findByText('Hay comprobaciones con error')).toBeInTheDocument();
    expect(screen.getByText('ai:classify')).toBeInTheDocument();
    expect(screen.getByText('Revisa el alias')).toBeInTheDocument();
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/admin/diagnostics')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/admin/diagnostics');
    expect(await request?.clone().json()).toEqual({ check_ai: true });
  });

  it('un usuario sin rol de instancia no la ve', async () => {
    stubApi({ ...session(USER) });

    renderRoute('/admin/diagnostics');

    expect(await screen.findByText('Sin permiso')).toBeInTheDocument();
  });
});
