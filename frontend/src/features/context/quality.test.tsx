import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';

// W5 (G3): calidad de la clasificación. Referencia y métricas sintéticas.
const RUN_ID = '66666666-6666-4666-8666-666666666666';
const REPORT = {
  axes: {
    domains: {
      axis: 'domains',
      multiple: false,
      labelled: 3,
      accuracy: 0.6667,
      coverage: 1,
      precision: 0.6667,
      recall: 0.6667,
      accuracy_by_classified_by: { rules: 1, ai: 0 },
      labelled_by_classified_by: { rules: 2, ai: 1 },
      confusions: [{ label: 'informes', assigned: 'facturas', count: 1 }],
    },
  },
  documents: 4,
  matched: 3,
  missing_documents: [],
  missing_total: 0,
};
const QUALITY = {
  gold: {
    filename: 'referencia.xlsx',
    sheet: 'Referencia',
    document_column: 'documento',
    columns: { domains: 'dominio_ok' },
    labels: 3,
    axes: ['domains'],
    uploaded_at: '2026-11-20T08:00:00+00:00',
    uploaded_by: 'ana',
  },
  decisions_available: false,
  evaluation: {
    run_id: RUN_ID,
    finished_at: '2026-11-20T09:00:00Z',
    result: { gold: 'xlsx', report: REPORT },
  },
  dry_run: {
    run_id: RUN_ID,
    finished_at: '2026-11-20T10:00:00Z',
    result: {
      baseline: REPORT,
      candidate: { ...REPORT, axes: { domains: { ...REPORT.axes.domains, accuracy: 1 } } },
      documents: 3,
      ai: { calls: 1, prompt_tokens: 100, completion_tokens: 20, model: 'modelo-prueba' },
    },
  },
};

describe('Calidad', () => {
  it('muestra la evaluación y la comparación, y lanza una evaluación', async () => {
    const fetchMock = stubApi({
      ...session(USER),
      'GET /api/v1/projects/7': { body: PROJECT },
      'GET /api/v1/projects/7/context/quality': { body: QUALITY },
      'GET /api/v1/taxonomy-templates': { body: { items: [] } },
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: RUN_ID, operation: 'context_evaluate' }),
      },
      [`GET /api/v1/runs/${RUN_ID}`]: { body: runOut({ id: RUN_ID, operation: 'context_evaluate' }) },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/context/quality');

    expect(await screen.findByText(/referencia.xlsx: 3 documentos etiquetados/)).toBeInTheDocument();
    const evaluation = screen.getByRole('region', { name: 'Evaluación del contexto' });
    expect(within(evaluation).getAllByText('67 %').length).toBeGreaterThan(0);
    expect(within(evaluation).getByText('«informes» clasificado como «facturas»: 1')).toBeInTheDocument();
    const compare = screen.getByRole('region', { name: 'Comparar cambios' });
    expect(within(compare).getByText('100 %')).toBeInTheDocument();
    expect(within(compare).getByText('+33')).toBeInTheDocument();

    await user.click(within(evaluation).getByRole('button', { name: 'Evaluar' }));
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toEqual({ operation: 'context_evaluate', gold: 'xlsx' });
  });
});
