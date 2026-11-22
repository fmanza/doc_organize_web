import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';

import { callsTo, session, stubApi, USER } from '../../test/api';
import { PROJECT, runOut } from '../../test/fixtures';
import { renderRoute } from '../../test/render';
import { choices, type DuplicateGroup, keepByPolicy } from './useDuplicates';

const PREVIEW_ID = '22222222-2222-4222-8222-222222222222';
const DRY_ID = '33333333-3333-4333-8333-333333333333';
const REAL_ID = '44444444-4444-4444-8444-444444444444';

function member(key: string, modified: string, canonical: boolean) {
  const [folder = '', ...rest] = key.split('/');
  return {
    key,
    folder,
    path: rest.join('/'),
    size_bytes: 1024,
    modified_at: modified,
    sha256: 'a'.repeat(64),
    canonical,
    output_path: `${key.replace(/\.[^.]+$/, '')}.md`,
  };
}

const EXACT: DuplicateGroup = {
  group_id: 'g-exact',
  reason: 'exact_duplicate',
  contained: false,
  members: [
    member('2024/factura.pdf', '2026-01-01T00:00:00Z', true),
    member('2025/copias/factura (copia).pdf', '2026-03-01T00:00:00Z', false),
  ],
};
const FUZZY: DuplicateGroup = {
  group_id: 'g-fuzzy',
  reason: 'fuzzy_name_match',
  contained: false,
  members: [
    member('2024/presupuesto obra.pdf', '2026-01-02T00:00:00Z', true),
    member('2025/presupuesto obras.pdf', '2026-01-03T00:00:00Z', false),
  ],
};

const PREVIEW = runOut({
  id: PREVIEW_ID,
  operation: 'dedup_preview',
  status: 'succeeded',
  finished_at: '2026-11-02T08:00:00Z',
  result: { groups: 2, exact_groups: 1, fuzzy_groups: 1 },
});

function routes(extra: Parameters<typeof stubApi>[0] = {}) {
  return stubApi({
    ...session(USER),
    'GET /api/v1/projects/7': { body: PROJECT },
    'GET /api/v1/projects/7/duplicates/last': {
      body: { preview: { ...PREVIEW, operation: 'dedup_preview' }, apply: null },
    },
    [`GET /api/v1/runs/${PREVIEW_ID}`]: { body: PREVIEW },
    [`GET /api/v1/runs/${PREVIEW_ID}/duplicate-groups`]: {
      body: { run: PREVIEW, items: [EXACT, FUZZY], total: 2 },
    },
    ...extra,
  });
}

describe('selección de duplicados', () => {
  it('conserva según la política y no aplica los parecidos por defecto', () => {
    expect(keepByPolicy(EXACT, 'oldest')).toBe('2024/factura.pdf');
    expect(keepByPolicy(EXACT, 'newest')).toBe('2025/copias/factura (copia).pdf');
    expect(keepByPolicy(EXACT, 'shortest')).toBe('2024/factura.pdf');
    expect(choices([EXACT, FUZZY], 'oldest', {})).toEqual([
      { group_id: 'g-exact', keep: '2024/factura.pdf' },
    ]);
    expect(
      choices([EXACT, FUZZY], 'oldest', {
        'g-exact': { keep: '2025/copias/factura (copia).pdf' },
        'g-fuzzy': { include: true },
      }),
    ).toEqual([
      { group_id: 'g-exact', keep: '2025/copias/factura (copia).pdf' },
      { group_id: 'g-fuzzy', keep: '2024/presupuesto obra.pdf' },
    ]);
  });
});

describe('DuplicatesPage', () => {
  // Las decisiones se guardan por búsqueda en sessionStorage: cada test empieza sin ellas.
  beforeEach(() => sessionStorage.clear());

  it('muestra los grupos lado a lado y cambia lo que se conserva con la política', async () => {
    routes();
    const user = userEvent.setup();

    renderRoute('/projects/7/duplicates');

    const keepCopy = await screen.findByRole('radio', { name: 'Conservar 2025/copias/factura (copia).pdf' });
    expect(screen.getByRole('radio', { name: 'Conservar 2024/factura.pdf' })).toBeChecked();
    expect(
      screen
        .getAllByRole('checkbox', { name: /^Aplicar el grupo/ })
        .map((c) => (c as HTMLInputElement).checked),
    ).toEqual([true, false]);
    await user.click(screen.getByRole('combobox', { name: 'Conservar por defecto' }));
    await user.click(await screen.findByRole('option', { name: 'El más reciente', hidden: true }));
    expect(keepCopy).toBeChecked();
  });

  it('2.2: busca por contenido; «contenido parecido» solo con el modelo de duplicados', async () => {
    const fetchMock = routes({
      'GET /api/v1/ai/status': {
        body: { families: { litellm: true }, tasks: { classify: true, dedup: false } },
      },
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: DRY_ID, operation: 'dedup_preview' }),
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/duplicates');

    const semantic = await screen.findByRole('switch', { name: /Contenido parecido \(IA\)/ });
    expect(semantic).toBeDisabled();
    expect(screen.getByText(/Necesita el modelo propio de «Duplicados por contenido»/)).toBeInTheDocument();
    await user.click(screen.getByRole('switch', { name: /Mismo contenido/ }));
    await user.click(screen.getByRole('button', { name: 'Buscar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toEqual({
      operation: 'dedup_preview',
      fuzzy_threshold: null,
      content: true,
      semantic_threshold: null,
    });
  });

  it('2.2: con el modelo de duplicados pide el umbral y avisa de lo que se envía', async () => {
    const fetchMock = routes({
      'GET /api/v1/ai/status': { body: { families: { litellm: true }, tasks: { dedup: true } } },
      'POST /api/v1/projects/7/runs': {
        status: 202,
        body: runOut({ id: DRY_ID, operation: 'dedup_preview' }),
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/duplicates');
    const semantic = await screen.findByRole('switch', { name: /Contenido parecido \(IA\)/ });
    await waitFor(() => expect(semantic).toBeEnabled());
    await user.click(semantic);

    expect(screen.getByText(/Se envía el texto completo/)).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Similitud mínima (0,5–1)' })).toHaveValue('0.9');
    await user.click(screen.getByRole('button', { name: 'Buscar' }));
    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(1));
    const [request] = callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs');
    expect(await request?.clone().json()).toMatchObject({ content: true, semantic_threshold: 0.9 });
  });

  it('2.2: un grupo parecido muestra sus similitudes y compara el texto plano lado a lado', async () => {
    const similar: DuplicateGroup = {
      group_id: 'g-similar',
      reason: 'semantic_content_match',
      similarity: 0.93,
      lexical_similarity: 0.41,
      contained: true,
      members: [
        member('2024/contrato.docx', '2026-01-01T00:00:00Z', true),
        member('2025/contrato v2.docx', '2026-02-01T00:00:00Z', false),
      ],
    };
    routes({
      [`GET /api/v1/runs/${PREVIEW_ID}/duplicate-groups`]: {
        body: { run: PREVIEW, items: [similar], total: 1 },
      },
      'GET /api/v1/projects/7/outputs': (request) => ({
        body: new URL(request.url).searchParams.get('path')?.startsWith('2024')
          ? ['Cláusula común', '<script>alert(1)</script>'].join('\n')
          : ['Cláusula común', 'Cláusula nueva'].join('\n'),
      }),
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/duplicates');

    expect(await screen.findByText('Significado 93 %')).toBeInTheDocument();
    expect(screen.getByText('Texto 41 %')).toBeInTheDocument();
    expect(screen.getByText('Contenido en otro')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Ver diferencias' }));
    const dialog = await screen.findByRole('dialog', { name: 'Comparar documentos' });

    expect(await within(dialog).findByText(/<script>alert\(1\)<\/script>/)).toBeInTheDocument(); // texto
    expect(within(dialog).getByText(/Cláusula nueva/)).toBeInTheDocument();
    expect(document.querySelector('script')).toBeNull();
  });

  it('aplica en dos pasos: vista previa y nombre del proyecto', async () => {
    const fetchMock = routes({
      'POST /api/v1/projects/7/runs': async (request) => {
        const body = (await request.clone().json()) as { dry_run: boolean };
        return {
          status: 202,
          body: runOut({ id: body.dry_run ? DRY_ID : REAL_ID, operation: 'dedup_apply' }),
        };
      },
      [`GET /api/v1/runs/${DRY_ID}`]: {
        body: runOut({
          id: DRY_ID,
          operation: 'dedup_apply',
          status: 'succeeded',
          result: { mode: 'copy', groups: 1, files: 1, skipped_changed: 0 },
        }),
      },
      [`GET /api/v1/runs/${REAL_ID}`]: { body: runOut({ id: REAL_ID, operation: 'dedup_apply' }) },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/duplicates');
    await user.click(await screen.findByRole('button', { name: 'Aplicar…' }));
    const dialog = await screen.findByRole('dialog');
    await user.click(within(dialog).getByRole('button', { name: 'Calcular qué se aplicaría' }));
    const confirm = await within(dialog).findByRole('textbox', { name: /Escribe «Proyecto A»/ });
    await user.type(confirm, 'Proyecto A');
    await user.click(within(dialog).getByRole('button', { name: 'Copiar' }));

    await waitFor(() => expect(callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs')).toHaveLength(2));
    const [dry, real] = await Promise.all(
      callsTo(fetchMock, 'POST', '/api/v1/projects/7/runs').map((r) => r.clone().json() as Promise<object>),
    );
    expect(dry).toMatchObject({
      operation: 'dedup_apply',
      groups_run_id: PREVIEW_ID,
      mode: 'copy',
      dry_run: true,
      groups: [{ group_id: 'g-exact', keep: '2024/factura.pdf' }],
    });
    expect(real).toMatchObject({ dry_run: false, preview_run_id: DRY_ID, confirm_name: 'Proyecto A' });
  });
});

describe('Fase 10: grupos largos', () => {
  beforeEach(() => sessionStorage.clear());

  it('pliega un grupo de muchos documentos y pagina de 10 en 10', async () => {
    const big: DuplicateGroup = {
      group_id: 'g-big',
      reason: 'exact_duplicate',
      contained: false,
      members: Array.from({ length: 8 }, (_, index) =>
        member(`2024/copia-${index}.pdf`, `2026-01-0${index + 1}T00:00:00Z`, index === 0),
      ),
    };
    const fetchMock = routes({
      [`GET /api/v1/runs/${PREVIEW_ID}/duplicate-groups`]: {
        body: { run: PREVIEW, items: [big], total: 25 },
      },
    });
    const user = userEvent.setup();

    renderRoute('/projects/7/duplicates');

    expect(await screen.findByText('2024/copia-4.pdf')).toBeInTheDocument();
    expect(screen.queryByText('2024/copia-5.pdf')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Ver 3 documentos más' }));
    expect(screen.getByText('2024/copia-7.pdf')).toBeInTheDocument();

    expect(screen.getByText('1–10 de 25')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Página siguiente' }));
    await waitFor(() =>
      expect(
        callsTo(fetchMock, 'GET', `/api/v1/runs/${PREVIEW_ID}/duplicate-groups`).some(
          (request) => new URL(request.url).searchParams.get('offset') === '10',
        ),
      ).toBe(true),
    );
  });
});
